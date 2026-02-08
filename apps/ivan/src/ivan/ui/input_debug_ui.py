from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme


class InputDebugUI:
    def __init__(self, *, aspect2d, theme: Theme) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        self._theme = theme
        self._last_text = ""

        # Boxed overlay anchored top-left to avoid overlapping the bottom status bar and menus.
        pad = 0.06
        w = min(1.55, (aspect_ratio * 2.0) - (pad * 2.0))
        h = 0.30
        x = -aspect_ratio + pad
        y = 0.62

        self._root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(x, 0.0, y),
        )
        self._root["state"] = DGG.DISABLED
        DirectFrame(
            parent=self._root,
            frameColor=(theme.panel[0], theme.panel[1], theme.panel[2], 0.86),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
        )["state"] = DGG.DISABLED

        self._label = DirectLabel(
            parent=self._root,
            text="",
            text_scale=0.035,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0.0, h - theme.pad - 0.040),
            text_wordwrap=80,
        )
        self._root.hide()
        self._enabled = False

    def show(self) -> None:
        self._enabled = True
        self._root.show()
        self._label["text"] = self._last_text

    def hide(self) -> None:
        self._enabled = False
        self._root.hide()

    def toggle(self) -> None:
        self._enabled = not self._enabled
        if self._enabled:
            self._root.show()
            self._label["text"] = self._last_text
        else:
            self._root.hide()

    def set_text(self, text: str) -> None:
        self._last_text = str(text)
        if self._enabled:
            self._label["text"] = self._last_text
