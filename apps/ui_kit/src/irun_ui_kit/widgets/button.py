from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


def _mul(c: Color, m: float) -> Color:
    r, g, b, a = c
    return (max(0.0, min(1.0, r * m)), max(0.0, min(1.0, g * m)), max(0.0, min(1.0, b * m)), a)


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
        frame_color: Color | None = None,
        on_click,
        text_fg: Color | None = None,
        disabled: bool = False,
    ) -> "Button":
        fc = frame_color or theme.panel2
        # DirectGUI supports per-state colors: (normal, pressed, hover, disabled).
        frame_colors = (
            fc,
            _mul(fc, 0.82),  # pressed: darken
            _mul(fc, 1.08),  # hover: subtle lift
            _mul(fc, 0.60),  # disabled
        )
        tfg = text_fg or theme.text
        b = DirectButton(
            parent=parent,
            text=(label, label, label, label),
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            # Baseline tweak: keep text vertically inside the button.
            text_pos=(-w / 2 + (theme.pad * 0.70), -theme.label_scale * 0.35),
            text_fg=tfg,
            frameColor=frame_colors,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=on_click,
            pressEffect=0,
        )
        if disabled:
            b["state"] = DGG.DISABLED
            b["text_fg"] = theme.text_muted
        return Button(node=b)
