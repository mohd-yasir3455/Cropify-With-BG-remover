"""Delete duplicate image files like ``IMG_123(1).jpg`` when ``IMG_123.jpg`` exists.

This only checks files inside the MANUAL tree. A suffixed file is deleted only
when the base filename with the same extension exists in the same folder.
"""
from __future__ import annotations

import re
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)\((?P<index>\d+)\)$")


def main() -> int:
    root = Path(__file__).resolve().parent
    deleted = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        match = SUFFIX_PATTERN.match(path.stem)
        if not match:
            continue

        original = path.with_name(f"{match.group('base')}{path.suffix}")
        if original.exists():
            path.unlink()
            deleted += 1
            print(f"deleted: {path.relative_to(root)}")

    print(f"Deleted {deleted} duplicate file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
