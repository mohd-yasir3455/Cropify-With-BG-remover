"""Generate an Excel report for the MANUAL folder.

The report mirrors the existing edited-images workbook format:
  - one row per immediate MANUAL subfolder
  - image count in that folder
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
        description="Build an Excel sheet for the MANUAL folder."
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("MANUAL"),
        help="MANUAL root folder.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output .xlsx path.",
    )
    return parser.parse_args(argv)


def build_manual_report(manual_root: Path, output_path: Path) -> int:
    """Write/update the MANUAL Excel report and return the folder count."""
    report = ExcelReport(output_path)
    folder_count = 0

    for folder in list_product_folders(manual_root):
        report.upsert(folder.name, len(list_images(folder)), "")
        folder_count += 1

    report.save()
    return folder_count


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    manual_root = args.manual.expanduser().resolve()
    if not manual_root.is_dir():
        raise SystemExit(f"MANUAL folder does not exist: {manual_root}")

    output_path = (
        args.output.expanduser().resolve()
        if args.output is not None
        else manual_root / config.REPORT_FILENAME
    )
    folder_count = build_manual_report(manual_root, output_path)
    print(f"Manual report updated: {output_path} ({folder_count} folders)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
