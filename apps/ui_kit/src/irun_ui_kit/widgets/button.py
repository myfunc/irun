from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class Button:
    node: DirectButton

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        frame_color: Color,
        on_click,
        text_fg: Color | None = None,
        disabled: bool = False,
    ) -> "Button":
        b = DirectButton(
            parent=parent,
            text=(label, label, label, label),
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            # Baseline tweak: keep text vertically inside the button.
            text_pos=(-w / 2 + 0.05, -theme.label_scale * 0.35),
            text_fg=text_fg or theme.text,
            frameColor=frame_color,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=on_click,
        )
        if disabled:
            b["state"] = DGG.DISABLED
            b["text_fg"] = theme.text_muted
        return Button(node=b)

