from __future__ import annotations

from dataclasses import dataclass

from direct.gui.DirectGui import DirectFrame


@dataclass(frozen=True)
class EditorLayoutStyle:
    left_width: float = 0.32
    right_width: float = 0.32
    pad: float = 0.02
    panel_bg_rgba: tuple[float, float, float, float] = (0.06, 0.07, 0.08, 0.72)
    panel_border_rgba: tuple[float, float, float, float] = (0.18, 0.20, 0.22, 0.95)


class EditorLayout:
    """Simple \"editor\" chrome: left/right translucent panels.

    This is intentionally minimal: real widgets will land later.
    """

    def __init__(self, *, aspect2d, style: EditorLayoutStyle | None = None) -> None:
        self._root = aspect2d
        self.style = style or EditorLayoutStyle()

        s = self.style
        # aspect2d is in [-1.333..1.333] x [-1..1] (approx). Panels are overlay UI.
        self.left = DirectFrame(
            parent=self._root,
            frameColor=s.panel_bg_rgba,
            frameSize=(-1.33, -1.33 + s.left_width, -0.98, 0.98),
            borderWidth=(0.003, 0.003),
            relief=1,
        )
        self.right = DirectFrame(
            parent=self._root,
            frameColor=s.panel_bg_rgba,
            frameSize=(1.33 - s.right_width, 1.33, -0.98, 0.98),
            borderWidth=(0.003, 0.003),
            relief=1,
        )

