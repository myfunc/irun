from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel, DirectSlider
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class Slider:
    """
    Basic slider with a label and a numeric value readout.

    This is intentionally minimal; the visuals are procedural and themed via colors.
    """

    root: DirectFrame
    slider: DirectSlider
    label: DirectLabel
    value: DirectLabel

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        label: str,
        min_value: float,
        max_value: float,
        value: float,
        on_change=None,
        decimals: int = 2,
        track_color: Color | None = None,
        thumb_color: Color | None = None,
        text_fg: Color | None = None,
    ) -> "Slider":
        root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -0.08, 0.08),
            pos=(x, 0, y),
        )

        fg = text_fg or theme.text
        track = track_color or theme.panel2
        thumb = thumb_color or theme.header

        lbl = DirectLabel(
            parent=root,
            text=label,
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=fg,
            frameColor=(0, 0, 0, 0),
            pos=(-w / 2, 0, 0.04),
        )
        val = DirectLabel(
            parent=root,
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ARight,
            text_fg=fg,
            frameColor=(0, 0, 0, 0),
            pos=(w / 2, 0, 0.04),
        )

        def _fmt(v: float) -> str:
            return f"{v:.{decimals}f}"

        def _set_value(v: float) -> None:
            try:
                vv = float(v)
            except Exception:
                vv = float(min_value)
            val["text"] = _fmt(vv)
            if on_change is not None:
                on_change(vv)

        s = DirectSlider(
            parent=root,
            range=(min_value, max_value),
            value=value,
            pageSize=(max_value - min_value) / 20.0 if max_value != min_value else 0.01,
            thumb_relief=DGG.FLAT,
            thumb_frameColor=thumb,
            frameColor=track,
            scale=(w / 2, 1, 1),
            pos=(0, 0, -0.02),
        )
        # Some Panda3D builds call DirectSlider's command with no args.
        # Read the current slider value directly for compatibility.
        s["command"] = lambda: _set_value(float(s["value"]))

        out = Slider(root=root, slider=s, label=lbl, value=val)
        out.value["text"] = _fmt(float(value))
        return out

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
