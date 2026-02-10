from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.text_input import TextInput


class FeelCaptureUI:
    """Quick in-run popup for route-tagged replay capture/export."""

    def __init__(
        self,
        *,
        aspect2d,
        theme: Theme,
        on_export,
        on_export_apply,
        on_restore,
        on_close,
    ) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        self._theme = theme
        self._on_export = on_export
        self._on_export_apply = on_export_apply
        self._on_restore = on_restore
        self._on_close = on_close
        self._route_tag = "A"

        panel_w = min(1.90, max(1.50, aspect_ratio * 1.02))
        panel_h = 1.34
        left = -panel_w * 0.5
        bottom = -panel_h * 0.5

        self._panel = Panel.build(
            parent=aspect2d,
            theme=theme,
            x=left,
            y=bottom,
            w=panel_w,
            h=panel_h,
            title="Feel Capture",
            header=True,
        )
        self.root = self._panel.node

        header_total_h = theme.header_h + (theme.outline_w * 2)
        content_h = panel_h - header_total_h - theme.pad * 2
        content_w = panel_w - theme.pad * 2

        self._content = DirectFrame(
            parent=self._panel.content,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, content_w, 0.0, content_h),
            pos=(theme.pad, 0.0, theme.pad),
        )

        hint_y = content_h - theme.pad - theme.small_scale * 0.9
        hint = DirectLabel(
            parent=self._content,
            text="G: open capture | Enter: export | Apply auto-backs up tuning | Revert restores last backup",
            text_scale=theme.small_scale * 0.90,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0.0, hint_y),
        )
        hint.setTransparency(True)

        btn_h = 0.11
        input_h = 0.10

        route_label_y = hint_y - 0.10
        self._route_label = DirectLabel(
            parent=self._content,
            text="Route",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0.0, route_label_y),
        )

        route_gap = theme.gap
        route_w = (content_w - route_gap * 2.0) / 3.0
        route_y = route_label_y - 0.07
        self._route_a = Checkbox.build(
            parent=self._content,
            theme=theme,
            x=route_w * 0.5,
            y=route_y,
            w=route_w,
            h=input_h * 0.82,
            label="A",
            checked=True,
            on_change=lambda checked: self._on_route_change("A", bool(checked)),
        )
        self._route_b = Checkbox.build(
            parent=self._content,
            theme=theme,
            x=(route_w * 1.5) + route_gap,
            y=route_y,
            w=route_w,
            h=input_h * 0.82,
            label="B",
            checked=False,
            on_change=lambda checked: self._on_route_change("B", bool(checked)),
        )
        self._route_c = Checkbox.build(
            parent=self._content,
            theme=theme,
            x=(route_w * 2.5) + (route_gap * 2.0),
            y=route_y,
            w=route_w,
            h=input_h * 0.82,
            label="C",
            checked=False,
            on_change=lambda checked: self._on_route_change("C", bool(checked)),
        )

        half_gap = theme.gap
        half_w = (content_w - half_gap) * 0.5
        left_x = half_w * 0.5
        right_x = half_w + half_gap + half_w * 0.5

        meta_label_y = route_y - 0.13
        self._route_name_label = DirectLabel(
            parent=self._content,
            text="Route Name",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0.0, meta_label_y),
        )
        self._run_note_label = DirectLabel(
            parent=self._content,
            text="Run Notes",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(half_w + half_gap, 0.0, meta_label_y),
        )

        meta_input_y = meta_label_y - 0.075
        self._route_name_input = TextInput.build(
            parent=self._content,
            theme=theme,
            x=left_x,
            y=meta_input_y,
            w=half_w,
            h=input_h,
            initial="",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        self._run_note_input = TextInput.build(
            parent=self._content,
            theme=theme,
            x=right_x,
            y=meta_input_y,
            w=half_w,
            h=input_h,
            initial="",
            on_submit=lambda _text: None,
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        try:
            self._route_name_input.entry["width"] = 36
            self._route_name_input.entry.guiItem.setMaxChars(160)
        except Exception:
            pass
        try:
            self._run_note_input.entry["width"] = 36
            self._run_note_input.entry.guiItem.setMaxChars(800)
        except Exception:
            pass

        feedback_label_y = meta_input_y - 0.13
        self._feedback_label = DirectLabel(
            parent=self._content,
            text="Feedback (optional tuning prompt)",
            text_scale=theme.small_scale,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0.0, feedback_label_y),
        )
        feedback_input_y = feedback_label_y - 0.075
        self._feedback_input = TextInput.build(
            parent=self._content,
            theme=theme,
            x=content_w * 0.5,
            y=feedback_input_y,
            w=content_w,
            h=input_h,
            initial="",
            on_submit=lambda _text: self._trigger_export(),
            frame_color=theme.panel2,
            text_fg=theme.text,
        )
        try:
            self._feedback_input.entry["width"] = 78
            self._feedback_input.entry.guiItem.setMaxChars(800)
        except Exception:
            pass

        button_y = theme.pad + btn_h * 0.5
        status_h = max(0.10, btn_h * 0.95)
        status_y = button_y + btn_h * 0.75 + theme.gap
        self._status_panel = DirectFrame(
            parent=self._content,
            frameColor=theme.panel2,
            relief=DGG.FLAT,
            frameSize=(0.0, content_w, 0.0, status_h),
            pos=(0.0, 0.0, status_y),
        )
        self._status = DirectLabel(
            parent=self._status_panel,
            text="",
            text_scale=theme.small_scale * 0.92,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad * 0.65, 0.0, status_h * 0.34),
            text_wordwrap=max(26, int(content_w * 18.0)),
        )

        footer_gap = theme.gap
        footer_w = (content_w - footer_gap * 3.0) / 4.0
        self._export_button = Button.build(
            parent=self._content,
            theme=theme,
            x=footer_w * 0.5,
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Save + Export",
            on_click=self._trigger_export,
        )
        self._export_apply_button = Button.build(
            parent=self._content,
            theme=theme,
            x=(footer_w * 1.5) + footer_gap,
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Export + Apply",
            on_click=self._trigger_export_apply,
        )
        self._restore_button = Button.build(
            parent=self._content,
            theme=theme,
            x=(footer_w * 2.5) + (footer_gap * 2.0),
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Revert Last",
            on_click=self._trigger_restore,
        )
        self._close_button = Button.build(
            parent=self._content,
            theme=theme,
            x=(footer_w * 3.5) + (footer_gap * 3.0),
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Close",
            on_click=self._on_close,
        )

        self._set_route_tag(self._route_tag)
        self.root.hide()

    @property
    def visible(self) -> bool:
        try:
            return bool(self.root.isHidden() is False)
        except Exception:
            return False

    def show(self) -> None:
        self.root.show()
        try:
            self._feedback_input.entry.setFocus()
        except Exception:
            pass

    def hide(self) -> None:
        self.root.hide()

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

    @property
    def route_tag(self) -> str:
        return str(self._route_tag)

    @property
    def route_name(self) -> str:
        try:
            return str(self._route_name_input.entry.get()).strip()
        except Exception:
            return ""

    @property
    def run_note(self) -> str:
        try:
            return str(self._run_note_input.entry.get()).strip()
        except Exception:
            return ""

    @property
    def feedback_text(self) -> str:
        try:
            return str(self._feedback_input.entry.get()).strip()
        except Exception:
            return ""

    def set_status(self, text: str) -> None:
        self._status["text"] = str(text)

    def clear_feedback(self) -> None:
        try:
            self._feedback_input.entry.enterText("")
        except Exception:
            pass

    def _trigger_export(self) -> None:
        self._on_export(self.route_tag, self.route_name, self.run_note, self.feedback_text)

    def _trigger_export_apply(self) -> None:
        self._on_export_apply(self.route_tag, self.route_name, self.run_note, self.feedback_text)

    def _trigger_restore(self) -> None:
        self._on_restore()

    def _set_route_tag(self, tag: str) -> None:
        t = str(tag or "").strip().upper()
        if t not in {"A", "B", "C"}:
            t = "A"
        self._route_tag = t
        self._route_a.set_checked(t == "A")
        self._route_b.set_checked(t == "B")
        self._route_c.set_checked(t == "C")

    def _on_route_change(self, tag: str, checked: bool) -> None:
        if not checked:
            self._set_route_tag(self._route_tag)
            return
        self._set_route_tag(tag)


__all__ = ["FeelCaptureUI"]
