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
        slider_offset: float = 0.52,
        entry_offset: float = 0.80,
        normalized_slider: bool = False,
        normalized_entry: bool = False,
        slider_scale: float = 0.12,
        slider_frame_size: tuple[float, float, float, float] | None = None,
        slider_thumb_size: tuple[float, float, float, float] | None = None,
        entry_scale: float = 0.045,
        precision: int = 3,
    ) -> None:
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._on_change = on_change
        self._normalized_slider = bool(normalized_slider)
        self._normalized_entry = bool(normalized_entry)
        self._precision = int(max(0, precision))

        self.label = DirectLabel(
            parent=parent,
            text=name,
            text_scale=0.030,
            text_align=TextNode.ALeft,
            text_fg=(0.93, 0.93, 0.93, 1),
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
        )
        slider_range = (0.0, 100.0) if self._normalized_slider else (minimum, maximum)
        slider_value = self._to_slider_value(value)
        self.slider = DirectSlider(
            parent=parent,
            range=slider_range,
            value=slider_value,
            pageSize=max(0.001, (slider_range[1] - slider_range[0]) / 100.0),
            scale=slider_scale,
            pos=(x + slider_offset, 0, y),
            frameColor=(0.16, 0.16, 0.16, 0.95),
            thumb_frameColor=(0.82, 0.82, 0.82, 1.0),
            thumb_relief=DGG.RIDGE,
            command=self._from_slider,
        )
        if slider_frame_size is not None:
            self.slider["frameSize"] = slider_frame_size
        if slider_thumb_size is not None:
            self.slider["thumb_frameSize"] = slider_thumb_size
        self.entry = DirectEntry(
            parent=parent,
            initialText=f"{value:.3f}",
            numLines=1,
            focus=0,
            scale=entry_scale,
            width=6,
            text_align=TextNode.ACenter,
            text_fg=(0.08, 0.08, 0.08, 1),
            frameColor=(0.9, 0.9, 0.9, 1),
            relief=DGG.FLAT,
            pos=(x + entry_offset, 0, y - 0.02),
            command=self._from_entry,
            suppressMouse=False,
        )
        self.entry.enterText(self._display_text(value))

    def _fmt(self, value: float) -> str:
        return f"{value:.{self._precision}f}"

    def _display_text(self, value: float) -> str:
        if self._normalized_entry:
            return f"{self._to_slider_value(value):.1f}"
        return self._fmt(value)

    def _to_slider_value(self, value: float) -> float:
        clamped = max(self._minimum, min(self._maximum, value))
        if not self._normalized_slider:
            return clamped
        span = max(1e-12, self._maximum - self._minimum)
        return ((clamped - self._minimum) / span) * 100.0

    def _from_slider_value(self, slider_value: float) -> float:
        if not self._normalized_slider:
            return max(self._minimum, min(self._maximum, slider_value))
        span = max(1e-12, self._maximum - self._minimum)
        value = self._minimum + (max(0.0, min(100.0, slider_value)) / 100.0) * span
        return max(self._minimum, min(self._maximum, value))

    def set_value(self, value: float) -> None:
        clamped = max(self._minimum, min(self._maximum, value))
        self.slider["value"] = self._to_slider_value(clamped)
        self.entry.enterText(self._display_text(clamped))
        self._on_change(clamped)

    def _from_slider(self) -> None:
        value = self._from_slider_value(float(self.slider["value"]))
        self.entry.enterText(self._display_text(value))
        self._on_change(value)

    def _from_entry(self, text: str) -> None:
        try:
            value = float(text)
        except ValueError:
            current = self._from_slider_value(float(self.slider["value"]))
            self.entry.enterText(self._display_text(current))
            return
        if self._normalized_entry:
            value = self._from_slider_value(value)
        self.set_value(value)
