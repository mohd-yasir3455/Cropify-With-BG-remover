"""Clean Raw Images by removing copied duplicates and moving extras to EXTRA.

Steps:
  1. Delete duplicate files like ``IMG_123(1).HEIC`` when ``IMG_123.HEIC``
     exists in the same folder.
  2. For folders with 7 or 8 supported images, keep the 6 most distinct images
     and move the most similar extras into ``<root>/EXTRA/<folder>``.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from review_similar import move_similar_extras


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)\((?P<index>\d+)\)$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Delete copied duplicates and move 7-8 folder extras into EXTRA."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Raw Images"),
        help="Root folder to clean.",
    )
    parser.add_argument(
        "--extra",
        type=Path,
        default=None,
        help="Optional explicit EXTRA folder path.",
    )
    return parser.parse_args(argv)


def delete_paren_duplicates(root: Path) -> list[Path]:
    """Delete files like ``name(1).ext`` when ``name.ext`` exists beside them."""
    deleted: list[Path] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        match = SUFFIX_PATTERN.match(path.stem)
        if not match:
            continue

        original = path.with_name(f"{match.group('base')}{path.suffix}")
        if original.exists():
            path.unlink()
            deleted.append(path)

    return deleted


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_root = args.input.expanduser().resolve()
    if not input_root.is_dir():
        raise SystemExit(f"Input folder does not exist: {input_root}")

    extra_root = (
        args.extra.expanduser().resolve()
        if args.extra is not None
        else input_root / "EXTRA"
    )

    deleted = delete_paren_duplicates(input_root)
    moved = move_similar_extras(input_root, extra_root)

    print(f"Deleted {len(deleted)} copied duplicate file(s).")
    for path in deleted:
        print(f"deleted: {path.relative_to(input_root)}")

    moved_total = sum(len(item.moved) for item in moved)
    print(f"Moved {moved_total} extra image(s) across {len(moved)} folder(s) into {extra_root}")
    for item in moved:
        print(f"{item.folder}: moved {', '.join(item.moved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
