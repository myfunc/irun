from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from direct.showbase import ShowBaseGlobal
from panda3d.core import NodePath

from irun_ui_kit.layout import Rect
from irun_ui_kit.theme import Theme


@dataclass
class Workspace:
    """
    Full-screen UI workspace container with a stable local coordinate space.

    Coordinate system:
    - Children should be parented under `content`.
    - Local origin is (0, 0) bottom-left.
    - Local extents are (0..w, 0..h), where:
      - h is always 2.0 (aspect2d vertical range)
      - w is 2 * aspect_ratio

    This is useful for editor-like apps where the UI should adapt to window aspect and
    act as a "dock area" for panels/toolbars.
    """

    root: DirectFrame
    content: NodePath
    w: float
    h: float
    theme: Theme

    @staticmethod
    def build(*, aspect2d, theme: Theme, fill: bool = True, base=None) -> "Workspace":
        # aspect2d is in [-aspect..+aspect] x [-1..+1].
        # We create a local 0..w, 0..h space by positioning at (-aspect, -1).
        if base is None:
            base = getattr(ShowBaseGlobal, "base", None)
        aspect = 1.3333333
        if base is not None:
            try:
                aspect = float(base.getAspectRatio())
            except Exception:
                aspect = 1.3333333
        w = 2.0 * float(max(0.5, aspect))
        h = 2.0

        root = DirectFrame(
            parent=aspect2d,
            frameColor=(theme.bg if fill else (0, 0, 0, 0)),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(-float(w) / 2.0, 0.0, -1.0),
        )
        content = root.attachNewNode("ui-kit-workspace-content")
        return Workspace(root=root, content=content, w=float(w), h=float(h), theme=theme)

    def bounds(self) -> Rect:
        return Rect(x0=0.0, y0=0.0, x1=float(self.w), y1=float(self.h))

    def relayout(self, *, aspect_ratio: float) -> None:
        aspect_ratio = max(0.5, float(aspect_ratio))
        self.w = 2.0 * aspect_ratio
        self.h = 2.0
        try:
            self.root.setPos(-self.w / 2.0, 0.0, -1.0)
            self.root["frameSize"] = (0.0, float(self.w), 0.0, float(self.h))
        except Exception:
            pass
