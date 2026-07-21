"""Flatten MANUAL product folders by replacing contents with extracted ZIP data.

For each immediate subfolder inside ``MANUAL`` (for example ``#SEC-0005``),
this script finds ZIP files, extracts them into a temporary directory, moves
all extracted files into the product folder root, and deletes everything else
that was previously inside that folder.
"""

# python3 manual_extract.py --manual "MANUAL"
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile

from utils import list_product_folders


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract ZIP files inside MANUAL product folders and flatten them."
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("MANUAL"),
        help="MANUAL root folder.",
    )
    return parser.parse_args(argv)


def extract_and_flatten_folder(folder: Path) -> list[Path]:
    """Replace ``folder`` contents with files extracted from its ZIP archives."""
    zip_files = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".zip")
    if not zip_files:
        return []

    with tempfile.TemporaryDirectory(prefix=f"{folder.name}_", dir=folder.parent) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        extract_root = temp_dir / "extracted"
        extract_root.mkdir()

        for index, zip_path in enumerate(zip_files, start=1):
            target = extract_root / f"zip_{index}"
            target.mkdir()
            with ZipFile(zip_path) as archive:
                archive.extractall(target)

        extracted_files = [
            path for path in sorted(extract_root.rglob("*"))
            if path.is_file()
        ]
        if not extracted_files:
            raise ValueError(f"No files were extracted from ZIPs in {folder}")

        existing_entries = list(folder.iterdir())
        for entry in existing_entries:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

        moved_files: list[Path] = []
        for source in extracted_files:
            destination = folder / source.name
            destination = make_unique_path(destination)
            shutil.move(str(source), destination)
            moved_files.append(destination)

    return moved_files


def make_unique_path(path: Path) -> Path:
    """Return a unique destination path by adding ``_1``, ``_2`` if needed."""
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    manual_root = args.manual.expanduser().resolve()
    if not manual_root.is_dir():
        raise SystemExit(f"MANUAL folder does not exist: {manual_root}")

    changed = 0
    skipped = 0
    for folder in list_product_folders(manual_root):
        moved_files = extract_and_flatten_folder(folder)
        if moved_files:
            changed += 1
            print(f"{folder.name}: replaced contents with {len(moved_files)} extracted file(s)")
        else:
            skipped += 1
            print(f"{folder.name}: skipped (no ZIP found)")

    print(f"Finished: updated {changed} folder(s), skipped {skipped} folder(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
