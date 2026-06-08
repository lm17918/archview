"""Cheap filesystem change detection and a push broker for live updates."""

from __future__ import annotations

import os
import threading
from pathlib import Path

WATCH_EXTS = (".py", ".sh", ".yaml", ".yml", ".json")
SKIP_DIRS = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}


def tree_signature(project_dir: Path, ignore_file: Path | None = None) -> int:
    """Order-independent hash of (path, mtime) for all watched files.

    Changes value when any watched file is added, removed, or edited. Just
    stat calls — cheap enough to poll several times a second on large trees.
    """
    sig = 0
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(WATCH_EXTS):
                p = os.path.join(root, f)
                try:
                    sig ^= hash((p, os.stat(p).st_mtime_ns))
                except OSError:
                    pass
    if ignore_file and Path(ignore_file).exists():
        sig ^= hash(("ignore", os.stat(ignore_file).st_mtime_ns))
    return sig


class LiveBroker:
    """Version counter that SSE clients block on until the graph changes."""

    def __init__(self):
        self._cond = threading.Condition()
        self._version = 0

    def bump(self) -> None:
        with self._cond:
            self._version += 1
            self._cond.notify_all()

    def wait(self, last_version: int, timeout: float) -> int:
        with self._cond:
            if self._version == last_version:
                self._cond.wait(timeout)
            return self._version
