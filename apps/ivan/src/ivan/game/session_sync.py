"""Session-level coordination: pointer lock, menu state for editor flow."""

from __future__ import annotations

from typing import Any


def should_restore_pointer_lock_after_picker(host: Any) -> bool:
    """
    True if pointer lock should be restored after closing the game mode picker.
    Used when editor picker closes: restore lock only when in game and no other menus open.
    """
    return host._mode == "game" and not (
        host._pause_menu_open
        or host._debug_menu_open
        or host._replay_browser_open
        or host._console_open
        or host._feel_capture_open
    )
