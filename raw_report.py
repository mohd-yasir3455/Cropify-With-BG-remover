"""Generate an Excel report for the Raw Images folder.

The report mirrors the existing edited-images workbook format:
  - one row per immediate Raw Images subfolder
  - supported-image count in that folder
  - optional comment column (left blank for now)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import config
from excel_report import ExcelReport
from utils import list_images, list_product_folders


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build an Excel sheet for the Raw Images folder."
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("Raw Images"),
        help="Raw Images root folder.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output .xlsx path.",
    )
    return parser.parse_args(argv)


def build_raw_report(raw_root: Path, output_path: Path) -> int:
    """Write/update the Raw Images Excel report and return the folder count."""
    report = ExcelReport(output_path)
    folder_count = 0

    for folder in list_product_folders(raw_root):
        report.upsert(folder.name, len(list_images(folder)), "")
        folder_count += 1

    report.save()
    return folder_count


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    raw_root = args.raw.expanduser().resolve()
    if not raw_root.is_dir():
        raise SystemExit(f"Raw Images folder does not exist: {raw_root}")

    output_path = (
        args.output.expanduser().resolve()
        if args.output is not None
        else raw_root / config.REPORT_FILENAME
    )
    folder_count = build_raw_report(raw_root, output_path)
    print(f"Raw report updated: {output_path} ({folder_count} folders)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
