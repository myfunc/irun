from __future__ import annotations

from collections import deque

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.text_input import TextInput


class ConsoleUI:
    """
    Minimal in-game console overlay.

    This is intentionally barebones: output log + single-line input.
    """

    def __init__(self, *, aspect2d, theme: Theme, on_submit) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        self._theme = theme
        self._on_submit = on_submit

        # Console occupies a bottom band (like classic drop-down console, but from the bottom).
        left = -aspect_ratio + 0.05
        right = aspect_ratio - 0.05
        width = right - left
        top = 0.15
        bottom = -0.85
        height = top - bottom

        self._root = DirectFrame(
            parent=aspect2d,
            pos=(left, 0.0, bottom),
            frameColor=(0, 0, 0, 0.78),
            relief=DGG.FLAT,
            frameSize=(0.0, width, 0.0, height),
        )

        header = DirectLabel(
            parent=self._root,
            text="Console (F4 to toggle)",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad, 0, height - theme.pad - theme.small_scale * 0.9),
        )
        header.setTransparency(True)

        # Keep the log bounded so it fits inside the panel without spilling below it.
        usable_h = max(0.1, height - theme.pad * 3 - theme.small_scale * 2.2 - 0.10 - 0.10)
        est_line_h = max(0.012, float(theme.small_scale) * 1.15)
        self._max_lines = max(6, int(usable_h / est_line_h))
        self._lines: deque[str] = deque(maxlen=int(self._max_lines))
        self._log = DirectLabel(
            parent=self._root,
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            # Place the label near the top so multi-line text flows downward inside the panel.
            pos=(theme.pad, 0, height - theme.pad - theme.small_scale * 2.3),
            text_wordwrap=max(20, int(width * 18)),
        )
        self._log.setTransparency(True)

        self._input = TextInput.build(
            parent=self._root,
            theme=theme,
            x=width / 2.0,
            y=theme.pad + 0.06,
            w=width - theme.pad * 2,
            h=0.10,
            initial="",
            on_submit=self._submit,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )

        self._root.hide()

    @property
    def visible(self) -> bool:
        try:
            return bool(self._root.isHidden() is False)
        except Exception:
            return False

    def show(self) -> None:
        self._root.show()
        try:
            self._input.entry.setFocus()
        except Exception:
            pass

    def hide(self) -> None:
        self._root.hide()

    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()

    def append(self, *lines: str) -> None:
        for ln in lines:
            s = str(ln)
            if not s:
                continue
            self._lines.append(s)
        self._log["text"] = "\n".join(self._lines)

    def _submit(self, text: str) -> None:
        line = str(text or "").strip()
        try:
            self._input.entry.enterText("")
            self._input.entry.setCursorPosition(0)
        except Exception:
            pass
        if not line:
            return
        self.append(f"] {line}")
        try:
            out_lines = self._on_submit(line)
        except Exception as e:
            out_lines = [f"error: {e}"]
        if out_lines:
            for ln in out_lines:
                self.append(str(ln))
