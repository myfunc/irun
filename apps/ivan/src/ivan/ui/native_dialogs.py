from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DirectoryPickResult:
    ok: bool
    path: str | None
    error: str | None = None


def pick_directory(*, title: str) -> DirectoryPickResult:
    """
    Open a native directory picker.

    Uses tkinter (stdlib). If unavailable (headless env, missing Tk), returns an error.
    """

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        return DirectoryPickResult(ok=False, path=None, error=f"tkinter unavailable: {e}")

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        d = filedialog.askdirectory(title=title, mustexist=True)
        if not d:
            return DirectoryPickResult(ok=False, path=None, error="Canceled.")
        return DirectoryPickResult(ok=True, path=str(d), error=None)
    except Exception as e:
        return DirectoryPickResult(ok=False, path=None, error=str(e))
    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass

