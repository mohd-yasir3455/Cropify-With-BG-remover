"""Shared image-loading helpers, including HEIC/HEIF support."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

_HEIF_REGISTERED = False


def ensure_heif_support() -> None:
    """Register HEIC/HEIF support with Pillow when the plugin is installed."""
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return

    try:
        from pillow_heif import register_heif_opener
    except ImportError:
        _HEIF_REGISTERED = True
        return

    register_heif_opener()
    _HEIF_REGISTERED = True


def open_image(path: Path) -> Image.Image:
    """Open an image after registering optional HEIC/HEIF support."""
    ensure_heif_support()
    return Image.open(path)
