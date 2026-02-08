from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode


class PauseMenuUI:
    """In-game ESC menu with navigation actions and key binding controls."""

    def __init__(
        self,
        *,
        aspect2d,
        on_resume,
        on_map_selector,
        on_back_to_menu,
        on_quit,
        on_open_keybindings,
        on_rebind_noclip,
    ) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())

        panel_top = 0.95
        panel_bottom = -0.70
        panel_width = 0.82
        right = aspect_ratio - 0.02
        left = right - panel_width

        self.root = DirectFrame(
            parent=aspect2d,
            frameColor=(0.06, 0.06, 0.06, 0.90),
            frameSize=(left, right, panel_bottom, panel_top),
            relief=DGG.FLAT,
            pos=(0, 0, 0),
        )

        self._main_nodes = []
        self._keys_nodes = []

        title = DirectLabel(
            parent=self.root,
            text="Menu",
            text_scale=0.060,
            text_align=TextNode.ALeft,
            text_fg=(1.0, 0.92, 0.65, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.12),
        )
        hint = DirectLabel(
            parent=self.root,
            text="Esc: resume | `: debug menu",
            text_scale=0.038,
            text_align=TextNode.ALeft,
            text_fg=(0.85, 0.85, 0.85, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.20),
        )
        self._main_nodes.extend([title, hint])

        btn_w = (right - left) - 0.12
        btn_x = left + 0.06 + (btn_w / 2.0)
        btn_frame = (-4.0, 4.0, -0.55, 0.55)
        btn_scale = btn_w / 8.0

        def _btn(*, label: str, y: float, command):
            b = DirectButton(
                parent=self.root,
                text=(label, label, label, label),
                text_scale=0.62,
                text_fg=(0.95, 0.95, 0.95, 1),
                frameColor=(0.18, 0.18, 0.18, 0.95),
                relief=DGG.FLAT,
                command=command,
                scale=btn_scale,
                frameSize=btn_frame,
                pos=(btn_x, 0, y),
            )
            self._main_nodes.append(b)

        _btn(label="Resume", y=panel_top - 0.38, command=on_resume)
        _btn(label="Map Selector", y=panel_top - 0.55, command=on_map_selector)
        _btn(label="Key Bindings", y=panel_top - 0.72, command=on_open_keybindings)
        _btn(label="Back to Main Menu", y=panel_top - 0.89, command=on_back_to_menu)
        _btn(label="Quit", y=panel_top - 1.06, command=on_quit)

        keys_title = DirectLabel(
            parent=self.root,
            text="Key Bindings",
            text_scale=0.056,
            text_align=TextNode.ALeft,
            text_fg=(1.0, 0.92, 0.65, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.12),
        )
        keys_hint = DirectLabel(
            parent=self.root,
            text="Set keys used while in-game.",
            text_scale=0.036,
            text_align=TextNode.ALeft,
            text_fg=(0.85, 0.85, 0.85, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.20),
        )
        self._keybind_status = DirectLabel(
            parent=self.root,
            text="",
            text_scale=0.036,
            text_align=TextNode.ALeft,
            text_fg=(0.96, 0.90, 0.72, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.74),
            text_wordwrap=20,
        )

        self._noclip_bind_button = DirectButton(
            parent=self.root,
            text=("Rebind Noclip Toggle",) * 4,
            text_scale=0.56,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.20, 0.20, 0.20, 0.95),
            relief=DGG.FLAT,
            command=on_rebind_noclip,
            scale=btn_scale,
            frameSize=btn_frame,
            pos=(btn_x, 0, panel_top - 0.45),
        )
        self._noclip_bind_label = DirectLabel(
            parent=self.root,
            text="Current noclip key: V",
            text_scale=0.042,
            text_align=TextNode.ALeft,
            text_fg=(0.90, 0.90, 0.90, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(left + 0.06, 0, panel_top - 0.58),
        )
        self._keys_back_button = DirectButton(
            parent=self.root,
            text=("Back",) * 4,
            text_scale=0.62,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.18, 0.18, 0.18, 0.95),
            relief=DGG.FLAT,
            command=self.show_main,
            scale=btn_scale,
            frameSize=btn_frame,
            pos=(btn_x, 0, panel_top - 0.92),
        )

        self._keys_nodes.extend(
            [
                keys_title,
                keys_hint,
                self._noclip_bind_button,
                self._noclip_bind_label,
                self._keybind_status,
                self._keys_back_button,
            ]
        )

        self.show_main()
        self.root.hide()

    def show(self) -> None:
        self.root.show()

    def hide(self) -> None:
        self.root.hide()
        self.set_keybind_status("")
        self.show_main()

    def destroy(self) -> None:
        self.root.destroy()

    def show_main(self) -> None:
        for node in self._main_nodes:
            node.show()
        for node in self._keys_nodes:
            node.hide()
        self.set_keybind_status("")

    def show_keybindings(self) -> None:
        for node in self._main_nodes:
            node.hide()
        for node in self._keys_nodes:
            node.show()

    def set_noclip_binding(self, key_name: str) -> None:
        self._noclip_bind_label["text"] = f"Current noclip key: {key_name.upper()}"

    def set_keybind_status(self, text: str) -> None:
        self._keybind_status["text"] = text
