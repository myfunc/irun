from __future__ import annotations

from dataclasses import dataclass

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode


@dataclass(frozen=True)
class MapEntry:
    label: str
    bsp_path: str


class MapSelectUI:
    def __init__(self, *, aspect2d, title: str) -> None:
        self._aspect2d = aspect2d
        self._title = OnscreenText(
            text=title,
            parent=aspect2d,
            align=TextNode.ALeft,
            pos=(-1.30, 0.92),
            scale=0.06,
            fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 1),
        )
        self._hint = OnscreenText(
            text="Up/Down: select | Enter: import+run | Esc: quit",
            parent=aspect2d,
            align=TextNode.ALeft,
            pos=(-1.30, 0.84),
            scale=0.045,
            fg=(0.85, 0.85, 0.85, 1),
            shadow=(0, 0, 0, 1),
        )
        self._status = OnscreenText(
            text="",
            parent=aspect2d,
            align=TextNode.ALeft,
            pos=(-1.30, -0.92),
            scale=0.045,
            fg=(0.9, 0.9, 0.9, 1),
            shadow=(0, 0, 0, 1),
        )

        self._rows: list[OnscreenText] = []
        self._visible_rows = 22
        for i in range(self._visible_rows):
            y = 0.74 - i * 0.065
            self._rows.append(
                OnscreenText(
                    text="",
                    parent=aspect2d,
                    align=TextNode.ALeft,
                    pos=(-1.30, y),
                    scale=0.045,
                    fg=(0.8, 0.8, 0.8, 1),
                    shadow=(0, 0, 0, 1),
                )
            )

        self._entries: list[MapEntry] = []
        self._selected: int = 0

    def destroy(self) -> None:
        for t in self._rows:
            t.removeNode()
        self._rows.clear()
        self._title.removeNode()
        self._hint.removeNode()
        self._status.removeNode()

    def set_entries(self, entries: list[MapEntry]) -> None:
        self._entries = entries
        self._selected = 0
        self._redraw()

    def move(self, delta: int) -> None:
        if not self._entries:
            return
        self._selected = max(0, min(len(self._entries) - 1, self._selected + delta))
        self._redraw()

    def selected(self) -> MapEntry | None:
        if not self._entries:
            return None
        return self._entries[self._selected]

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def _redraw(self) -> None:
        if not self._entries:
            for r in self._rows:
                r.setText("")
            self._status.setText("No maps found.")
            return

        # Keep selection centered-ish.
        half = self._visible_rows // 2
        start = max(0, min(len(self._entries) - self._visible_rows, self._selected - half))
        window = self._entries[start : start + self._visible_rows]

        for i, r in enumerate(self._rows):
            if i >= len(window):
                r.setText("")
                continue
            idx = start + i
            prefix = "> " if idx == self._selected else "  "
            r.setText(prefix + window[i].label)
            if idx == self._selected:
                r.setFg((1.0, 0.95, 0.75, 1))
            else:
                r.setFg((0.8, 0.8, 0.8, 1))

        self._status.setText(f"{self._selected + 1}/{len(self._entries)}")

