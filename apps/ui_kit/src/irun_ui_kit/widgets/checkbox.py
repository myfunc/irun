from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


@dataclass
class Checkbox:
    """
    Minimal procedural checkbox.

    Implemented as a single button with a text prefix:
    - "[x]" when checked
    - "[ ]" when unchecked
    """

    node: DirectButton
    checked: bool
    label: str

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
        checked: bool = False,
        on_change=None,
        frame_color: Color | None = None,
        text_fg: Color | None = None,
        disabled: bool = False,
    ) -> "Checkbox":
        def _prefix(v: bool) -> str:
            return "[x]" if v else "[ ]"

        def _text(v: bool) -> str:
            return f"{_prefix(v)} {label}"

        cb = DirectButton(
            parent=parent,
            text=(_text(checked), _text(checked), _text(checked), _text(checked)),
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            text_pos=(-w / 2 + 0.05, -theme.label_scale * 0.35),
            text_fg=text_fg or theme.text,
            frameColor=frame_color or theme.panel2,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=lambda: None,
        )

        out = Checkbox(node=cb, checked=checked, label=label)

        def _toggle() -> None:
            if disabled:
                return
            out.checked = not out.checked
            out.node["text"] = (_text(out.checked), _text(out.checked), _text(out.checked), _text(out.checked))
            if on_change is not None:
                on_change(out.checked)

        out.node["command"] = _toggle
        if disabled:
            out.node["state"] = DGG.DISABLED
            out.node["text_fg"] = theme.text_muted

        return out

