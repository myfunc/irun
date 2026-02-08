from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel, DirectSlider
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.text_input import TextInput


@dataclass
class NumericControl:
    """
    Label + slider + entry for tuning numeric values.

    This is a library-grade replacement for game-side "number control" widgets:
    callers provide min/max/value and an on_change callback.
    """

    root: DirectFrame
    label: DirectLabel
    slider: DirectSlider
    entry: TextInput
    minimum: float
    maximum: float
    normalized_slider: bool
    normalized_entry: bool
    precision: int
    on_change: callable

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        label: str,
        value: float,
        minimum: float,
        maximum: float,
        on_change,
        normalized_slider: bool = True,
        normalized_entry: bool = True,
        precision: int = 2,
    ) -> "NumericControl":
        minimum = float(minimum)
        maximum = float(maximum)
        precision = int(max(0, precision))

        # Row layout: label | slider | entry
        # Keep it stable without font metrics.
        row_h = 0.105
        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, row_h),
            pos=(x, 0, y),
        )

        label_w = max(0.20, w * 0.42)
        entry_w = max(0.18, w * 0.16)
        slider_w = max(0.18, w - label_w - entry_w - theme.gap * 2)

        lbl = DirectLabel(
            parent=root,
            text=str(label),
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, row_h * 0.58),
        )

        slider_min, slider_max = ((0.0, 100.0) if normalized_slider else (minimum, maximum))
        slider_value = NumericControl._to_slider_value(
            value, minimum=minimum, maximum=maximum, normalized=normalized_slider
        )

        s = DirectSlider(
            parent=root,
            range=(slider_min, slider_max),
            value=slider_value,
            pageSize=max(0.001, (slider_max - slider_min) / 100.0),
            frameColor=theme.panel2,
            thumb_frameColor=theme.outline,
            thumb_relief=DGG.FLAT,
            thumb_frameSize=(-0.030, 0.030, -0.040, 0.040),
            relief=DGG.FLAT,
            frameSize=(-1.0, 1.0, -0.040, 0.040),
            scale=(slider_w / 2.0, 1, 1),
            pos=(label_w + theme.gap + slider_w / 2.0, 0, row_h * 0.30),
        )

        def _fmt(v: float) -> str:
            return f"{v:.{precision}f}"

        def _display(v: float) -> str:
            if normalized_entry:
                sv = NumericControl._to_slider_value(
                    v, minimum=minimum, maximum=maximum, normalized=True
                )
                return f"{sv:.1f}"
            return _fmt(v)

        def _clamp(v: float) -> float:
            return max(minimum, min(maximum, float(v)))

        def _emit(v: float) -> None:
            on_change(float(v))

        def _from_slider() -> None:
            v = NumericControl._from_slider_value(
                float(s["value"]), minimum=minimum, maximum=maximum, normalized=normalized_slider
            )
            v = _clamp(v)
            entry.entry.enterText(_display(v))
            _emit(v)

        s["command"] = _from_slider

        entry = TextInput.build(
            parent=root,
            theme=theme,
            x=label_w + theme.gap + slider_w + theme.gap + entry_w / 2.0,
            y=row_h * 0.34,
            w=entry_w,
            h=row_h * 0.64,
            initial="",
            on_submit=lambda text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )

        out = NumericControl(
            root=root,
            label=lbl,
            slider=s,
            entry=entry,
            minimum=minimum,
            maximum=maximum,
            normalized_slider=bool(normalized_slider),
            normalized_entry=bool(normalized_entry),
            precision=precision,
            on_change=on_change,
        )

        def _from_entry(text: str) -> None:
            try:
                vv = float(str(text).strip())
            except Exception:
                # Restore current value from slider.
                cur = NumericControl._from_slider_value(
                    float(out.slider["value"]),
                    minimum=out.minimum,
                    maximum=out.maximum,
                    normalized=out.normalized_slider,
                )
                out.entry.entry.enterText(_display(cur))
                return
            if out.normalized_entry:
                vv = NumericControl._from_slider_value(
                    vv, minimum=out.minimum, maximum=out.maximum, normalized=True
                )
            vv = _clamp(vv)
            out.set_value(vv, emit=True)

        out.entry.entry["command"] = _from_entry
        out.set_value(float(value), emit=False)
        return out

    @staticmethod
    def _to_slider_value(*, value: float, minimum: float, maximum: float, normalized: bool) -> float:
        v = max(minimum, min(maximum, float(value)))
        if not normalized:
            return v
        span = max(1e-12, maximum - minimum)
        return ((v - minimum) / span) * 100.0

    @staticmethod
    def _from_slider_value(*, slider_value: float, minimum: float, maximum: float, normalized: bool) -> float:
        if not normalized:
            return max(minimum, min(maximum, float(slider_value)))
        span = max(1e-12, maximum - minimum)
        v = minimum + (max(0.0, min(100.0, float(slider_value))) / 100.0) * span
        return max(minimum, min(maximum, v))

    def set_value(self, value: float, *, emit: bool) -> None:
        v = max(self.minimum, min(self.maximum, float(value)))
        self.slider["value"] = self._to_slider_value(
            value=v, minimum=self.minimum, maximum=self.maximum, normalized=self.normalized_slider
        )
        if self.normalized_entry:
            sv = self._to_slider_value(value=v, minimum=self.minimum, maximum=self.maximum, normalized=True)
            self.entry.entry.enterText(f"{sv:.1f}")
        else:
            self.entry.entry.enterText(f"{v:.{self.precision}f}")
        if emit:
            self.on_change(v)

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

