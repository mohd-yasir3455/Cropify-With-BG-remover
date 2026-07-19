"""Central configuration for the batch product-image processor.

Every tunable value lives here so behaviour can be adjusted without touching the
processing logic. Change a value, re-run the program -- no code edits required.

The comment beside each value explains what it controls and its safe range.
"""
from __future__ import annotations

import os as _os

# --------------------------------------------------------------------------- #
# Supported input formats                                                      #
# --------------------------------------------------------------------------- #
# Any file whose extension is NOT in this set is ignored (never processed,
# never counted). Extensions are matched case-insensitively.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif"}
)

# --------------------------------------------------------------------------- #
# Background removal (rembg)                                                    #
# --------------------------------------------------------------------------- #
# Model choices for CPU:
#   "u2net"             -> balanced quality/speed (default, recommended)
#   "u2netp"            -> smaller/faster, slightly lower quality
#   "isnet-general-use" -> higher quality, noticeably slower on CPU
# The chosen model is downloaded automatically on first use (needs internet
# once) and then cached in the user's home folder for every later run.
REMBG_MODEL: str = "u2net"

# Alpha matting refines edges (hair/fuzzy outlines) but is much slower on CPU.
# Leave False for product photography; flip to True only if edges look rough.
ALPHA_MATTING: bool = False

# When cropping, a pixel counts as "object" only if its alpha exceeds this
# (0-255). A small threshold trims faint semi-transparent halos so the crop
# hugs the real object rather than a ghost outline.
ALPHA_THRESHOLD: int = 10

# --------------------------------------------------------------------------- #
# Crop / white-space padding                                                   #
# --------------------------------------------------------------------------- #
# White space kept around the object on EACH side, as a fraction of the
# object's size. 0.07 == 7 %, which keeps the crop clean without feeling tight.
PADDING_RATIO: float = 0.07

# Never pad fewer than this many pixels on a side (protects very small subjects
# where 8 % would round down to almost nothing).
MIN_PADDING_PX: int = 8

# Crop-only mode treats near-white pixels as background. Increase this if white
# margins remain; decrease it if light-colored products are cropped too tightly.
CROP_WHITE_THRESHOLD: int = 245

# --------------------------------------------------------------------------- #
# Output                                                                        #
# --------------------------------------------------------------------------- #
OUTPUT_FORMAT: str = "JPEG"          # Pillow format name
OUTPUT_EXTENSION: str = ".jpg"       # extension written to disk
JPEG_QUALITY: int = 90               # 1-95; 90 per spec

# Optional hard cap on the largest side of an INPUT image, in pixels, to bound
# memory on unusually large photos. None keeps the original resolution
# (recommended, per spec). Set e.g. 4000 only if you hit memory limits.
MAX_INPUT_DIMENSION: int | None = None

# --------------------------------------------------------------------------- #
# Output filename cleaning  (rule: "photoroom" / "copy")                        #
# --------------------------------------------------------------------------- #
# Case-insensitive substrings removed from OUTPUT filenames only (originals are
# never touched). After removal, separators (space, _ , -) left dangling at the
# start/end are trimmed and any doubled separators are collapsed.
RENAME_STRIP_TOKENS: tuple[str, ...] = ("photoroom", "copy")

# --------------------------------------------------------------------------- #
# Folder image-count rules                                                      #
# --------------------------------------------------------------------------- #
#   count == 0                         -> empty, listed in report, not edited
#   1 .. (REVIEW_MIN - 1)              -> processed normally, no flag
#   REVIEW_MIN .. REVIEW_MAX  (7-8)    -> processed AND flagged "trim to 6"
#   count >= SKIP_MIN         (9+)     -> SKIPPED (not edited), marked "discard"
REVIEW_MIN: int = 7
REVIEW_MAX: int = 8
SKIP_MIN: int = 9          # "more than 8" -> skip the folder
TARGET_KEEP: int = 6       # how many images the user wants to keep manually

# When True, every non-empty folder is processed regardless of image count.
PROCESS_ALL_FOLDERS: bool = False

# List empty / skipped folders in the Excel report too (with a comment) so the
# sheet is a complete control panel. Set False to omit empty folders.
LIST_EMPTY_FOLDERS: bool = True

# --------------------------------------------------------------------------- #
# Performance                                                                   #
# --------------------------------------------------------------------------- #
# Worker threads used to process images. A single rembg model session is shared
# across them (thread-safe), so threads mainly overlap decoding, cropping,
# JPEG encoding and disk I/O with inference. On a low-core laptop, 2-4 is the
# sweet spot; more threads mostly just use more RAM.
DEFAULT_WORKERS: int = max(1, min(4, (_os.cpu_count() or 2)))

# --------------------------------------------------------------------------- #
# Report / state / log filenames  (created inside the OUTPUT folder)           #
# --------------------------------------------------------------------------- #
REPORT_FILENAME: str = "processing_report.xlsx"
STATE_FILENAME: str = "processing_state.json"
LOG_FILENAME: str = "processing.log"

# Save the Excel report after this many folders (1 = after every folder, the
# safest for crash recovery). Raise it for very large runs to reduce writes.
EXCEL_SAVE_EVERY: int = 1

# --------------------------------------------------------------------------- #
# Excel report layout                                                          #
# --------------------------------------------------------------------------- #
EXCEL_HEADERS: tuple[str, str, str] = ("Folder Name", "No. of Pics", "Any Comment")
EXCEL_FONT: str = "Arial"            # professional font throughout

# --------------------------------------------------------------------------- #
# Comment templates for the "Any Comment" column                               #
# --------------------------------------------------------------------------- #
COMMENT_NORMAL: str = ""             # 1..6 images: nothing to flag
COMMENT_REVIEW: str = (
    "{count} images \u2013 trim to {keep} "
    "(remove extras/duplicates; keep front & back angles)"
)
COMMENT_SKIP: str = (
    "Discard \u2013 {count} images (more than {max_ok}, review manually)"
)
COMMENT_EMPTY: str = "Empty \u2013 no valid image files"
COMMENT_FAILED: str = "Processing failed: {error}"
COMMENT_PARTIAL: str = "{done}/{total} processed \u2013 {failed} failed (see log)"
