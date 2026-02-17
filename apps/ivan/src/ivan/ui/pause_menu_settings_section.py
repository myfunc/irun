from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.slider import Slider
from irun_ui_kit.widgets.text_input import TextInput


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
        on_apply_mcp_control,
        on_back,
        master_volume: float,
        sfx_volume: float,
        mcp_control_enabled: bool,
        mcp_control_port: int,
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
        row_step = max(0.118, float(button_h) * 1.02)
        section_gap = max(0.045, float(theme.gap) * 1.45)
        s0 = top_y - theme.label_scale * 2.95
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
            y=s0 - row_step,
            w=slider_w,
            label="Sfx Volume",
            min_value=0.0,
            max_value=1.0,
            value=self._sfx_volume,
            on_change=self._on_sfx_change,
            decimals=2,
        )

        keybind_label_y = s0 - row_step - section_gap - (button_h * 0.22)
        keybind_button_y = keybind_label_y - (button_h * 0.86)
        self._noclip_bind_label = DirectLabel(
            parent=parent,
            text="Current noclip key: V",
            text_scale=theme.label_scale * 0.94,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, keybind_label_y),
        )
        self._noclip_bind_button = Button.build(
            parent=parent,
            theme=theme,
            x=width / 2.0,
            y=keybind_button_y,
            w=width,
            h=button_h,
            label="Rebind Noclip Toggle",
            on_click=on_rebind_noclip,
        )

        mcp_y = keybind_button_y - (button_h * 1.12)
        self._mcp_checkbox = Checkbox.build(
            parent=parent,
            theme=theme,
            x=width * 0.5,
            y=mcp_y,
            w=width,
            h=button_h * 0.58,
            label="Enable MCP Console Control",
            checked=bool(mcp_control_enabled),
            on_change=lambda _checked: None,
        )
        mcp_port_label_y = mcp_y - (button_h * 0.95)
        mcp_port_input_y = mcp_port_label_y - 0.10
        mcp_apply_button_y = mcp_port_input_y - 0.145
        self._mcp_port_label = DirectLabel(
            parent=parent,
            text="MCP Port",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, mcp_port_label_y),
        )
        self._mcp_port_input = TextInput.build(
            parent=parent,
            theme=theme,
            x=width * 0.5,
            y=mcp_port_input_y,
            w=width,
            h=0.10,
            initial=str(int(mcp_control_port)),
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._mcp_apply_button = Button.build(
            parent=parent,
            theme=theme,
            x=width * 0.5,
            y=mcp_apply_button_y,
            w=width,
            h=button_h,
            label="Apply MCP Settings",
            on_click=lambda: on_apply_mcp_control(self.mcp_control_enabled, self.mcp_control_port_text),
        )

        status_h = max(0.11, button_h * 1.06)
        status_y = theme.pad + button_h + theme.gap + 0.022
        self._status_panel = DirectFrame(
            parent=parent,
            frameColor=theme.panel2,
            relief=DGG.FLAT,
            frameSize=(0.0, width, 0.0, status_h),
            pos=(0.0, 0.0, status_y),
        )
        self._status = DirectLabel(
            parent=self._status_panel,
            text="",
            text_scale=theme.small_scale * 0.96,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad * 0.65, 0.0, status_h * 0.33),
            text_wordwrap=30,
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

    @property
    def mcp_control_enabled(self) -> bool:
        try:
            return bool(self._mcp_checkbox.checked)
        except Exception:
            return True

    @property
    def mcp_control_port_text(self) -> str:
        try:
            return str(self._mcp_port_input.entry.get()).strip()
        except Exception:
            return ""

    def set_mcp_settings(self, *, enabled: bool, port: int) -> None:
        try:
            self._mcp_checkbox.set_checked(bool(enabled))
        except Exception:
            pass
        try:
            self._mcp_port_input.entry.enterText(str(int(port)))
        except Exception:
            pass

    def set_mcp_status(self, text: str) -> None:
        self.set_status(text)
