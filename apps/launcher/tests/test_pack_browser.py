"""Tests for pack_browser module."""

import tempfile
from pathlib import Path

import pytest

from launcher.pack_browser import PackEntry, scan_packs


def test_scan_packs_empty_when_dir_missing() -> None:
    assert scan_packs("/nonexistent/path") == []


def test_scan_packs_finds_irunmap_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pack1 = Path(tmp) / "demo" / "demo.irunmap"
        pack1.parent.mkdir(parents=True, exist_ok=True)
        pack1.touch()
        pack2 = Path(tmp) / "test.irunmap"
        pack2.touch()

        entries = scan_packs(tmp)
        assert len(entries) == 2
        stems = {e.path.stem for e in entries}
        assert "demo" in stems
        assert "test" in stems


def test_scan_packs_sorted_newest_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old_pack = Path(tmp) / "old.irunmap"
        old_pack.touch()
        new_pack = Path(tmp) / "new.irunmap"
        new_pack.touch()

        entries = scan_packs(tmp)
        assert len(entries) >= 2
        assert entries[0].mtime >= entries[-1].mtime


def test_pack_entry_age_label() -> None:
    with tempfile.NamedTemporaryFile(suffix=".irunmap", delete=False) as f:
        p = Path(f.name)
    try:
        st = p.stat()
        entry = PackEntry(path=p, name=p.name, mtime=st.st_mtime)
        assert "ago" in entry.age_label or "just now" in entry.age_label
    finally:
        p.unlink(missing_ok=True)
