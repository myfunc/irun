from __future__ import annotations

from dataclasses import dataclass

from direct.showbase import ShowBaseGlobal


def aspect_ratio() -> float:
    """Best-effort current aspect ratio, with a stable fallback."""
    ratio = 16.0 / 9.0
    if getattr(ShowBaseGlobal, "base", None) is not None:
        try:
            ratio = float(ShowBaseGlobal.base.getAspectRatio())
        except Exception:
            pass
    return float(ratio)


# Shared screen-space anchors.
SCREEN_PAD_X = 0.06
PANEL_TOP = 0.95
PANEL_BOTTOM = -0.86
TOP_CHIP_Y = 0.90
INPUT_DEBUG_TOP_ANCHOR = 0.84
DEBUG_HUD_Y = 0.72
STATUS_BAR_Y = -0.94
ERROR_CONSOLE_Y = -0.82


@dataclass(frozen=True)
class UILayers:
    """Render order for game UI roots (higher wins)."""

    HUD: int = 20
    OVERLAY: int = 30
    MENU: int = 40
    CONSOLE: int = 50
