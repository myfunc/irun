from __future__ import annotations

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode


class InputDebugUI:
    def __init__(self, *, aspect2d) -> None:
        self._text = OnscreenText(
            text="",
            parent=aspect2d,
            align=TextNode.ALeft,
            pos=(-1.30, -0.92),
            scale=0.04,
            fg=(0.95, 0.95, 0.95, 0.95),
            shadow=(0, 0, 0, 1),
        )
        self._text.hide()
        self._enabled = False

    def show(self) -> None:
        self._enabled = True
        self._text.show()

    def hide(self) -> None:
        self._enabled = False
        self._text.hide()

    def toggle(self) -> None:
        self._enabled = not self._enabled
        if self._enabled:
            self._text.show()
        else:
            self._text.hide()

    def set_text(self, text: str) -> None:
        if not self._enabled:
            return
        self._text.setText(text)
