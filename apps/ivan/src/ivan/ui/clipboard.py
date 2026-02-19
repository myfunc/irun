"""Cross-platform clipboard helpers. Windows primary target with graceful fallback."""

from __future__ import annotations

import sys


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to system clipboard.

    Returns (success, status_message). On Windows uses ctypes + user32/kernel32.
    On other platforms attempts pyperclip if available, else returns failure.
    """
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return True, "Nothing to copy."

    if sys.platform == "win32":
        return _copy_windows(text)
    return _copy_fallback(text)


def _copy_windows(text: str) -> tuple[bool, str]:
    """Windows: use ctypes with user32/kernel32. No extra dependencies."""
    try:
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        data = text.encode("utf-16-le") + b"\x00\x00"  # null terminator for wide string
        n = len(data)

        if user32.OpenClipboard(None) == 0:
            return False, "Clipboard: OpenClipboard failed."

        try:
            if user32.EmptyClipboard() == 0:
                return False, "Clipboard: EmptyClipboard failed."

            h = kernel32.GlobalAlloc(wintypes.UINT(GMEM_MOVEABLE), wintypes.SIZE_T(n))
            if h is None or h == 0:
                return False, "Clipboard: GlobalAlloc failed."

            ptr = kernel32.GlobalLock(wintypes.HANDLE(h))
            if ptr is None:
                kernel32.GlobalFree(wintypes.HANDLE(h))
                return False, "Clipboard: GlobalLock failed."

            try:
                ctypes.memmove(ptr, data, n)
            finally:
                kernel32.GlobalUnlock(wintypes.HANDLE(h))

            if user32.SetClipboardData(wintypes.UINT(CF_UNICODETEXT), wintypes.HANDLE(h)) is None:
                return False, "Clipboard: SetClipboardData failed."

            return True, "Copied to clipboard."
        finally:
            user32.CloseClipboard()
    except Exception as e:
        return False, f"Clipboard: {e!r}"


def _copy_fallback(text: str) -> tuple[bool, str]:
    """Non-Windows: try pyperclip if installed."""
    try:
        import pyperclip

        pyperclip.copy(text)
        return True, "Copied to clipboard."
    except ImportError:
        return False, "Clipboard unavailable (install pyperclip for non-Windows)."
    except Exception as e:
        return False, f"Clipboard: {e!r}"
