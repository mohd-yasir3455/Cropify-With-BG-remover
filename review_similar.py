"""Move extra similar images from 7-8 image folders into a REVIEW folder.

For each immediate product folder inside a chosen root folder:
  - if it contains 7 or 8 supported images
  - compute visual similarity between images
  - keep the 6 most distinct images
  - move the most redundant extras into <root>/REVIEW/<folder>

Original files are never deleted.
"""
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from image_io import open_image
from utils import list_images, list_product_folders


@dataclass(slots=True)
class FolderMoveResult:
    """Summary of one folder processed for similarity review."""

    folder: str
    total: int
    moved: list[str]


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Move extra similar images from 7-8 image folders into REVIEW."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Edited Images"),
        help="Root folder to scan, e.g. Edited Images or Raw Images.",
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=None,
        help="Optional explicit REVIEW folder path.",
    )
    return parser.parse_args(argv)


def _load_signature(path: Path, size: int = 16) -> np.ndarray:
    """Create a compact grayscale signature for visual comparison."""
    with open_image(path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((512, 512))
        square = ImageOps.fit(img, (size, size), method=Image.LANCZOS)
        arr = np.asarray(square.convert("L"), dtype=np.float32) / 255.0
    return arr


def _pairwise_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Return a simple visual distance between two signatures."""
    return float(np.mean(np.abs(a - b)))


def _choose_files_to_move(images: list[Path], keep_count: int = 6) -> list[Path]:
    """Return the most redundant files to move out of the folder.

    Greedy rule:
      - start with the pair of most different images
      - repeatedly keep the image farthest from the current kept set
      - everything else is considered extra/redundant
    """
    if len(images) <= keep_count:
        return []

    signatures = {path: _load_signature(path) for path in images}
    distances: dict[tuple[Path, Path], float] = {}

    def get_distance(left: Path, right: Path) -> float:
        key = tuple(sorted((left, right), key=lambda item: str(item)))
        if key not in distances:
            distances[key] = _pairwise_distance(signatures[left], signatures[right])
        return distances[key]

    # Seed with the most different pair so the kept set spans the folder variety.
    best_pair: tuple[Path, Path] | None = None
    best_distance = -1.0
    for index, left in enumerate(images):
        for right in images[index + 1 :]:
            distance = get_distance(left, right)
            if distance > best_distance:
                best_distance = distance
                best_pair = (left, right)

    kept: list[Path]
    if best_pair is None:
        kept = [images[0]]
    else:
        kept = [best_pair[0], best_pair[1]]

    remaining = [image for image in images if image not in kept]
    while len(kept) < keep_count and remaining:
        next_image = max(
            remaining,
            key=lambda image: min(get_distance(image, kept_image) for kept_image in kept),
        )
        kept.append(next_image)
        remaining.remove(next_image)

    return [image for image in images if image not in kept]


def move_similar_extras(input_root: Path, review_root: Path) -> list[FolderMoveResult]:
    """Move extra similar images from 7-8 image folders into REVIEW."""
    results: list[FolderMoveResult] = []
    review_root.mkdir(parents=True, exist_ok=True)

    for folder in list_product_folders(input_root):
        if folder.resolve() == review_root.resolve():
            continue

        images = list_images(folder)
        if len(images) not in (7, 8):
            continue

        to_move = _choose_files_to_move(images, keep_count=6)
        if not to_move:
            continue

        target_folder = review_root / folder.name
        target_folder.mkdir(parents=True, exist_ok=True)
        moved_names: list[str] = []
        for src in to_move:
            dst = target_folder / src.name
            suffix = 1
            while dst.exists():
                dst = target_folder / f"{src.stem}_{suffix}{src.suffix}"
                suffix += 1
            shutil.move(str(src), str(dst))
            moved_names.append(dst.name)

        results.append(FolderMoveResult(folder=folder.name, total=len(images), moved=moved_names))

    return results


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_root = args.input.expanduser().resolve()
    if not input_root.is_dir():
        raise SystemExit(f"Input folder does not exist: {input_root}")

    review_root = (
        args.review.expanduser().resolve()
        if args.review is not None
        else input_root / "REVIEW"
    )
    results = move_similar_extras(input_root, review_root)

    if not results:
        print("No 7-8 image folders needed review moves.")
        return 0

    moved_total = sum(len(item.moved) for item in results)
    print(f"Moved {moved_total} image(s) across {len(results)} folder(s) into {review_root}")
    for item in results:
        print(f"{item.folder}: moved {', '.join(item.moved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
