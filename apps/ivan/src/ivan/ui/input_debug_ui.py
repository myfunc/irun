from __future__ import annotations

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, TransparencyAttrib

from irun_ui_kit.theme import Theme
from ivan.ui.ui_layout import INPUT_DEBUG_TOP_ANCHOR, SCREEN_PAD_X, aspect_ratio


class InputDebugUI:
    def __init__(self, *, aspect2d, theme: Theme) -> None:
        screen_ar = aspect_ratio()

        self._theme = theme
        self._last_text = ""
        self._panel_width = 0.0
        self._panel_height = 0.0
        self._min_height = 0.24
        self._max_height = 0.70
        self._wordwrap = 112

        # Boxed overlay anchored top-left to avoid overlapping the bottom status bar and menus.
        pad = SCREEN_PAD_X
        w = min(2.45, (screen_ar * 2.0) - (pad * 2.0))
        h = 0.34
        x = -screen_ar + pad
        self._top_anchor = INPUT_DEBUG_TOP_ANCHOR
        y = self._top_anchor - h
        self._panel_width = float(w)
        self._panel_height = float(h)
        self._anchor_x = float(x)
        self._anchor_y = float(y)

        self._root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(x, 0.0, y),
        )
        self._root["state"] = DGG.DISABLED
        self._root.setTransparency(TransparencyAttrib.M_alpha)
        self._inner = DirectFrame(
            parent=self._root,
            frameColor=(theme.panel[0], theme.panel[1], theme.panel[2], 0.48),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, w - theme.outline_w, theme.outline_w, h - theme.outline_w),
        )
        self._inner["state"] = DGG.DISABLED
        self._inner.setTransparency(TransparencyAttrib.M_alpha)

        self._label = DirectLabel(
            parent=self._root,
            text="",
            text_scale=0.029,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0.0, h - theme.pad - 0.034),
            text_wordwrap=self._wordwrap,
        )
        self._label.setTransparency(TransparencyAttrib.M_alpha)
        self._root.hide()
        self._enabled = False

    @property
    def root(self):
        return self._root

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
        self._fit_to_content(self._last_text)
        if self._enabled:
            self._label["text"] = self._last_text

    def _fit_to_content(self, text: str) -> None:
        lines = str(text).splitlines() or [""]
        wrap_chars = max(28, int(self._wordwrap))
        visual_lines = 0
        for line in lines:
            n = max(1, int(math.ceil(len(line) / float(wrap_chars))))
            visual_lines += n

        # Tuned empirically for DirectLabel's line spacing in this HUD.
        required = 0.06 + (visual_lines * 0.035)
        target_h = max(self._min_height, min(self._max_height, required))
        self._set_height(target_h)

    def _set_height(self, h: float) -> None:
        h = float(max(self._min_height, min(self._max_height, h)))
        if abs(h - self._panel_height) < 1e-5:
            return
        self._panel_height = h
        w = self._panel_width
        t = self._theme
        self._root["frameSize"] = (0.0, w, 0.0, h)
        self._root.setPos(self._anchor_x, 0.0, self._top_anchor - h)
        self._inner["frameSize"] = (t.outline_w, w - t.outline_w, t.outline_w, h - t.outline_w)
        self._label.setPos(t.outline_w + t.pad * 0.50, 0.0, h - t.pad - 0.034)
