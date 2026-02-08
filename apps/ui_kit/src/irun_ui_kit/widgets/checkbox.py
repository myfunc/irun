from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme, Color


def _mul(c: Color, m: float) -> Color:
    r, g, b, a = c
    return (max(0.0, min(1.0, r * m)), max(0.0, min(1.0, g * m)), max(0.0, min(1.0, b * m)), a)


@dataclass
class Checkbox:
    """
    Procedural checkbox with visual box + check mark.

    - Hover: subtle lift on the whole row + accent outline on the box.
    - Press: darken.
    - Checked: accent-filled box with an ink-colored mark.
    """

    button: DirectButton
    box_outline: DirectFrame
    box_fill: DirectFrame
    mark: DirectLabel
    text: DirectLabel
    checked: bool
    disabled: bool
    theme: Theme
    _sync_fn: callable

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
        disabled: bool = False,
    ) -> "Checkbox":
        bg = theme.panel2
        frame_colors = (
            bg,
            _mul(bg, 0.82),  # pressed
            _mul(bg, 1.08),  # hover
            _mul(bg, 0.60),  # disabled
        )

        # Clickable row.
        b = DirectButton(
            parent=parent,
            text="",
            text_fg=theme.text,
            frameColor=frame_colors,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=lambda: None,
            pressEffect=0,
        )

        # Visual box on the left.
        box = min(h * 0.70, 0.085)
        box_x0 = -w / 2 + (theme.pad * 0.70)
        box_y0 = -box / 2

        outline = DirectFrame(
            parent=b,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(box_x0, box_x0 + box, box_y0, box_y0 + box),
        )
        fill = DirectFrame(
            parent=b,
            frameColor=theme.panel,
            relief=DGG.FLAT,
            frameSize=(
                box_x0 + theme.outline_w,
                box_x0 + box - theme.outline_w,
                box_y0 + theme.outline_w,
                box_y0 + box - theme.outline_w,
            ),
        )
        mark = DirectLabel(
            parent=b,
            text="",
            text_scale=theme.label_scale * 0.95,
            text_align=TextNode.ACenter,
            text_fg=theme.ink,
            frameColor=(0, 0, 0, 0),
            pos=(box_x0 + box / 2, 0, -theme.label_scale * 0.30),
        )
        txt = DirectLabel(
            parent=b,
            text=label,
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(box_x0 + box + (theme.pad * 0.55), 0, -theme.label_scale * 0.35),
        )

        out = Checkbox(
            button=b,
            box_outline=outline,
            box_fill=fill,
            mark=mark,
            text=txt,
            checked=bool(checked),
            disabled=bool(disabled),
            theme=theme,
            _sync_fn=lambda: None,
        )

        def _sync() -> None:
            if out.checked:
                out.box_outline["frameColor"] = theme.header
                out.box_fill["frameColor"] = _mul(theme.header, 0.95)
                out.mark["text"] = "x"
            else:
                out.box_outline["frameColor"] = theme.outline
                out.box_fill["frameColor"] = theme.panel
                out.mark["text"] = ""

            if out.disabled:
                out.button["state"] = DGG.DISABLED
                out.button["text_fg"] = theme.text_muted
                out.text["text_fg"] = theme.text_muted
                out.box_outline["frameColor"] = _mul(theme.outline, 0.70)
                out.box_fill["frameColor"] = _mul(theme.panel, 0.70)
                out.mark["text_fg"] = theme.text_muted
            else:
                out.text["text_fg"] = theme.text
                out.mark["text_fg"] = theme.ink

        def _toggle() -> None:
            if out.disabled:
                return
            out.checked = not out.checked
            _sync()
            if on_change is not None:
                on_change(out.checked)

        def _hover_on(_evt=None) -> None:
            if out.disabled:
                return
            # Accent the box outline on hover for clarity.
            out.box_outline["frameColor"] = _mul(theme.header, 1.05) if out.checked else _mul(theme.header, 0.85)

        def _hover_off(_evt=None) -> None:
            if out.disabled:
                return
            _sync()

        out.button["command"] = _toggle
        out.button.bind(DGG.ENTER, _hover_on)
        out.button.bind(DGG.EXIT, _hover_off)

        out._sync_fn = _sync
        _sync()
        return out

    def set_checked(self, checked: bool) -> None:
        self.checked = bool(checked)
        try:
            self._sync_fn()
        except Exception:
            pass

    def set_disabled(self, disabled: bool) -> None:
        self.disabled = bool(disabled)
        try:
            self._sync_fn()
        except Exception:
            pass
