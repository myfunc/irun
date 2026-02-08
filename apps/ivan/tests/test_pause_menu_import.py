from __future__ import annotations


def test_pause_menu_ui_importable() -> None:
    # Import-only test to avoid requiring a Panda3D window in CI/headless test runs.
    from ivan.ui.pause_menu_ui import PauseMenuUI  # noqa: F401

