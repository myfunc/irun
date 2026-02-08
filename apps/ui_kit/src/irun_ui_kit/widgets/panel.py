from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme


@dataclass
class Panel:
    node: DirectFrame
    w: float
    h: float

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str | None = None,
        header: bool = True,
    ) -> "Panel":
        """
        Build a panel container at global (x, y) in aspect2d, with local child coordinates.

        Child coordinate system:
        - parented to returned `node`
        - local origin at (0, 0) bottom-left
        - local extents (0..w, 0..h)
        """

        # Shadow goes behind the panel for a retro "heavy" layered look.
        shadow = DirectFrame(
            parent=parent,
            frameColor=theme.shadow,
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
            pos=(x + theme.shadow_off_x, 0, y + theme.shadow_off_y),
        )
        # Ensure the shadow never intercepts mouse events.
        shadow["state"] = DGG.DISABLED

        out = DirectFrame(
            parent=parent,
            frameColor=theme.outline,
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
            pos=(x, 0, y),
        )
        inner = DirectFrame(
            parent=out,
            frameColor=theme.panel,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
            relief=DGG.FLAT,
        )

        if header:
            DirectFrame(
                parent=inner,
                frameColor=theme.header,
                frameSize=(theme.outline_w, w - theme.outline_w, h - theme.outline_w - theme.header_h, h - theme.outline_w),
                relief=DGG.FLAT,
            )
            if title:
                DirectLabel(
                    parent=inner,
                    text=title,
                    text_scale=theme.title_scale,
                    text_align=TextNode.ALeft,
                    text_fg=theme.ink,
                    frameColor=(0, 0, 0, 0),
                    pos=(theme.outline_w + theme.pad, 0, h - theme.outline_w - (theme.header_h * 0.70)),
                )

        return Panel(node=inner, w=w, h=h)
