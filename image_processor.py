"""Core single-image processing pipeline.

Steps per image:
    1. Load the original (EXIF-orientation respected; never modified on disk).
    2. Remove the background with rembg -> RGBA with transparency.
    3. Crop to the subject's bounding box and add proportional white-space
       padding, composited onto a pure-white (#FFFFFF) background.
    4. Save as JPEG (quality 90) at the object's native resolution -- no
       stretching, squashing or forced resizing.

The rembg model session is created once (see :func:`create_session`) and shared
across worker threads; onnxruntime's ``Run`` is thread-safe, so a single session
keeps memory low while still allowing parallelism.

:func:`process_image` never raises -- every failure is captured in the returned
:class:`ImageResult` so one bad image can never stop the batch.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

import config
from logger import get_logger

logger = get_logger()

# rembg is imported lazily so this module can be imported (and unit-tested)
# without rembg/onnxruntime installed. The callables are cached after first use.
_new_session: Any = None
_rembg_remove: Any = None


def create_session(model_name: str = config.REMBG_MODEL) -> Any:
    """Create a rembg inference session for ``model_name``.

    The model is downloaded automatically on first use (internet required once)
    and cached in the user's home directory thereafter.

    Args:
        model_name: rembg model name, e.g. ``"u2net"``.

    Returns:
        An opaque rembg session object to pass to :func:`process_image`.
    """
    global _new_session
    if _new_session is None:
        from rembg import new_session  # lazy import

        _new_session = new_session
    return _new_session(model_name)


def remove_background(image: Image.Image, session: Any) -> Image.Image:
    """Remove the background from ``image`` and return an RGBA image.

    Args:
        image: Source image (any mode).
        session: A session from :func:`create_session`.

    Returns:
        An ``RGBA`` image whose background pixels are transparent.
    """
    global _rembg_remove
    if _rembg_remove is None:
        from rembg import remove  # lazy import

        _rembg_remove = remove
    result = _rembg_remove(image, session=session, alpha_matting=config.ALPHA_MATTING)
    if result.mode != "RGBA":
        result = result.convert("RGBA")
    return result


@dataclass(slots=True)
class ImageResult:
    """Outcome of processing a single image."""

    source: Path
    output: Path | None
    status: str  # "processed" | "failed"
    elapsed_s: float = 0.0
    error: str = ""


def _load_image(path: Path) -> Image.Image:
    """Open ``path``, apply EXIF orientation, optionally cap its size."""
    img = Image.open(path)
    img.load()
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # pragma: no cover - orientation is best-effort
        pass

    if config.MAX_INPUT_DIMENSION:
        width, height = img.size
        longest = max(width, height)
        if longest > config.MAX_INPUT_DIMENSION:
            scale = config.MAX_INPUT_DIMENSION / longest
            img = img.resize(
                (round(width * scale), round(height * scale)), Image.LANCZOS
            )
    return img


def _matte_and_crop(rgba: Image.Image, original: Image.Image) -> Image.Image:
    """Crop to the subject and composite onto white with padding.

    Args:
        rgba: Background-removed RGBA image.
        original: The loaded original, used as a fallback if no subject is
            detected (so we never output a blank white frame).

    Returns:
        An ``RGB`` image on a pure-white background.
    """
    alpha = rgba.getchannel("A")
    # Threshold alpha so faint halos do not inflate the bounding box.
    mask = alpha.point(lambda a: 255 if a > config.ALPHA_THRESHOLD else 0)
    bbox = mask.getbbox()

    if bbox is None:
        logger.warning("No subject detected in image; keeping full frame on white.")
        base = original.convert("RGB")
        canvas = Image.new("RGB", base.size, (255, 255, 255))
        canvas.paste(base, (0, 0))
        return canvas

    left, upper, right, lower = bbox
    obj_w = right - left
    obj_h = lower - upper
    pad_x = max(config.MIN_PADDING_PX, round(obj_w * config.PADDING_RATIO))
    pad_y = max(config.MIN_PADDING_PX, round(obj_h * config.PADDING_RATIO))

    cropped = rgba.crop(bbox)  # RGBA subject at native resolution
    canvas = Image.new("RGB", (obj_w + 2 * pad_x, obj_h + 2 * pad_y), (255, 255, 255))
    # Paste using the subject's own alpha as the mask -> clean white edges.
    canvas.paste(cropped, (pad_x, pad_y), cropped)
    return canvas


def process_image(src: Path, dst: Path, session: Any) -> ImageResult:
    """Run the full pipeline for one image. Never raises.

    Args:
        src: Source image path (read-only; never modified).
        dst: Destination ``.jpg`` path (parent created; overwritten if present).
        session: rembg session from :func:`create_session`.

    Returns:
        An :class:`ImageResult` describing success or failure.
    """
    start = time.perf_counter()
    try:
        with _load_image(src) as original:
            rgba = remove_background(original, session)
            final = _matte_and_crop(rgba, original)
            dst.parent.mkdir(parents=True, exist_ok=True)
            final.save(dst, config.OUTPUT_FORMAT, quality=config.JPEG_QUALITY)
        return ImageResult(src, dst, "processed", time.perf_counter() - start)
    except Exception as exc:  # noqa: BLE001 - deliberately catch everything
        # Full traceback goes to the log file only (DEBUG); the orchestrator
        # logs a concise one-line error that also reaches the console.
        logger.debug("Traceback while processing %s", src, exc_info=True)
        return ImageResult(
            src,
            None,
            "failed",
            time.perf_counter() - start,
            error=f"{type(exc).__name__}: {exc}",
        )
