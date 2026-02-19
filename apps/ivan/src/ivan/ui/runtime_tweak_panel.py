"""Schema-driven runtime tweak panel for RPG viewmodel tuning.

Reads/writes via typed console commands only. Supports COPY to clipboard
(Windows primary, graceful fallback).
"""

from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.numeric_control import NumericControl
from irun_ui_kit.widgets.panel import Panel
from irun_ui_kit.widgets.scrolled import Scrolled

from ivan.ui.clipboard import copy_to_clipboard
from ivan.ui.runtime_tweak_schema import (
    RPG_VIEWMODEL_FIELDS,
    build_console_script,
    parse_vm_rpg_state,
)


class RuntimeTweakPanel:
    """Schema-driven panel for runtime tuning via console commands."""

    def __init__(
        self,
        *,
        aspect2d,
        theme: Theme,
        execute_cmd: callable,
        on_close: callable,
    ) -> None:
        self._theme = theme
        self._execute_cmd = execute_cmd
        self._on_close = on_close
        self._state: dict[str, list[float]] = {}
        self._controls: dict[str, dict[str, NumericControl]] = {}  # key -> {component -> ctrl}

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        panel_w = min(1.85, max(1.40, aspect_ratio * 0.95))
        panel_h = 1.28
        left = -panel_w * 0.5
        bottom = -panel_h * 0.5

        self._panel = Panel.build(
            parent=aspect2d,
            theme=theme,
            x=left,
            y=bottom,
            w=panel_w,
            h=panel_h,
            title="Runtime Tweak (F10)",
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

        hint_y = content_h - theme.pad - theme.small_scale * 0.88
        hint = DirectLabel(
            parent=self._content,
            text="RPG viewmodel tuning via console commands. COPY exports script to clipboard.",
            text_scale=theme.small_scale * 0.88,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0.0, hint_y),
        )
        hint.setTransparency(True)

        btn_h = 0.10
        row_h = 0.11
        scroll_h = max(0.35, content_h - (hint_y - 0.02) - btn_h - theme.gap * 2)
        scroll_w = content_w - theme.pad * 2
        scroll_x = theme.pad
        scroll_y = theme.pad + btn_h + theme.gap

        self._scroll = Scrolled.build(
            parent=self._content,
            theme=theme,
            x=scroll_x,
            y=scroll_y,
            w=scroll_w,
            h=scroll_h,
            canvas_h=scroll_h,
        )
        try:
            self._scroll.frame.bind(DGG.WHEELUP, lambda _evt: self._scroll.scroll_wheel(+1))
            self._scroll.frame.bind(DGG.WHEELDOWN, lambda _evt: self._scroll.scroll_wheel(-1))
        except Exception:
            pass

        scroll_content_w = self._scroll.content_w()
        x0 = theme.pad
        row_w = scroll_content_w - theme.pad * 2
        y_cursor = scroll_h - theme.pad - row_h

        for spec in RPG_VIEWMODEL_FIELDS:
            comp_controls: dict[str, NumericControl] = {}
            for i, comp in enumerate(spec.components):
                label = f"{spec.label} [{comp}]" if len(spec.components) > 1 else spec.label
                ctrl = NumericControl.build(
                    parent=self._scroll.canvas,
                    theme=theme,
                    x=x0,
                    y=y_cursor,
                    w=row_w,
                    label=label,
                    value=0.0,
                    minimum=spec.min_val,
                    maximum=spec.max_val,
                    on_change=lambda val, s=spec, c=comp: self._on_value_change(s, c, float(val)),
                    normalized_slider=False,
                    normalized_entry=False,
                    precision=spec.precision,
                )
                comp_controls[comp] = ctrl
                y_cursor -= row_h
            self._controls[spec.key] = comp_controls

        canvas_total = max(scroll_h, -y_cursor + theme.pad)
        self._scroll.set_canvas_h(canvas_total)

        button_y = theme.pad + btn_h * 0.5
        footer_gap = theme.gap
        footer_w = (content_w - footer_gap * 2.0) / 3.0
        self._reset_button = Button.build(
            parent=self._content,
            theme=theme,
            x=footer_w * 0.5,
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Reset",
            on_click=self._on_reset,
        )
        self._copy_button = Button.build(
            parent=self._content,
            theme=theme,
            x=(footer_w * 1.5) + footer_gap,
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Copy",
            on_click=self._on_copy,
        )
        self._close_button = Button.build(
            parent=self._content,
            theme=theme,
            x=(footer_w * 2.5) + (footer_gap * 2.0),
            y=button_y,
            w=footer_w,
            h=btn_h,
            label="Close",
            on_click=self._on_close_click,
        )

        self._status = DirectLabel(
            parent=self._content,
            text="",
            text_scale=theme.small_scale * 0.90,
            text_align=TextNode.ALeft,
            text_fg=theme.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(theme.pad, 0.0, theme.pad * 0.5),
        )

        self.root.hide()

    def show(self) -> None:
        self.root.show()
        self._refresh_from_console()

    def hide(self) -> None:
        self.root.hide()

    def set_status(self, text: str) -> None:
        self._status["text"] = str(text)

    def scroll_wheel(self, direction: int) -> None:
        self._scroll.scroll_wheel(direction)

    def _refresh_from_console(self) -> None:
        """Execute vm_rpg_print and sync UI from parsed output."""
        result = self._execute_cmd("vm_rpg_print")
        lines = (
            list(result.out) if hasattr(result, "out") else (result if isinstance(result, list) else [])
        )
        self._state = parse_vm_rpg_state(lines)
        for spec in RPG_VIEWMODEL_FIELDS:
            vals = self._state.get(spec.key)
            if vals is None:
                continue
            for i, comp in enumerate(spec.components):
                if i < len(vals) and comp in self._controls.get(spec.key, {}):
                    self._controls[spec.key][comp].set_value(float(vals[i]), emit=False)

    def _on_value_change(self, spec, component: str, value: float) -> None:
        """User changed a value: build full vector and execute set command."""
        comp_controls = self._controls.get(spec.key, {})
        vals: list[float] = []
        for comp in spec.components:
            if comp == component:
                vals.append(value)
                continue
            ctrl = comp_controls.get(comp)
            if ctrl is not None:
                try:
                    raw = ctrl.entry.entry.get() if hasattr(ctrl, "entry") else "0"
                    v = float(str(raw).strip() or 0)
                except (ValueError, TypeError):
                    v = 0.0
                vals.append(max(spec.min_val, min(spec.max_val, v)))
            else:
                vals.append(0.0)

        cmd = self._build_set_command(spec, vals)
        if cmd:
            self._execute_cmd(cmd)
            self._state[spec.key] = vals

    def _build_set_command(self, spec, vals: list[float]) -> str:
        if spec.set_cmd == "vm_rpg_pos" and len(vals) >= 3:
            return f"vm_rpg_pos {vals[0]:.4f} {vals[1]:.4f} {vals[2]:.4f}"
        if spec.set_cmd == "vm_rpg_hpr" and len(vals) >= 3:
            return f"vm_rpg_hpr {vals[0]:.4f} {vals[1]:.4f} {vals[2]:.4f}"
        if spec.set_cmd == "vm_rpg_model_hpr" and len(vals) >= 3:
            return f"vm_rpg_model_hpr {vals[0]:.4f} {vals[1]:.4f} {vals[2]:.4f}"
        if spec.set_cmd == "vm_rpg_model_scale" and len(vals) >= 3:
            return f"vm_rpg_model_scale {vals[0]:.4f} {vals[1]:.4f} {vals[2]:.4f}"
        if spec.set_cmd == "vm_rpg_size" and vals:
            return f"vm_rpg_size {vals[0]:.4f}"
        return ""

    def _on_reset(self) -> None:
        self._execute_cmd("vm_rpg_reset")
        self._refresh_from_console()
        self.set_status("Reset to defaults.")

    def _on_copy(self) -> None:
        # Ensure state is current (refresh if needed)
        if not self._state:
            self._refresh_from_console()
        script = build_console_script(self._state)
        ok, msg = copy_to_clipboard(script)
        self.set_status("Copied to clipboard." if ok else msg)

    def _on_close_click(self) -> None:
        self._on_close()


__all__ = ["RuntimeTweakPanel"]
