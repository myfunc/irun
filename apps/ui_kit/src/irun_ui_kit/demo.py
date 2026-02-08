from __future__ import annotations

import argparse
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import loadPrcFileData

from irun_ui_kit.renderer import UIRenderer
from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.slider import Slider
from irun_ui_kit.widgets.tabs import Tabs
from irun_ui_kit.widgets.text_input import TextInput


class DemoApp(ShowBase):
    def __init__(self, *, smoke_screenshot: str | None) -> None:
        loadPrcFileData("", "win-size 1280 720")
        loadPrcFileData("", "window-title IRUN UI Kit Demo")
        loadPrcFileData("", "sync-video 1")
        loadPrcFileData("", "show-frame-rate-meter 0")
        super().__init__()
        self.disableMouse()

        theme = Theme()
        self.ui = UIRenderer(base=self, theme=theme)
        self.ui.set_background()

        aspect = float(self.getAspectRatio())
        win = self.ui.create_window(title="UI KIT PLAYGROUND", x=-aspect + 0.08, y=-0.92, w=2.95, h=1.84)

        # Layout: component tabs at top; each tab page contains a Preview panel and a Controls panel.
        content_w = 2.95
        content_h = 1.84 - (theme.header_h + (theme.outline_w * 2))

        tabs_x = theme.pad
        tabs_y = theme.pad
        tabs_w = content_w - (theme.pad * 2)
        tabs_tab_h = 0.10
        tabs_page_h = content_h - (theme.pad * 2) - tabs_tab_h

        top_tabs = Tabs.build(
            parent=win.content,
            theme=theme,
            x=tabs_x,
            y=tabs_y,
            w=tabs_w,
            tab_h=tabs_tab_h,
            page_h=tabs_page_h,
            labels=["Button", "TextInput", "Checkbox", "Slider"],
            active=0,
        )

        page_pad = theme.pad
        page_gap = theme.pad
        page_inner_w = tabs_w - (page_pad * 2)
        preview_w = page_inner_w * 0.60
        controls_w = page_inner_w - preview_w - page_gap
        panel_h = tabs_page_h - (page_pad * 2)

        def _panel_content(*, panel, has_header: bool = True):
            """
            Create a child container with a (0..w, 0..h) local coordinate space.
            This avoids having demo code accidentally destroy the Panel's header/outline nodes.
            """

            x0 = theme.outline_w + theme.pad
            y0 = theme.outline_w + theme.pad
            header_h = theme.header_h if has_header else 0.0
            cw = panel.w - (theme.outline_w * 2) - (theme.pad * 2)
            ch = panel.h - (theme.outline_w * 2) - header_h - (theme.pad * 2)
            if cw < 0.05:
                cw = 0.05
            if ch < 0.05:
                ch = 0.05
            return DirectFrame(
                parent=panel.node,
                frameColor=(0, 0, 0, 0),
                relief=DGG.FLAT,
                frameSize=(0.0, cw, 0.0, ch),
                pos=(x0, 0, y0),
            )

        # One controls panel per component page. Each panel uses its own tabs to hide/show control groups.
        def _build_controls_panel(*, parent, title: str):
            # A simple container panel in local coordinates.
            from irun_ui_kit.widgets.panel import Panel

            p = Panel.build(
                parent=parent,
                theme=theme,
                x=page_pad + preview_w + page_gap,
                y=page_pad,
                w=controls_w,
                h=panel_h,
                title=title,
                header=True,
            )
            content = _panel_content(panel=p, has_header=True)
            cw = float(content["frameSize"][1])
            ch = float(content["frameSize"][3])

            t = Tabs.build(
                parent=content,
                theme=theme,
                x=0.0,
                y=0.0,
                w=cw,
                tab_h=0.09,
                page_h=ch - 0.09,
                labels=["Props", "Layout", "Theme"],
                active=0,
            )
            return (p, content, t)

        def _build_preview_panel(*, parent, title: str):
            from irun_ui_kit.widgets.panel import Panel

            p = Panel.build(
                parent=parent,
                theme=theme,
                x=page_pad,
                y=page_pad,
                w=preview_w,
                h=panel_h,
                title=title,
                header=True,
            )
            content = _panel_content(panel=p, has_header=True)
            return (p, content)

        # --- Button page ---
        btn_page = top_tabs.page(0)
        btn_preview, btn_preview_content = _build_preview_panel(parent=btn_page, title="Preview")
        btn_controls_panel, btn_controls_content, btn_controls_tabs = _build_controls_panel(parent=btn_page, title="Controls")

        state = {
            "button_label": "Primary Button",
            "button_w": 1.20,
            "button_h": 0.12,
            "button_disabled": False,
            "button_color": theme.panel2,
        }

        def _render_button_preview() -> None:
            # Clear and rebuild preview contents to reflect new props.
            try:
                for c in btn_preview_content.getChildren():
                    c.removeNode()
            except Exception:
                pass
            cw = float(btn_preview_content["frameSize"][1])
            ch = float(btn_preview_content["frameSize"][3])
            Button.build(
                parent=btn_preview_content,
                theme=theme,
                x=cw / 2,
                y=ch / 2,
                w=float(state["button_w"]),
                h=float(state["button_h"]),
                label=str(state["button_label"]),
                frame_color=state["button_color"],
                disabled=bool(state["button_disabled"]),
                on_click=lambda: None,
            )

        def _controls_geometry() -> tuple[float, float]:
            cw = float(btn_controls_content["frameSize"][1])
            ch = float(btn_controls_content["frameSize"][3])
            return (cw, ch)

        cw, ch = _controls_geometry()
        col_w = cw
        row0 = ch - 0.18
        row1 = ch - 0.36

        # Props tab
        TextInput.build(
            parent=btn_controls_tabs.page(0),
            theme=theme,
            x=col_w / 2,
            y=row0,
            w=col_w - 0.18,
            h=0.11,
            initial=state["button_label"],
            on_submit=lambda text: (state.__setitem__("button_label", text), _render_button_preview()),
        )
        Checkbox.build(
            parent=btn_controls_tabs.page(0),
            theme=theme,
            x=col_w / 2,
            y=row1,
            w=col_w - 0.18,
            h=0.11,
            label="Disabled",
            checked=state["button_disabled"],
            on_change=lambda v: (state.__setitem__("button_disabled", v), _render_button_preview()),
        )
        # Layout tab
        Slider.build(
            parent=btn_controls_tabs.page(1),
            theme=theme,
            x=col_w / 2,
            y=row0,
            w=col_w - 0.18,
            label="Width",
            min_value=0.60,
            max_value=1.40,
            value=state["button_w"],
            on_change=lambda v: (state.__setitem__("button_w", v), _render_button_preview()),
        )
        Slider.build(
            parent=btn_controls_tabs.page(1),
            theme=theme,
            x=col_w / 2,
            y=row1,
            w=col_w - 0.18,
            label="Height",
            min_value=0.08,
            max_value=0.22,
            value=state["button_h"],
            on_change=lambda v: (state.__setitem__("button_h", v), _render_button_preview()),
        )
        # Theme tab
        Button.build(
            parent=btn_controls_tabs.page(2),
            theme=theme,
            x=col_w / 2,
            y=row0,
            w=col_w - 0.18,
            h=0.11,
            label="Use panel2",
            frame_color=theme.panel2,
            on_click=lambda: (state.__setitem__("button_color", theme.panel2), _render_button_preview()),
        )
        Button.build(
            parent=btn_controls_tabs.page(2),
            theme=theme,
            x=col_w / 2,
            y=row1,
            w=col_w - 0.18,
            h=0.11,
            label="Use danger",
            frame_color=theme.danger,
            on_click=lambda: (state.__setitem__("button_color", theme.danger), _render_button_preview()),
        )

        _render_button_preview()

        # --- TextInput page ---
        ti_page = top_tabs.page(1)
        ti_preview, ti_preview_content = _build_preview_panel(parent=ti_page, title="Preview")
        ti_controls_panel, ti_controls_content, ti_controls_tabs = _build_controls_panel(parent=ti_page, title="Controls")
        ti_cw = float(ti_preview_content["frameSize"][1])
        ti_ch = float(ti_preview_content["frameSize"][3])
        TextInput.build(
            parent=ti_preview_content,
            theme=theme,
            x=ti_cw / 2,
            y=ti_ch / 2,
            w=min(ti_cw, preview_w) - 0.10,
            h=0.11,
            initial="Type and press Enter...",
            on_submit=lambda _t: None,
        )
        # Keep controls sparse for now; the tabs still demonstrate group visibility.
        Checkbox.build(
            parent=ti_controls_tabs.page(0),
            theme=theme,
            x=float(ti_controls_content["frameSize"][1]) / 2,
            y=float(ti_controls_content["frameSize"][3]) - 0.18,
            w=float(ti_controls_content["frameSize"][1]) - 0.18,
            h=0.11,
            label="(Placeholder) Disabled",
            checked=False,
            on_change=lambda _v: None,
            disabled=True,
        )

        # --- Checkbox page ---
        cb_page = top_tabs.page(2)
        cb_preview, cb_preview_content = _build_preview_panel(parent=cb_page, title="Preview")
        cb_controls_panel, cb_controls_content, cb_controls_tabs = _build_controls_panel(parent=cb_page, title="Controls")
        cb_cw = float(cb_preview_content["frameSize"][1])
        cb_ch = float(cb_preview_content["frameSize"][3])
        Checkbox.build(
            parent=cb_preview_content,
            theme=theme,
            x=cb_cw / 2,
            y=cb_ch / 2,
            w=cb_cw - 0.10,
            h=0.11,
            label="Enable something",
            checked=True,
            on_change=lambda _v: None,
        )
        Checkbox.build(
            parent=cb_controls_tabs.page(0),
            theme=theme,
            x=float(cb_controls_content["frameSize"][1]) / 2,
            y=float(cb_controls_content["frameSize"][3]) - 0.18,
            w=float(cb_controls_content["frameSize"][1]) - 0.18,
            h=0.11,
            label="(No extra props yet)",
            checked=False,
            on_change=lambda _v: None,
            disabled=True,
        )

        # --- Slider page ---
        sl_page = top_tabs.page(3)
        sl_preview, sl_preview_content = _build_preview_panel(parent=sl_page, title="Preview")
        sl_controls_panel, sl_controls_content, sl_controls_tabs = _build_controls_panel(parent=sl_page, title="Controls")
        sl_cw = float(sl_preview_content["frameSize"][1])
        sl_ch = float(sl_preview_content["frameSize"][3])
        Slider.build(
            parent=sl_preview_content,
            theme=theme,
            x=sl_cw / 2,
            y=sl_ch / 2,
            w=sl_cw - 0.10,
            label="Volume",
            min_value=0.0,
            max_value=1.0,
            value=0.50,
            on_change=lambda _v: None,
        )
        Checkbox.build(
            parent=sl_controls_tabs.page(0),
            theme=theme,
            x=float(sl_controls_content["frameSize"][1]) / 2,
            y=float(sl_controls_content["frameSize"][3]) - 0.18,
            w=float(sl_controls_content["frameSize"][1]) - 0.18,
            h=0.11,
            label="(No extra props yet)",
            checked=False,
            on_change=lambda _v: None,
            disabled=True,
        )

        self.accept("escape", self.userExit)
        self.accept("q", self.userExit)

        if smoke_screenshot:
            out = Path(smoke_screenshot).expanduser()
            self.taskMgr.doMethodLater(0.2, self._smoke, "smoke", extraArgs=[out], appendTask=True)

    def _smoke(self, out: Path, task):
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(str(out))
        finally:
            self.userExit()
        return task.done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-screenshot", default=None)
    args = ap.parse_args()
    DemoApp(smoke_screenshot=args.smoke_screenshot).run()


if __name__ == "__main__":
    main()
