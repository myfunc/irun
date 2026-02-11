from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.slider import Slider


class PauseMenuSettingsSection:
    def __init__(
        self,
        *,
        parent,
        theme: Theme,
        page_h: float,
        width: float,
        button_h: float,
        on_rebind_noclip,
        on_master_volume_change,
        on_sfx_volume_change,
        on_back,
        master_volume: float,
        sfx_volume: float,
    ) -> None:
        self._theme = theme
        self._master_volume = max(0.0, min(1.0, float(master_volume)))
        self._sfx_volume = max(0.0, min(1.0, float(sfx_volume)))
        self._on_master_volume_change = on_master_volume_change
        self._on_sfx_volume_change = on_sfx_volume_change

        top_y = page_h - theme.pad
        self._title = DirectLabel(
            parent=parent,
            text="Settings",
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, top_y - theme.label_scale * 0.6),
        )

        self._controls_hint = DirectLabel(
            parent=parent,
            text="Fire: LMB   Grapple: RMB   Slots: 1/2/3/4",
            text_scale=theme.small_scale * 0.95,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, top_y - theme.label_scale * 1.85),
        )

        slider_w = float(width)
        s0 = top_y - theme.label_scale * 3.2
        self._master_slider = Slider.build(
            parent=parent,
            theme=theme,
            x=slider_w * 0.5,
            y=s0,
            w=slider_w,
            label="Master Volume",
            min_value=0.0,
            max_value=1.0,
            value=self._master_volume,
            on_change=self._on_master_change,
            decimals=2,
        )
        self._sfx_slider = Slider.build(
            parent=parent,
            theme=theme,
            x=slider_w * 0.5,
            y=s0 - 0.14,
            w=slider_w,
            label="Sfx Volume",
            min_value=0.0,
            max_value=1.0,
            value=self._sfx_volume,
            on_change=self._on_sfx_change,
            decimals=2,
        )

        self._noclip_bind_label = DirectLabel(
            parent=parent,
            text="Current noclip key: V",
            text_scale=theme.label_scale * 0.94,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, s0 - 0.30),
        )
        self._noclip_bind_button = Button.build(
            parent=parent,
            theme=theme,
            x=width / 2.0,
            y=s0 - 0.42,
            w=width,
            h=button_h,
            label="Rebind Noclip Toggle",
            on_click=on_rebind_noclip,
        )

        self._status_panel = DirectFrame(
            parent=parent,
            frameColor=theme.panel2,
            relief=DGG.FLAT,
            frameSize=(0.0, width, 0.0, max(0.12, button_h * 1.22)),
            pos=(0.0, 0.0, theme.pad + button_h + theme.gap + 0.015),
        )
        self._status = DirectLabel(
            parent=self._status_panel,
            text="",
            text_scale=theme.small_scale * 0.96,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad * 0.65, 0.0, max(0.12, button_h * 1.22) * 0.33),
            text_wordwrap=24,
        )

        self._back_button = Button.build(
            parent=parent,
            theme=theme,
            x=width / 2.0,
            y=theme.pad + button_h / 2.0,
            w=width,
            h=button_h,
            label="Back",
            on_click=on_back,
        )

    def _on_master_change(self, value: float) -> None:
        self._master_volume = max(0.0, min(1.0, float(value)))
        self._on_master_volume_change(float(self._master_volume))

    def _on_sfx_change(self, value: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, float(value)))
        self._on_sfx_volume_change(float(self._sfx_volume))

    def set_noclip_binding(self, key_name: str) -> None:
        self._noclip_bind_label["text"] = f"Current noclip key: {str(key_name).upper()}"

    def set_status(self, text: str) -> None:
        self._status["text"] = str(text)

    def set_master_volume(self, value: float) -> None:
        self._master_volume = max(0.0, min(1.0, float(value)))
        try:
            self._master_slider.slider["value"] = float(self._master_volume)
            self._master_slider.value["text"] = f"{self._master_volume:.2f}"
        except Exception:
            pass

    def set_sfx_volume(self, value: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, float(value)))
        try:
            self._sfx_slider.slider["value"] = float(self._sfx_volume)
            self._sfx_slider.value["text"] = f"{self._sfx_volume:.2f}"
        except Exception:
            pass

