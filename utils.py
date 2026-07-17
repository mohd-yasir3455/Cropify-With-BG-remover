"""Filesystem scanning and output-filename helpers.

Pure, side-effect-free helpers used by the orchestrator: locating product
folders, listing valid images, and computing clean, collision-free output
filenames (including the "photoroom"/"copy" renaming rule).
"""
from __future__ import annotations

import re
from pathlib import Path

import config

# Junk/system files that are not real images and should always be ignored.
_JUNK_NAMES: frozenset[str] = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})

# Characters treated as separators when tidying filenames.
_SEP_CLASS = r"[\s_\-]"


def is_hidden(path: Path) -> bool:
    """Return True for hidden or system files (dot-files and known junk)."""
    name = path.name
    return name.startswith(".") or name.lower() in _JUNK_NAMES


def is_supported_image(path: Path) -> bool:
    """Return True if ``path`` is a regular file with a supported extension."""
    return path.is_file() and path.suffix.lower() in config.SUPPORTED_EXTENSIONS


def list_product_folders(root: Path) -> list[Path]:
    """Return the immediate, non-hidden subdirectories of ``root`` (sorted)."""
    return sorted(
        (p for p in root.iterdir() if p.is_dir() and not is_hidden(p)),
        key=lambda p: p.name.lower(),
    )


def list_images(folder: Path) -> list[Path]:
    """Return valid, non-hidden image files directly inside ``folder`` (sorted)."""
    return sorted(
        (
            p
            for p in folder.iterdir()
            if is_supported_image(p) and not is_hidden(p)
        ),
        key=lambda p: p.name.lower(),
    )


def needs_rename(stem: str, tokens: tuple[str, ...] = config.RENAME_STRIP_TOKENS) -> bool:
    """Return True if ``stem`` contains any strip-token (case-insensitive)."""
    low = stem.lower()
    return any(token.lower() in low for token in tokens)


def clean_stem(stem: str, tokens: tuple[str, ...] = config.RENAME_STRIP_TOKENS) -> str:
    """Remove strip-tokens from a filename stem and tidy the result.

    The token is removed wherever it appears (case-insensitive). Separator runs
    created by the removal (``__``, ``--``, double spaces) are collapsed to a
    single separator, and separators are trimmed from both ends. Single internal
    separators the user already had are preserved.

    Args:
        stem: Filename without extension.
        tokens: Substrings to remove.

    Returns:
        The cleaned stem (may be empty if nothing meaningful remains).
    """
    result = stem
    for token in tokens:
        result = re.sub(re.escape(token), "", result, flags=re.IGNORECASE)
    # Collapse a run of separators to its first character (fixes gaps left by
    # removal) while leaving lone separators untouched.
    result = re.sub(rf"({_SEP_CLASS}){_SEP_CLASS}+", r"\1", result)
    # Trim separators/whitespace from both ends.
    result = result.strip(" \t_-")
    return result


def _safe_fragment(text: str) -> str:
    """Make an arbitrary string safe for use inside a filename (fallback only)."""
    cleaned = re.sub(r"[^\w.\-]+", "_", text).strip("_")
    return cleaned or "image"


def build_output_names(images: list[Path], folder_code: str) -> dict[Path, str]:
    """Map each source image to a unique output filename ending in ``.jpg``.

    Rules applied:
      * Files without a strip-token keep their original base name.
      * Files containing "photoroom"/"copy" have the token removed and
        separators tidied.
      * Names are made unique within the folder by appending ``_1``, ``_2`` ...
        Non-renamed originals are assigned first so they keep their clean name
        and any colliding "copy" variant is the one that gets a suffix.

    Args:
        images: Source image paths (any order).
        folder_code: The product folder name, used only for fallback names.

    Returns:
        Dict mapping ``source Path`` -> ``output filename`` (str, with ``.jpg``).
    """
    taken: set[str] = set()
    mapping: dict[Path, str] = {}

    keep = [p for p in images if not needs_rename(p.stem)]
    rename = [p for p in images if needs_rename(p.stem)]

    for src in keep:
        mapping[src] = _assign_unique(src.stem, taken)

    for index, src in enumerate(rename, start=1):
        stem = clean_stem(src.stem) or f"{_safe_fragment(folder_code)}_{index}"
        mapping[src] = _assign_unique(stem, taken)

    return mapping


def _assign_unique(stem: str, taken: set[str]) -> str:
    """Return ``stem + .jpg`` made unique against ``taken`` (updates ``taken``)."""
    candidate = f"{stem}{config.OUTPUT_EXTENSION}"
    suffix = 1
    while candidate.lower() in taken:
        candidate = f"{stem}_{suffix}{config.OUTPUT_EXTENSION}"
        suffix += 1
    taken.add(candidate.lower())
    return candidate
