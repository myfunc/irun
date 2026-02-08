from __future__ import annotations

from dataclasses import dataclass

from direct.gui.DirectGui import DirectScrolledFrame
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import NodePath

from irun_ui_kit.theme import Theme


@dataclass
class Scrolled:
    """
    Thin wrapper around DirectScrolledFrame with themed colors and a stable API.

    Coordinate system:
    - The returned canvas is a normal NodePath. Callers are responsible for laying out children.
    - We keep canvasSize in a conventional bottom-up range (0..canvas_h).
    """

    frame: DirectScrolledFrame
    canvas: NodePath
    w: float
    h: float
    canvas_h: float

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        canvas_h: float,
    ) -> "Scrolled":
        out = DirectScrolledFrame(
            parent=parent,
            frameColor=theme.panel,
            frameSize=(0.0, w, 0.0, h),
            canvasSize=(0.0, w, 0.0, max(h, canvas_h)),
            relief=DGG.FLAT,
            autoHideScrollBars=False,
            manageScrollBars=True,
            verticalScroll_frameColor=theme.panel2,
            verticalScroll_thumb_frameColor=theme.outline,
            verticalScroll_incButton_frameColor=theme.panel2,
            verticalScroll_decButton_frameColor=theme.panel2,
            pos=(x, 0, y),
        )
        canvas = out.getCanvas()
        try:
            out.horizontalScroll.hide()
        except Exception:
            pass
        return Scrolled(frame=out, canvas=canvas, w=float(w), h=float(h), canvas_h=float(max(h, canvas_h)))

    def set_canvas_h(self, canvas_h: float) -> None:
        self.canvas_h = float(max(self.h, canvas_h))
        self.frame["canvasSize"] = (0.0, self.w, 0.0, self.canvas_h)

    def scroll_wheel(self, direction: int) -> None:
        d = 1 if int(direction) > 0 else -1
        try:
            bar = self.frame.verticalScroll
            cur = float(bar["value"])
            bar["value"] = max(0.0, min(1.0, cur - d * 0.020))
        except Exception:
            pass

    def destroy(self) -> None:
        try:
            self.frame.destroy()
        except Exception:
            pass

