from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectEntry
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class TextInput:
    # We keep both: a frame button (for consistent sizing) and the entry itself.
    frame: DirectButton
    entry: DirectEntry

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        initial: str,
        on_submit,
        frame_color: Color = (0.92, 0.92, 0.92, 1.0),
        text_fg: Color = (0.08, 0.08, 0.10, 1.0),
    ) -> "TextInput":
        # Frame provides predictable box sizing and keeps the entry visually anchored.
        frame = DirectButton(
            parent=parent,
            text="",
            frameColor=frame_color,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=lambda: None,
        )
        entry = DirectEntry(
            parent=frame,
            initialText=initial,
            numLines=1,
            focus=0,
            width=22,  # approx; refined in runtime later
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=text_fg,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            pos=(-w / 2 + 0.03, 0, -theme.small_scale * 0.40),
            command=on_submit,
            suppressMouse=False,
        )
        return TextInput(frame=frame, entry=entry)

