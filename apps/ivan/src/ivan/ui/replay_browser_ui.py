from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.list_menu import ListMenu, ListMenuItem


@dataclass(frozen=True)
class ReplayListItem:
    label: str
    path: Path


class ReplayBrowserUI:
    def __init__(self, *, aspect2d, theme: Theme, on_select, on_close) -> None:
        self._menu = ListMenu(
            aspect2d=aspect2d,
            theme=theme,
            title="IVAN :: Replays",
            hint="Up/Down: select | Enter: load replay | Esc: back",
        )
        self._on_select = on_select
        self._on_close = on_close
        self._items: list[ReplayListItem] = []
        self._visible = False
        self.hide()

    def destroy(self) -> None:
        self._menu.destroy()

    def show(self, *, items: list[ReplayListItem], status: str = "") -> None:
        self._items = list(items)
        rows = [ListMenuItem(i.label, enabled=True) for i in self._items]
        self._menu.set_items(rows, selected=0)
        self._menu.set_status(status)
        self._menu.show()
        self._visible = True

    def hide(self) -> None:
        self._menu.hide()
        self._visible = False

    def is_visible(self) -> bool:
        return self._visible

    def tick(self, now: float) -> None:
        if self._visible:
            self._menu.tick(now)

    def move(self, delta: int) -> None:
        if self._visible:
            self._menu.move(delta)

    def on_enter(self) -> None:
        if not self._visible:
            return
        idx = self._menu.selected_index()
        if idx is None or idx < 0 or idx >= len(self._items):
            return
        self._on_select(self._items[idx].path)

    def on_escape(self) -> None:
        if not self._visible:
            return
        self._on_close()
