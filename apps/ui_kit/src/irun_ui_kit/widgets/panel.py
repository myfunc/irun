from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import NodePath, TextNode

from irun_ui_kit.theme import Theme


@dataclass
class Panel:
    node: DirectFrame
    content: NodePath
    w: float
    h: float
    title: DirectLabel | None = None

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
        - parented to returned `content`
        - local origin at (0, 0) bottom-left
        - local extents (0..w, 0..h)
        """

        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
            pos=(x, 0, y),
        )

        # Shadow goes behind the panel for a retro "heavy" layered look.
        shadow = DirectFrame(
            parent=root,
            frameColor=theme.shadow,
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
            pos=(theme.shadow_off_x, 0, theme.shadow_off_y),
        )
        # Ensure the shadow never intercepts mouse events.
        shadow["state"] = DGG.DISABLED

        outline = DirectFrame(
            parent=root,
            frameColor=theme.outline,
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
        )

        inner = DirectFrame(
            parent=root,
            frameColor=theme.panel,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
            relief=DGG.FLAT,
        )

        title_lbl: DirectLabel | None = None
        if header:
            DirectFrame(
                parent=root,
                frameColor=theme.panel2,
                frameSize=(theme.outline_w, w - theme.outline_w, h - theme.outline_w - theme.header_h, h - theme.outline_w),
                relief=DGG.FLAT,
            )
            # Thin accent line at the very top (avoid filling the whole outline with accent).
            DirectFrame(
                parent=root,
                frameColor=theme.header,
                frameSize=(theme.outline_w, w - theme.outline_w, h - theme.outline_w - theme.accent_h, h - theme.outline_w),
                relief=DGG.FLAT,
            )
            if title:
                title_lbl = DirectLabel(
                    parent=root,
                    text=str(title).upper(),
                    text_scale=theme.title_scale,
                    text_align=TextNode.ALeft,
                    text_fg=theme.text,
                    frameColor=(0, 0, 0, 0),
                    pos=(theme.outline_w + theme.pad, 0, h - theme.outline_w - (theme.header_h * 0.70)),
                )

        content = root.attachNewNode("ui-kit-panel-content")
        return Panel(node=root, content=content, w=w, h=h, title=title_lbl)
