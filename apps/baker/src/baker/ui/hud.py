from __future__ import annotations

from dataclasses import dataclass

from direct.gui.OnscreenText import OnscreenText


@dataclass
class HudState:
    map_label: str = ""
    tonemap_label: str = "gamma-only"
    pointer_lock_label: str = "locked"


class ViewerHUD:
    def __init__(self, *, aspect2d) -> None:
        self._root = aspect2d
        self.state = HudState()

        self._title = OnscreenText(
            text="IRUN Baker (mapperoni)",
            parent=self._root,
            pos=(-1.28, 0.94),
            scale=0.05,
            fg=(1, 1, 1, 1),
            align=0,  # left
            mayChange=False,
        )
        self._map = OnscreenText(
            text="",
            parent=self._root,
            pos=(-1.28, 0.88),
            scale=0.04,
            fg=(0.9, 0.9, 0.9, 1),
            align=0,
            mayChange=True,
        )
        self._tonemap = OnscreenText(
            text="",
            parent=self._root,
            pos=(-1.28, 0.82),
            scale=0.04,
            fg=(0.9, 0.9, 0.9, 1),
            align=0,
            mayChange=True,
        )
        self._lock = OnscreenText(
            text="",
            parent=self._root,
            pos=(-1.28, 0.76),
            scale=0.04,
            fg=(0.9, 0.9, 0.9, 1),
            align=0,
            mayChange=True,
        )
        self._input = OnscreenText(
            text="",
            parent=self._root,
            pos=(-1.28, 0.70),
            scale=0.035,
            fg=(0.75, 0.85, 1.0, 1),
            align=0,
            mayChange=True,
        )
        self._logtail = OnscreenText(
            text="",
            parent=self._root,
            pos=(-1.28, 0.62),
            scale=0.03,
            fg=(1.0, 0.75, 0.75, 1),
            align=0,
            mayChange=True,
        )
        self._help = OnscreenText(
            text=(
                "WASD move, Q/E down/up, Shift faster (RU layout supported)\n"
                "Hold mouse button to look | Tab toggle look | Esc unlock cursor\n"
                "F focus | F1 input debug | 1 gamma-only | 2 Reinhard | 3 ACES approx"
            ),
            parent=self._root,
            pos=(-1.28, -0.94),
            scale=0.035,
            fg=(0.85, 0.85, 0.85, 1),
            align=0,
            mayChange=False,
        )

        self.refresh()

    def refresh(self) -> None:
        self._map.setText(f"Map: {self.state.map_label}" if self.state.map_label else "Map: (unknown)")
        self._tonemap.setText(f"Tonemap: {self.state.tonemap_label}")
        self._lock.setText(f"Pointer: {self.state.pointer_lock_label}")

    def set_map_label(self, label: str) -> None:
        self.state.map_label = str(label)
        self.refresh()

    def set_tonemap_label(self, label: str) -> None:
        self.state.tonemap_label = str(label)
        self.refresh()

    def set_pointer_lock_label(self, label: str) -> None:
        self.state.pointer_lock_label = str(label)
        self.refresh()

    def set_input_debug(self, text: str) -> None:
        # Debug is optional; keep it empty by default.
        self._input.setText(str(text or ""))

    def set_log_tail(self, text: str) -> None:
        self._logtail.setText(str(text or ""))
