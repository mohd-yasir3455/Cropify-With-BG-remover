"""Resume-safe progress tracking, persisted as ``processing_state.json``.

The state records which source images have been processed and the outcome of
each folder, so an interrupted run can be resumed by re-running the same
command. It is flushed once per folder: product folders hold only a handful of
images, so at most the folder in flight is redone on resume, while writes stay
cheap even across thousands of images.

Writes are atomic (temp file + replace) so an interruption mid-write cannot
corrupt the state file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProcessingState:
    """Load, query and persist processing progress."""

    def __init__(self, path: Path) -> None:
        """Load existing state from ``path`` if present, else start empty."""
        self.path = path
        self._completed_images: set[str] = set()
        self._folders: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Read state from disk; on any error start fresh (originals are safe)."""
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._completed_images = set(data.get("completed_images", []))
            self._folders = dict(data.get("folders", {}))
        except (json.JSONDecodeError, OSError, ValueError):
            self._completed_images = set()
            self._folders = {}

    # -- image-level ------------------------------------------------------- #
    def is_image_done(self, key: str) -> bool:
        """Return True if the image identified by ``key`` was already processed."""
        return key in self._completed_images

    def mark_image_done(self, key: str) -> None:
        """Record that the image identified by ``key`` finished successfully."""
        self._completed_images.add(key)

    # -- folder-level ------------------------------------------------------ #
    def is_folder_done(self, folder: str) -> bool:
        """Return True if ``folder`` fully finished on a previous run."""
        return self._folders.get(folder, {}).get("status") == "done"

    def set_folder(self, folder: str, **info: Any) -> None:
        """Store status/metadata for ``folder`` (overwrites any previous entry)."""
        self._folders[folder] = info

    def get_folder(self, folder: str) -> dict[str, Any]:
        """Return the stored metadata dict for ``folder`` (empty if unknown)."""
        return self._folders.get(folder, {})

    # -- persistence ------------------------------------------------------- #
    def save(self) -> None:
        """Atomically write the current state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "completed_images": sorted(self._completed_images),
            "folders": self._folders,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
