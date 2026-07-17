"""Logging configuration for the batch image processor.

A single named logger writes a detailed, timestamped log to ``processing.log``
(append mode) inside the output folder. The console handler only shows warnings
and errors so it never fights the tqdm progress bar.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "batch_image_processor"


def setup_logger(
    log_path: Path,
    *,
    console_level: int = logging.WARNING,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        log_path: Destination log file (opened in append mode). Parent folders
            are created if needed.
        console_level: Minimum level echoed to stderr (default WARNING).
        file_level: Minimum level written to the file (default DEBUG, so full
            tracebacks are captured for debugging without cluttering the console).

    Returns:
        The configured :class:`logging.Logger`. Safe to call more than once in
        the same process; handlers are reset so logs are not duplicated.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the shared application logger (configure via :func:`setup_logger`)."""
    return logging.getLogger(LOGGER_NAME)
