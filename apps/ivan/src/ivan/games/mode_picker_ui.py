from __future__ import annotations

from dataclasses import dataclass

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.list_menu import ListMenu, ListMenuItem


@dataclass(frozen=True)
class ModeItem:
    id: str
    label: str


class GameModePickerUI:
    def __init__(self, *, aspect2d, theme: Theme, on_select, on_close) -> None:
        self._menu = ListMenu(
            aspect2d=aspect2d,
            theme=theme,
            title="IVAN :: Game Editor",
            hint="Up/Down: select | Enter/click: choose | Esc: close",
        )
        self._on_select = on_select
        self._on_close = on_close
        self._items: list[ModeItem] = []
        self._visible = False
        self.hide()

    def show(self, *, items: list[ModeItem], status: str = "") -> None:
        self._items = list(items)
        rows = [ListMenuItem(it.label, enabled=True) for it in self._items]
        self._menu.set_items(rows, selected=0)
        self._menu.set_status(status)
        self._menu.show()
        self._visible = True

    def hide(self) -> None:
        self._menu.hide()
        self._visible = False

    def destroy(self) -> None:
        self._menu.destroy()

    def is_visible(self) -> bool:
        return bool(self._visible)

    def tick(self, now: float) -> None:
        if self._visible:
            self._menu.tick(float(now))

    def move(self, delta: int) -> None:
        if self._visible:
            self._menu.move(int(delta))

    def on_enter(self) -> None:
        if not self._visible:
            return
        idx = self._menu.selected_index()
        if idx is None or idx < 0 or idx >= len(self._items):
            return
        self._on_select(self._items[idx].id)

    def on_escape(self) -> None:
        if self._visible:
            self._on_close()

