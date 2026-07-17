"""Create cropped MANUAL copies for raw folders missing from edited output.

Folder rules:
  - ``Raw Images`` is read-only and is never deleted or modified.
  - ``Edited Images`` contains the background-removed, white-background output.
  - ``MANUAL`` contains cropped-only JPEG copies.
  - If a product folder exists in ``Raw Images`` but not in ``Edited Images``,
    that raw folder is cropped into ``MANUAL``.
  - If ``Edited Images`` is empty, every raw product folder is cropped into
    ``MANUAL``.
"""
from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from tqdm import tqdm

import config
from image_processor import create_session, remove_background
from utils import list_images, list_product_folders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CropResult:
    """Outcome of processing a single image."""

    source: Path
    output: Path | None
    status: str  # "cropped" | "failed"
    elapsed_s: float = 0.0
    error: str = ""


def _load_image(path: Path) -> Image.Image:
    """Open ``path``, apply EXIF orientation, optionally cap its size."""
    img = Image.open(path)
    img.load()
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # pragma: no cover - best effort
        pass

    if config.MAX_INPUT_DIMENSION:
        width, height = img.size
        longest = max(width, height)
        if longest > config.MAX_INPUT_DIMENSION:
            scale = config.MAX_INPUT_DIMENSION / longest
            img = img.resize(
                (round(width * scale), round(height * scale)),
                Image.LANCZOS,
            )
    return img


def _find_content_bbox(original: Image.Image, session: object) -> tuple[int, int, int, int] | None:
    """Find the detected object's bounding box using rembg's foreground mask."""
    rgba = remove_background(original, session)
    alpha = rgba.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > config.ALPHA_THRESHOLD else 0)
    return mask.getbbox()


def _crop_with_padding(original: Image.Image, session: object) -> Image.Image:
    """Crop the original image around the detected object with light padding."""
    bbox = _find_content_bbox(original, session)
    if bbox is None:
        logger.warning("No object boundary detected; keeping full original frame.")
        return original.convert("RGB")

    left, upper, right, lower = bbox
    obj_w = right - left
    obj_h = lower - upper
    pad_x = max(config.MIN_PADDING_PX, round(obj_w * config.PADDING_RATIO))
    pad_y = max(config.MIN_PADDING_PX, round(obj_h * config.PADDING_RATIO))

    crop_box = (
        max(0, left - pad_x),
        max(0, upper - pad_y),
        min(original.width, right + pad_x),
        min(original.height, lower + pad_y),
    )
    return original.convert("RGB").crop(crop_box)


def crop_image(src: Path, dst: Path, session: object) -> CropResult:
    """Crop and save a single image. Never raises."""
    start = time.perf_counter()
    try:
        with _load_image(src) as original:
            final = _crop_with_padding(original, session)
            dst.parent.mkdir(parents=True, exist_ok=True)
            final.save(dst, config.OUTPUT_FORMAT, quality=config.JPEG_QUALITY)
        return CropResult(src, dst, "cropped", time.perf_counter() - start)
    except Exception as exc:  # noqa: BLE001 - keep batch going
        logger.debug("Traceback while processing %s", src, exc_info=True)
        return CropResult(
            src,
            None,
            "failed",
            time.perf_counter() - start,
            error=f"{type(exc).__name__}: {exc}",
        )


def _folder_has_any_images(folder: Path) -> bool:
    """Return True if ``folder`` or one of its product folders contains images."""
    if not folder.exists():
        return False
    if list_images(folder):
        return True
    return any(list_images(child) for child in list_product_folders(folder))


def _select_manual_folders(raw_root: Path, edited_root: Path) -> list[Path]:
    """Return raw product folders that should be copied into MANUAL."""
    raw_folders = list_product_folders(raw_root)
    if not raw_folders:
        return []

    if not _folder_has_any_images(edited_root):
        logger.info("Edited Images is empty, so all raw folders will be cropped into MANUAL.")
        return raw_folders

    edited_names = {folder.name.rstrip() for folder in list_product_folders(edited_root)}
    missing = [folder for folder in raw_folders if folder.name not in edited_names]
    logger.info(
        "Found %d raw folders missing from Edited Images out of %d total.",
        len(missing),
        len(raw_folders),
    )
    return missing


def process_manual_queue(
    raw_root: Path,
    edited_root: Path,
    manual_root: Path,
    *,
    workers: int,
    force: bool,
) -> int:
    """Build cropped MANUAL copies from the selected raw folders."""
    if not raw_root.exists():
        logger.error("Raw Images folder does not exist: %s", raw_root)
        return 1

    targets = _select_manual_folders(raw_root, edited_root)
    if not targets:
        logger.info("No folders need MANUAL output.")
        return 0

    logger.info("Loading object-detection session for crop bounds: %s", config.REMBG_MODEL)
    session = create_session(config.REMBG_MODEL)
    manual_root.mkdir(parents=True, exist_ok=True)
    results: list[CropResult] = []

    for folder in targets:
        images = list_images(folder)
        if not images:
            logger.info("No images found in %s; skipping.", folder.name)
            continue

        manual_sub = manual_root / folder.name
        manual_sub.mkdir(parents=True, exist_ok=True)
        logger.info("Cropping %d images from %s into %s", len(images), folder.name, manual_sub)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {}
            for src in images:
                dst = manual_sub / f"{src.stem}.jpg"
                if dst.exists() and not force:
                    logger.info("Skipping existing MANUAL file %s/%s", folder.name, dst.name)
                    continue
                futures[executor.submit(crop_image, src, dst, session)] = (src, dst)

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Cropping {folder.name}",
            ):
                result = future.result()
                results.append(result)
                if result.status == "cropped":
                    logger.info("OK   %s -> %s", result.source.name, result.output.name)
                else:
                    logger.error("FAIL %s | %s", result.source.name, result.error)

    cropped = sum(1 for result in results if result.status == "cropped")
    failed = sum(1 for result in results if result.status == "failed")
    logger.info("Manual crop summary: %d cropped, %d failed", cropped, failed)
    logger.info("Raw Images was left untouched.")
    return 0 if failed == 0 else 2


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Crop raw folders into MANUAL when they are missing from Edited Images."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Raw Images"),
        help="Raw Images root folder.",
    )
    parser.add_argument(
        "--edited",
        type=Path,
        default=Path("Edited Images"),
        help="Edited Images root folder.",
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("MANUAL"),
        help="MANUAL output root folder.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config.DEFAULT_WORKERS,
        help=f"Number of worker threads (default: {config.DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild MANUAL files even if they already exist.",
    )
    return parser.parse_args(argv)


def main() -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:])
    logger.info("=" * 70)
    logger.info("MANUAL CROP PIPELINE")
    logger.info("=" * 70)
    logger.info("Raw Images   : %s", args.input)
    logger.info("Edited Images: %s", args.edited)
    logger.info("MANUAL       : %s", args.manual)
    logger.info("Workers      : %s", args.workers)
    logger.info("Force        : %s", args.force)
    logger.info("=" * 70)
    return process_manual_queue(
        raw_root=args.input,
        edited_root=args.edited,
        manual_root=args.manual,
        workers=args.workers,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
