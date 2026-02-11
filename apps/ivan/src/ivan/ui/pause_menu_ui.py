from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.tabs import Tabs
from irun_ui_kit.widgets.text_input import TextInput
from ivan.ui.ui_layout import PANEL_BOTTOM, PANEL_TOP, SCREEN_PAD_X, aspect_ratio
from .pause_menu_settings_section import PauseMenuSettingsSection


class PauseMenuUI:
    """In-game ESC menu with navigation, settings, multiplayer, and feel controls."""

    def __init__(
        self,
        *,
        aspect2d,
        theme: Theme,
        on_resume,
        on_map_selector,
        on_back_to_menu,
        on_quit,
        on_open_replays,
        on_open_feel_session,
        on_open_settings,
        on_rebind_noclip,
        on_master_volume_change,
        on_sfx_volume_change,
        on_toggle_open_network,
        on_connect_server,
        on_disconnect_server,
        on_feel_export_latest,
        on_feel_apply_feedback,
        master_volume: float = 0.85,
        sfx_volume: float = 0.90,
    ) -> None:
        screen_ar = aspect_ratio()
        panel_top = PANEL_TOP
        panel_bottom = PANEL_BOTTOM
        panel_width = min(1.38, max(1.04, screen_ar * 0.74))
        right = screen_ar - 0.02
        left = right - panel_width

        w = panel_width
        h = panel_top - panel_bottom
        self._theme = theme
        self._feel_route_tag: str = "A"

        self._panel = Panel.build(
            parent=aspect2d,
            theme=theme,
            x=left,
            y=panel_bottom,
            w=w,
            h=h,
            title="Menu",
            header=True,
        )
        self.root = self._panel.node

        header_total_h = theme.header_h + (theme.outline_w * 2)
        content_h = h - header_total_h - theme.pad * 2
        content_w = w - theme.pad * 2

        self._content = DirectFrame(
            parent=self._panel.content,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            # Keep local origin at (0, 0) bottom-left for children.
            frameSize=(0.0, content_w, 0.0, content_h),
            pos=(theme.pad, 0.0, theme.pad),
        )

        # Keep button hints in a screen corner to avoid overlapping menus/HUD.
        self._hint = DirectLabel(
            parent=aspect2d,
            text="Esc: resume | `: debug menu",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            # Keep hint below the top HUD lane to avoid collisions with chips.
            pos=(-screen_ar + SCREEN_PAD_X, 0, 0.82),
        )
        self._hint.hide()

        tab_h = 0.11
        page_h = max(0.20, content_h - tab_h - theme.gap * 1.5)
        self._tabs = Tabs.build(
            parent=self._content,
            theme=theme,
            x=0.0,
            y=0.0,
            w=content_w,
            tab_h=tab_h,
            page_h=page_h,
            labels=["Menu", "Options", "Online", "Feel"],
            active=0,
        )
        self._multiplayer_status = DirectLabel(
            parent=self._tabs.page(2),
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, theme.pad),
            text_wordwrap=22,
        )
        btn_h = 0.12
        btn_w = content_w

        # Main page buttons (2-column grid to keep everything visible on smaller windows).
        y0 = page_h - theme.pad - btn_h / 2.0
        row_gap = theme.gap + 0.02
        row_step = btn_h + row_gap
        col_gap = theme.gap
        col_w = (btn_w - col_gap) * 0.5
        left_x = col_w * 0.5
        right_x = col_w + col_gap + col_w * 0.5
        self._btn_resume = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=left_x,
            y=y0,
            w=col_w,
            h=btn_h,
            label="Resume",
            on_click=on_resume,
        )
        self._btn_map_selector = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=right_x,
            y=y0,
            w=col_w,
            h=btn_h,
            label="Map Selector",
            on_click=on_map_selector,
        )

        def _open_settings() -> None:
            on_open_settings()
            self.show_settings()

        self._btn_keybindings = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=left_x,
            y=y0 - row_step,
            w=col_w,
            h=btn_h,
            label="Settings",
            on_click=_open_settings,
        )
        self._btn_replays = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=right_x,
            y=y0 - row_step,
            w=col_w,
            h=btn_h,
            label="Replays",
            on_click=on_open_replays,
        )
        self._btn_multiplayer = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=left_x,
            y=y0 - row_step * 2.0,
            w=col_w,
            h=btn_h,
            label="Multiplayer",
            on_click=self.show_multiplayer,
        )
        self._btn_feel = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=right_x,
            y=y0 - row_step * 2.0,
            w=col_w,
            h=btn_h,
            label="Feel Session",
            on_click=lambda: (on_open_feel_session(), self.show_feel_session()),
        )
        self._btn_back_to_menu = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=left_x,
            y=y0 - row_step * 3.0,
            w=col_w,
            h=btn_h,
            label="Back to Main Menu",
            on_click=on_back_to_menu,
        )
        self._btn_quit = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=right_x,
            y=y0 - row_step * 3.0,
            w=col_w,
            h=btn_h,
            label="Quit",
            on_click=on_quit,
        )
        open_network_h = btn_h * 0.55
        open_network_y = max(theme.pad + open_network_h / 2.0, y0 - row_step * 4.0)
        self._open_network_checkbox = Checkbox.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=open_network_y,
            w=btn_w,
            h=open_network_h,
            label="Open To Network",
            checked=False,
            on_change=lambda checked: on_toggle_open_network(bool(checked)),
        )

        # Settings page (audio + keybinds).
        self._settings = PauseMenuSettingsSection(
            parent=self._tabs.page(1),
            theme=theme,
            page_h=page_h,
            width=btn_w,
            button_h=btn_h,
            on_rebind_noclip=on_rebind_noclip,
            on_master_volume_change=on_master_volume_change,
            on_sfx_volume_change=on_sfx_volume_change,
            on_back=self.show_main,
            master_volume=float(master_volume),
            sfx_volume=float(sfx_volume),
        )

        # Multiplayer page.
        input_h = 0.10
        label_y0 = page_h - theme.pad - theme.small_scale * 1.0
        self._host_label = DirectLabel(
            parent=self._tabs.page(2),
            text="Host/IP",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, label_y0),
        )
        self._host_input = TextInput.build(
            parent=self._tabs.page(2),
            theme=theme,
            x=btn_w / 2.0,
            y=label_y0 - input_h * 0.8,
            w=btn_w,
            h=input_h,
            initial="127.0.0.1",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._port_label = DirectLabel(
            parent=self._tabs.page(2),
            text="Port",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, label_y0 - input_h * 1.9),
        )
        self._port_input = TextInput.build(
            parent=self._tabs.page(2),
            theme=theme,
            x=btn_w / 2.0,
            y=label_y0 - input_h * 2.7,
            w=btn_w,
            h=input_h,
            initial="7777",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._connect_button = Button.build(
            parent=self._tabs.page(2),
            theme=theme,
            x=btn_w / 2.0,
            y=label_y0 - input_h * 4.2,
            w=btn_w,
            h=btn_h,
            label="Connect",
            on_click=lambda: on_connect_server(self.connect_host, self.connect_port),
        )
        self._disconnect_button = Button.build(
            parent=self._tabs.page(2),
            theme=theme,
            x=btn_w / 2.0,
            y=label_y0 - input_h * 5.45,
            w=btn_w,
            h=btn_h,
            label="Disconnect",
            on_click=on_disconnect_server,
        )
        self._multiplayer_back_button = Button.build(
            parent=self._tabs.page(2),
            theme=theme,
            x=btn_w / 2.0,
            y=theme.pad + btn_h / 2.0,
            w=btn_w,
            h=btn_h,
            label="Back",
            on_click=self.show_main,
        )

        # Feel Session page.
        feel_label_y0 = page_h - theme.pad - theme.small_scale * 1.0
        self._feel_route_label = DirectLabel(
            parent=self._tabs.page(3),
            text="Route",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, feel_label_y0),
        )
        self._feel_hint_label = DirectLabel(
            parent=self._tabs.page(3),
            text="Tip: press G in-game for quick Save+Export popup.",
            text_scale=theme.small_scale * 0.90,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(btn_w * 0.42, 0, feel_label_y0),
        )
        route_w = (btn_w / 3.0) - theme.gap
        route_y = feel_label_y0 - input_h * 0.70
        self._feel_route_a = Checkbox.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=(route_w * 0.5),
            y=route_y,
            w=route_w,
            h=input_h * 0.85,
            label="A",
            checked=True,
            on_change=lambda checked: self._on_feel_route_change("A", bool(checked)),
        )
        self._feel_route_b = Checkbox.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=(route_w * 1.5) + theme.gap,
            y=route_y,
            w=route_w,
            h=input_h * 0.85,
            label="B",
            checked=False,
            on_change=lambda checked: self._on_feel_route_change("B", bool(checked)),
        )
        self._feel_route_c = Checkbox.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=(route_w * 2.5) + (theme.gap * 2.0),
            y=route_y,
            w=route_w,
            h=input_h * 0.85,
            label="C",
            checked=False,
            on_change=lambda checked: self._on_feel_route_change("C", bool(checked)),
        )
        self._feel_feedback_label = DirectLabel(
            parent=self._tabs.page(3),
            text="Feedback",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, feel_label_y0 - input_h * 2.1),
        )
        self._feel_feedback_input = TextInput.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 2.9,
            w=btn_w,
            h=input_h,
            initial="",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        try:
            self._feel_feedback_input.entry["width"] = 96
        except Exception:
            pass
        try:
            self._feel_feedback_input.entry.guiItem.setMaxChars(800)
        except Exception:
            pass
        self._feel_export_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 4.4,
            w=btn_w,
            h=btn_h,
            label="Export Latest Replay",
            on_click=lambda: on_feel_export_latest(self.feel_route_tag, self.feel_feedback_text),
        )
        self._feel_apply_feedback_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 5.65,
            w=btn_w,
            h=btn_h,
            label="Apply Feedback Tuning",
            on_click=lambda: on_feel_apply_feedback(self.feel_route_tag, self.feel_feedback_text),
        )
        status_h = max(0.12, btn_h * 1.25)
        status_y = theme.pad + btn_h + theme.gap + 0.02
        self._feel_status_panel = DirectFrame(
            parent=self._tabs.page(3),
            frameColor=theme.panel2,
            relief=DGG.FLAT,
            frameSize=(0.0, btn_w, 0.0, status_h),
            pos=(0.0, 0.0, status_y),
        )
        self._feel_status = DirectLabel(
            parent=self._feel_status_panel,
            text="",
            text_scale=theme.small_scale * 0.95,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad * 0.65, 0.0, status_h * 0.33),
            text_wordwrap=26,
        )
        self._feel_back_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=theme.pad + btn_h / 2.0,
            w=btn_w,
            h=btn_h,
            label="Back",
            on_click=self.show_main,
        )

        self.show_main()
        self.root.hide()

    def show(self) -> None:
        self.root.show()
        self._hint.show()

    def hide(self) -> None:
        self.root.hide()
        self._hint.hide()
        self.set_keybind_status("")
        self.show_main()

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self._hint.destroy()
        except Exception:
            pass

    def show_main(self) -> None:
        self._tabs.select(
            0,
            active_color=self._theme.panel2,
            inactive_color=self._theme.panel,
            active_text_fg=self._theme.text,
            inactive_text_fg=self._theme.text_muted,
        )
        self.set_keybind_status("")

    def show_settings(self) -> None:
        self._tabs.select(
            1,
            active_color=self._theme.panel2,
            inactive_color=self._theme.panel,
            active_text_fg=self._theme.text,
            inactive_text_fg=self._theme.text_muted,
        )

    def show_keybindings(self) -> None:
        # Backward compatibility for callers/tests that still use the old name.
        self.show_settings()

    def show_multiplayer(self) -> None:
        self._tabs.select(
            2,
            active_color=self._theme.panel2,
            inactive_color=self._theme.panel,
            active_text_fg=self._theme.text,
            inactive_text_fg=self._theme.text_muted,
        )

    def show_feel_session(self) -> None:
        self._tabs.select(
            3,
            active_color=self._theme.panel2,
            inactive_color=self._theme.panel,
            active_text_fg=self._theme.text,
            inactive_text_fg=self._theme.text_muted,
        )
        self._set_feel_route_tag(self._feel_route_tag)

    def set_noclip_binding(self, key_name: str) -> None:
        self._settings.set_noclip_binding(key_name)

    def set_keybind_status(self, text: str) -> None:
        self._settings.set_status(text)

    def set_audio_levels(self, *, master_volume: float, sfx_volume: float) -> None:
        self._settings.set_master_volume(master_volume)
        self._settings.set_sfx_volume(sfx_volume)

    def set_open_to_network(self, value: bool) -> None:
        self._open_network_checkbox.set_checked(bool(value))

    @property
    def connect_host(self) -> str:
        try:
            return str(self._host_input.entry.get()).strip()
        except Exception:
            return ""

    @property
    def connect_port(self) -> str:
        try:
            return str(self._port_input.entry.get()).strip()
        except Exception:
            return ""

    def set_connect_target(self, host: str, port: int) -> None:
        try:
            self._host_input.entry.enterText(str(host))
        except Exception:
            pass
        try:
            self._port_input.entry.enterText(str(int(port)))
        except Exception:
            pass

    def set_multiplayer_status(self, text: str) -> None:
        self._multiplayer_status["text"] = str(text)

    def set_feel_status(self, text: str) -> None:
        self._feel_status["text"] = str(text)

    @property
    def feel_route_tag(self) -> str:
        return str(self._feel_route_tag)

    @property
    def feel_feedback_text(self) -> str:
        try:
            return str(self._feel_feedback_input.entry.get()).strip()
        except Exception:
            return ""

    def set_feel_feedback_text(self, text: str) -> None:
        try:
            self._feel_feedback_input.entry.enterText(str(text))
        except Exception:
            pass

    def clear_feel_feedback(self) -> None:
        self.set_feel_feedback_text("")

    def _set_feel_route_tag(self, tag: str) -> None:
        t = str(tag or "").strip().upper()
        if t not in {"A", "B", "C"}:
            t = "A"
        self._feel_route_tag = t
        self._feel_route_a.set_checked(t == "A")
        self._feel_route_b.set_checked(t == "B")
        self._feel_route_c.set_checked(t == "C")

    def _on_feel_route_change(self, tag: str, checked: bool) -> None:
        if not checked:
            # Keep radio semantics: one option always selected.
            self._set_feel_route_tag(self._feel_route_tag)
            return
        self._set_feel_route_tag(tag)
