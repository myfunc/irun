"""Scan a directory tree for .irunmap pack files and return them sorted by modification time."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PackEntry:
    """One discovered .irunmap pack file."""

    path: Path
    name: str
    mtime: float  # seconds since epoch

    @property
    def age_label(self) -> str:
        """Human-readable 'time ago' string."""
        delta = time.time() - self.mtime
        if delta < 60:
            return "just now"
        if delta < 3600:
            mins = int(delta // 60)
            return f"{mins} min ago"
        if delta < 86400:
            hrs = int(delta // 3600)
            return f"{hrs}h ago"
        days = int(delta // 86400)
        if days == 1:
            return "yesterday"
        return f"{days}d ago"


def scan_packs(maps_dir: str) -> list[PackEntry]:
    """Recursively find *.irunmap files under *maps_dir*, newest first."""
    root = Path(maps_dir)
    if not root.is_dir():
        return []
    entries: list[PackEntry] = []
    for p in root.rglob("*.irunmap"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        rel = p.relative_to(root)
        entries.append(PackEntry(path=p, name=str(rel), mtime=st.st_mtime))
    entries.sort(key=lambda e: e.mtime, reverse=True)
    return entries
