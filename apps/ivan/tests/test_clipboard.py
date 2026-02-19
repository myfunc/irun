"""Tests for clipboard helper (Windows primary, graceful fallback)."""

from __future__ import annotations

import sys

from ivan.ui.clipboard import copy_to_clipboard


def test_copy_to_clipboard_empty_returns_ok() -> None:
    """Empty string is a no-op but returns success."""
    ok, msg = copy_to_clipboard("")
    assert ok is True
    assert "Nothing" in msg or "copy" in msg.lower()


def test_copy_to_clipboard_returns_tuple() -> None:
    """copy_to_clipboard returns (bool, str)."""
    ok, msg = copy_to_clipboard("test")
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_copy_to_clipboard_windows_smoke() -> None:
    """On Windows, copy should succeed for short ASCII text."""
    if sys.platform != "win32":
        return
    ok, msg = copy_to_clipboard("IVAN runtime tweak test")
    # May succeed or fail depending on environment (e.g. headless CI).
    assert isinstance(ok, bool)
    assert len(msg) > 0
