"""Batch product-image processor -- command-line entry point.

For every product subfolder inside a chosen parent folder, this program removes
image backgrounds, mattes each onto pure white, auto-crops with white-space
padding, and saves JPEGs (quality 90) into an output folder that mirrors the
input structure exactly. Originals are never modified.

It also produces an Excel report (append/update), a detailed log, and a
resume-safe state file so an interrupted run can pick up where it left off.

Usage:
    python main.py                       # pick folders with dialogs
    python main.py --input RAW --output OUT
    python main.py --input RAW --output OUT --workers 4 --model u2net
    python main.py --input RAW --output OUT --force     # ignore saved progress
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

import config
from excel_report import ExcelReport
from image_processor import create_session, process_image
from logger import setup_logger
from state import ProcessingState
from utils import build_output_names, list_images, list_product_folders


# --------------------------------------------------------------------------- #
# Command line + folder selection                                              #
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated batch background removal for product images."
    )
    parser.add_argument(
        "--input", type=Path, help="Parent folder that contains the product subfolders."
    )
    parser.add_argument(
        "--output", type=Path, help="Output folder (created automatically)."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config.DEFAULT_WORKERS,
        help=f"Parallel worker threads (default: {config.DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--model",
        default=config.REMBG_MODEL,
        help=f"rembg model name (default: {config.REMBG_MODEL}).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=config.JPEG_QUALITY,
        help=f"Output JPEG quality 1-95 (default: {config.JPEG_QUALITY}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess everything, ignoring the saved progress state.",
    )
    return parser.parse_args(argv)


def pick_folder(title: str) -> Path | None:
    """Open a native folder-picker dialog; return the chosen path or None.

    Returns None if the dialog is cancelled or a GUI is unavailable (headless),
    in which case the caller should fall back to --input/--output.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        chosen = filedialog.askdirectory(title=title)
    finally:
        root.destroy()
    return Path(chosen) if chosen else None


def resolve_folders(args: argparse.Namespace) -> tuple[Path, Path]:
    """Determine the input and output folders from args or dialogs; validate."""
    input_dir = args.input or pick_folder("Select the Raw Images parent folder")
    if not input_dir:
        sys.exit("No input folder selected. Use --input or choose one in the dialog.")
    input_dir = Path(input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        sys.exit(f"Input folder does not exist: {input_dir}")

    output_dir = args.output or pick_folder("Select the Output folder")
    if not output_dir:
        sys.exit("No output folder selected. Use --output or choose one in the dialog.")
    output_dir = Path(output_dir).expanduser().resolve()

    if output_dir == input_dir:
        sys.exit("Input and output folders must be different.")
    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


# --------------------------------------------------------------------------- #
# Folder decision rule                                                         #
# --------------------------------------------------------------------------- #
def decide_folder(count: int) -> tuple[bool, str]:
    """Return (should_process, base_comment) for a folder with ``count`` images.

    See ``config`` for the thresholds:
      * 0 images            -> not processed, "empty"
      * 1..6                -> processed, no comment
      * 7..8                -> processed, "trim to 6" flag
      * 9 or more           -> not processed, "discard"
    """
    if count == 0:
        return False, config.COMMENT_EMPTY
    if count >= config.SKIP_MIN:
        return False, config.COMMENT_SKIP.format(count=count, max_ok=config.REVIEW_MAX)
    if config.REVIEW_MIN <= count <= config.REVIEW_MAX:
        return True, config.COMMENT_REVIEW.format(count=count, keep=config.TARGET_KEEP)
    return True, config.COMMENT_NORMAL


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #
def _flush(report: ExcelReport, state: ProcessingState, folder_index: int) -> None:
    """Persist state every folder and the report every ``EXCEL_SAVE_EVERY``."""
    state.save()
    if (folder_index + 1) % max(1, config.EXCEL_SAVE_EVERY) == 0:
        report.save()


def run(input_dir: Path, output_dir: Path, args: argparse.Namespace) -> None:
    """Process every product folder under ``input_dir`` into ``output_dir``."""
    logger = setup_logger(output_dir / config.LOG_FILENAME)
    logger.info("=== Run started ===")
    logger.info("Input : %s", input_dir)
    logger.info("Output: %s", output_dir)
    logger.info(
        "Model=%s workers=%d quality=%d force=%s",
        args.model,
        args.workers,
        args.quality,
        args.force,
    )

    # CLI override read at processing time by image_processor via config.*
    config.JPEG_QUALITY = args.quality

    state = ProcessingState(output_dir / config.STATE_FILENAME)
    report = ExcelReport(output_dir / config.REPORT_FILENAME)

    # Never treat the output folder as a product folder (matters if nested).
    folders = [f for f in list_product_folders(input_dir) if f.resolve() != output_dir]
    if not folders:
        msg = f"No product subfolders found in {input_dir}"
        logger.warning(msg)
        print(msg)
        return

    # Plan first so the progress bar knows the true total up front.
    plan: list[tuple[Path, list[Path], bool, str]] = []
    total_to_process = 0
    for folder in folders:
        images = list_images(folder)
        should_process, comment = decide_folder(len(images))
        if not should_process and not config.LIST_EMPTY_FOLDERS and len(images) == 0:
            continue
        plan.append((folder, images, should_process, comment))
        if should_process:
            total_to_process += len(images)

    logger.info("Folders=%d images_to_process=%d", len(plan), total_to_process)

    session = None
    if total_to_process:
        print(
            f"Loading background-removal model '{args.model}' "
            f"(first run downloads it; this can take a minute)..."
        )
        session = create_session(args.model)

    interrupted = False
    progress = tqdm(
        total=total_to_process, unit="img", desc="Starting", dynamic_ncols=True
    )
    executor = ThreadPoolExecutor(max_workers=max(1, args.workers))
    try:
        for folder_index, (folder, images, should_process, base_comment) in enumerate(
            plan
        ):
            name = folder.name
            progress.set_description(name[:24])

            # Empty / discard folders: record and continue (no editing).
            if not should_process:
                report.upsert(name, len(images), base_comment)
                state.set_folder(
                    name,
                    status="skipped",
                    count=len(images),
                    processed=0,
                    comment=base_comment,
                )
                logger.info(
                    "Folder %-26s | %d images | %s",
                    name,
                    len(images),
                    base_comment or "skipped",
                )
                _flush(report, state, folder_index)
                continue

            # Resume: whole folder already finished on a previous run.
            if not args.force and state.is_folder_done(name):
                progress.update(len(images))
                logger.info("Folder %-26s | already done, skipped", name)
                continue

            _process_folder(
                folder,
                images,
                base_comment,
                output_dir,
                session,
                executor,
                report,
                state,
                progress,
                logger,
                force=args.force,
            )
            _flush(report, state, folder_index)

    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Interrupted by user - saving progress...")
        print("\nInterrupted - saving progress so you can resume...")
    finally:
        # Cancel not-yet-started tasks; let in-flight images finish cleanly.
        executor.shutdown(wait=True, cancel_futures=True)
        progress.close()
        report.save()
        state.save()
        logger.info("=== Run %s ===", "interrupted" if interrupted else "finished")

    _print_summary(plan, output_dir, interrupted)


def _process_folder(
    folder: Path,
    images: list[Path],
    base_comment: str,
    output_dir: Path,
    session: object,
    executor: ThreadPoolExecutor,
    report: ExcelReport,
    state: ProcessingState,
    progress: tqdm,
    logger,
    *,
    force: bool,
) -> None:
    """Process every image in a single folder in parallel, then record results."""
    name = folder.name
    out_dir = output_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    names = build_output_names(images, name)

    logger.info("Folder %-26s | %d images | processing", name, len(images))
    folder_start = time.perf_counter()

    done_count = 0
    fail_count = 0
    futures = {}

    for src in images:
        dst = out_dir / names[src]
        key = str(src)
        # Skip images already finished on a previous run (unless --force).
        if not force and state.is_image_done(key) and dst.exists():
            done_count += 1
            progress.update(1)
            continue
        futures[executor.submit(process_image, src, dst, session)] = (src, dst, key)

    for future in as_completed(futures):
        src, dst, key = futures[future]
        result = future.result()  # process_image never raises
        if result.status == "processed":
            done_count += 1
            state.mark_image_done(key)
            logger.info(
                "  OK   %-38s -> %-30s (%.2fs)", src.name, dst.name, result.elapsed_s
            )
        else:
            fail_count += 1
            logger.error("  FAIL %-38s | %s", src.name, result.error)
        progress.update(1)

    elapsed = time.perf_counter() - folder_start
    comment = base_comment
    if fail_count:
        partial = config.COMMENT_PARTIAL.format(
            done=done_count, total=len(images), failed=fail_count
        )
        comment = f"{base_comment} | {partial}" if base_comment else partial

    report.upsert(name, len(images), comment)
    # Only a fully successful folder is "done"; if any image failed the folder
    # is "partial" so a later rerun retries just the failures (successful images
    # are skipped via the image-level state).
    status = "done" if fail_count == 0 else "partial"
    state.set_folder(
        name, status=status, count=len(images), processed=done_count, comment=comment
    )
    logger.info(
        "Folder %-26s | done=%d failed=%d (%.1fs)", name, done_count, fail_count, elapsed
    )


def _print_summary(
    plan: list[tuple[Path, list[Path], bool, str]], output_dir: Path, interrupted: bool
) -> None:
    """Print a short human-readable summary at the end of a run."""
    total = len(plan)
    to_edit = sum(1 for _, _, should, _ in plan if should)
    skipped = total - to_edit
    print()
    print(
        f"{'Interrupted' if interrupted else 'Done'}. "
        f"{total} folders scanned | {to_edit} processed | {skipped} skipped/empty."
    )
    print(f"Output : {output_dir}")
    print(f"Report : {output_dir / config.REPORT_FILENAME}")
    print(f"Log    : {output_dir / config.LOG_FILENAME}")
    if interrupted:
        print("Re-run the same command to resume where it left off.")


def main(argv: list[str] | None = None) -> None:
    """Program entry point."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_dir, output_dir = resolve_folders(args)
    run(input_dir, output_dir, args)


if __name__ == "__main__":
    main()
