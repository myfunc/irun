from __future__ import annotations


def test_feel_capture_ui_importable() -> None:
    # Import-only test to avoid requiring a Panda3D window in CI/headless test runs.
    from ivan.ui.feel_capture_ui import FeelCaptureUI  # noqa: F401
