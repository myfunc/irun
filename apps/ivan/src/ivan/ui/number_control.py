from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectLabel, DirectSlider
from panda3d.core import TextNode


class NumberControl:
    def __init__(
        self,
        parent,
        name: str,
        x: float,
        y: float,
        value: float,
        minimum: float,
        maximum: float,
        on_change,
    ) -> None:
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._on_change = on_change

        self.label = DirectLabel(
            parent=parent,
            text=name,
            text_scale=0.042,
            text_align=TextNode.ALeft,
            text_fg=(0.93, 0.93, 0.93, 1),
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
        )
        self.slider = DirectSlider(
            parent=parent,
            range=(minimum, maximum),
            value=value,
            pageSize=max(0.001, (maximum - minimum) / 150.0),
            scale=0.19,
            pos=(x + 0.32, 0, y),
            frameColor=(0.16, 0.16, 0.16, 0.95),
            thumb_frameColor=(0.82, 0.82, 0.82, 1.0),
            thumb_relief=DGG.FLAT,
            command=self._from_slider,
        )
        self.entry = DirectEntry(
            parent=parent,
            initialText=f"{value:.3f}",
            numLines=1,
            focus=0,
            scale=0.045,
            width=6,
            text_align=TextNode.ACenter,
            text_fg=(0.08, 0.08, 0.08, 1),
            frameColor=(0.9, 0.9, 0.9, 1),
            relief=DGG.FLAT,
            pos=(x + 0.62, 0, y - 0.02),
            command=self._from_entry,
            suppressMouse=False,
        )

    def set_value(self, value: float) -> None:
        clamped = max(self._minimum, min(self._maximum, value))
        self.slider["value"] = clamped
        self.entry.enterText(f"{clamped:.3f}")
        self._on_change(clamped)

    def _from_slider(self) -> None:
        value = float(self.slider["value"])
        self.entry.enterText(f"{value:.3f}")
        self._on_change(value)

    def _from_entry(self, text: str) -> None:
        try:
            value = float(text)
        except ValueError:
            self.entry.enterText(f"{float(self.slider['value']):.3f}")
            return
        self.set_value(value)

