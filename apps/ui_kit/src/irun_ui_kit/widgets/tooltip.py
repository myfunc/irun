from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme


@dataclass
class Tooltip:
    """
    Minimal tooltip helper.

    This is intentionally simple: callers create one tooltip label per screen/panel and
    bind widgets (ENTER/EXIT) to show/hide it.
    """

    label: DirectLabel

    @staticmethod
    def build(*, parent, theme: Theme, x: float, y: float, w: float, wordwrap: int = 60) -> "Tooltip":
        lbl = DirectLabel(
            parent=parent,
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
            text_wordwrap=int(max(10, wordwrap)),
        )
        lbl.hide()
        return Tooltip(label=lbl)

    def show(self, text: str) -> None:
        self.label["text"] = str(text)
        self.label.show()

    def hide(self) -> None:
        self.label.hide()

    def bind(self, widget, text: str) -> None:
        """
        Bind hover events to show/hide this tooltip.

        `widget` must be a DirectGUI node that supports .bind(...).
        """

        try:
            widget.bind(DGG.ENTER, lambda _evt, tip=str(text): self.show(tip))
            widget.bind(DGG.EXIT, lambda _evt: self.hide())
        except Exception:
            # Not all DirectGUI objects expose bind() consistently across Panda builds.
            return

    def destroy(self) -> None:
        try:
            self.label.destroy()
        except Exception:
            pass
