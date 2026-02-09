from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.tabs import Tabs
from irun_ui_kit.widgets.text_input import TextInput


class PauseMenuUI:
    """In-game ESC menu with navigation actions and key binding controls."""

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
        on_open_keybindings,
        on_rebind_noclip,
        on_toggle_open_network,
        on_connect_server,
        on_disconnect_server,
        on_feel_export_latest,
        on_feel_compare_latest,
        on_feel_apply_feedback,
    ) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        panel_top = 0.95
        panel_bottom = -0.70
        panel_width = 0.88
        right = aspect_ratio - 0.02
        left = right - panel_width

        w = panel_width
        h = panel_top - panel_bottom
        self._theme = theme

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
            pos=(-aspect_ratio + 0.06, 0, 0.93),
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
            labels=["Menu", "Key Bindings", "Multiplayer", "Feel Session"],
            active=0,
        )

        self._keybind_status = DirectLabel(
            parent=self._tabs.page(1),
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, theme.pad),
            text_wordwrap=22,
        )
        self._noclip_bind_label = DirectLabel(
            parent=self._tabs.page(1),
            text="Current noclip key: V",
            text_scale=theme.label_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, page_h - theme.pad - theme.label_scale * 0.9),
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
        self._feel_status = DirectLabel(
            parent=self._tabs.page(3),
            text="",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, theme.pad),
            text_wordwrap=22,
        )

        btn_h = 0.13
        btn_w = content_w

        # Main page buttons (stacked).
        y0 = page_h - theme.pad - btn_h / 2.0
        gap = theme.gap + 0.03
        self._btn_resume = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0,
            w=btn_w,
            h=btn_h,
            label="Resume",
            on_click=on_resume,
        )
        self._btn_map_selector = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - gap - btn_h,
            w=btn_w,
            h=btn_h,
            label="Map Selector",
            on_click=on_map_selector,
        )

        def _open_keys() -> None:
            on_open_keybindings()
            self.show_keybindings()

        self._btn_keybindings = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 2,
            w=btn_w,
            h=btn_h,
            label="Key Bindings",
            on_click=_open_keys,
        )
        self._btn_replays = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 3,
            w=btn_w,
            h=btn_h,
            label="Replays",
            on_click=on_open_replays,
        )
        self._btn_multiplayer = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 4,
            w=btn_w,
            h=btn_h,
            label="Multiplayer",
            on_click=self.show_multiplayer,
        )
        self._btn_feel = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 5,
            w=btn_w,
            h=btn_h,
            label="Feel Session",
            on_click=lambda: (on_open_feel_session(), self.show_feel_session()),
        )
        self._btn_back_to_menu = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 6,
            w=btn_w,
            h=btn_h,
            label="Back to Main Menu",
            on_click=on_back_to_menu,
        )
        self._btn_quit = Button.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=y0 - (gap + btn_h) * 7,
            w=btn_w,
            h=btn_h,
            label="Quit",
            on_click=on_quit,
        )
        self._open_network_checkbox = Checkbox.build(
            parent=self._tabs.page(0),
            theme=theme,
            x=btn_w / 2.0,
            y=max(theme.pad + 0.06, y0 - (gap + btn_h) * 7.7),
            w=btn_w,
            h=btn_h * 0.55,
            label="Open To Network",
            checked=False,
            on_change=lambda checked: on_toggle_open_network(bool(checked)),
        )

        # Key bindings page.
        self._noclip_bind_button = Button.build(
            parent=self._tabs.page(1),
            theme=theme,
            x=btn_w / 2.0,
            y=page_h - theme.pad - btn_h / 2.0 - theme.label_scale * 1.3,
            w=btn_w,
            h=btn_h,
            label="Rebind Noclip Toggle",
            on_click=on_rebind_noclip,
        )
        self._keys_back_button = Button.build(
            parent=self._tabs.page(1),
            theme=theme,
            x=btn_w / 2.0,
            y=theme.pad + btn_h / 2.0,
            w=btn_w,
            h=btn_h,
            label="Back",
            on_click=self.show_main,
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
            text="Route tag (A/B/C)",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, feel_label_y0),
        )
        self._feel_route_input = TextInput.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 0.8,
            w=btn_w,
            h=input_h,
            initial="A",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._feel_feedback_label = DirectLabel(
            parent=self._tabs.page(3),
            text="Feedback",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, feel_label_y0 - input_h * 1.9),
        )
        self._feel_feedback_input = TextInput.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 2.7,
            w=btn_w,
            h=input_h,
            initial="",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._feel_export_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 4.2,
            w=btn_w,
            h=btn_h,
            label="Export Latest Replay",
            on_click=lambda: on_feel_export_latest(self.feel_route_tag),
        )
        self._feel_compare_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 5.45,
            w=btn_w,
            h=btn_h,
            label="Compare Latest vs Previous",
            on_click=lambda: on_feel_compare_latest(self.feel_route_tag),
        )
        self._feel_apply_feedback_button = Button.build(
            parent=self._tabs.page(3),
            theme=theme,
            x=btn_w / 2.0,
            y=feel_label_y0 - input_h * 6.7,
            w=btn_w,
            h=btn_h,
            label="Apply Feedback Tuning",
            on_click=lambda: on_feel_apply_feedback(self.feel_route_tag, self.feel_feedback_text),
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

    def show_keybindings(self) -> None:
        self._tabs.select(
            1,
            active_color=self._theme.panel2,
            inactive_color=self._theme.panel,
            active_text_fg=self._theme.text,
            inactive_text_fg=self._theme.text_muted,
        )

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

    def set_noclip_binding(self, key_name: str) -> None:
        self._noclip_bind_label["text"] = f"Current noclip key: {str(key_name).upper()}"

    def set_keybind_status(self, text: str) -> None:
        self._keybind_status["text"] = str(text)

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
        try:
            return str(self._feel_route_input.entry.get()).strip()
        except Exception:
            return ""

    @property
    def feel_feedback_text(self) -> str:
        try:
            return str(self._feel_feedback_input.entry.get()).strip()
        except Exception:
            return ""
