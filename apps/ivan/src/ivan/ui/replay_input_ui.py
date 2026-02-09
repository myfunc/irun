from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.panel import Panel


class ReplayInputUI:
    """
    Replay-only input visualizer.

    Shows a compact "movement diamond" style indicator plus dedicated sections
    for jump, crouch, and mouse direction.
    """

    def __init__(self, *, aspect2d, theme: Theme) -> None:
        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        w = min(1.45, (aspect_ratio * 2.0) - 0.16)
        h = 0.50
        x = -w / 2.0
        y = -0.97

        self._theme = theme
        self._panel = Panel.build(
            parent=aspect2d,
            theme=theme,
            x=x,
            y=y,
            w=w,
            h=h,
            title="Replay Input",
            header=True,
        )
        self._root = self._panel.node
        self._root["state"] = DGG.DISABLED

        # Content local coordinates: origin at panel bottom-left.
        # Place a "diamond-like" cluster left, and vertical status sections right.
        self._move_origin_x = 0.07
        self._move_origin_y = 0.10
        self._move_w = 0.78
        self._move_h = 0.30

        self._inactive = (0.22, 0.20, 0.17, 0.95)
        self._active_lr = (0.96, 0.67, 0.17, 0.98)
        self._active_fwd = (0.10, 0.85, 0.10, 0.98)
        self._active_back = (0.90, 0.15, 0.15, 0.98)

        self._move_left = self._box(
            x=self._move_origin_x,
            y=self._move_origin_y,
            w=0.28,
            h=self._move_h,
            color=self._inactive,
            text="<",
        )
        self._move_center_top = self._box(
            x=self._move_origin_x + 0.30,
            y=self._move_origin_y + (self._move_h * 0.50),
            w=0.18,
            h=self._move_h * 0.50,
            color=self._inactive,
            text="W",
        )
        self._move_center_bottom = self._box(
            x=self._move_origin_x + 0.30,
            y=self._move_origin_y,
            w=0.18,
            h=self._move_h * 0.50,
            color=self._inactive,
            text="S",
        )
        self._move_right = self._box(
            x=self._move_origin_x + 0.50,
            y=self._move_origin_y,
            w=0.28,
            h=self._move_h,
            color=self._inactive,
            text=">",
        )
        self._label(
            x=self._move_origin_x,
            y=self._move_origin_y + self._move_h + 0.03,
            text="Movement",
            scale=theme.small_scale,
            fg=theme.text_muted,
        )

        # Separate sections for jump/crouch/mouse.
        sx = self._move_origin_x + self._move_w + 0.08
        self._jump_box = self._box(
            x=sx,
            y=self._move_origin_y + 0.20,
            w=0.24,
            h=0.10,
            color=self._inactive,
            text="JUMP",
            text_scale=theme.small_scale,
        )
        self._crouch_box = self._box(
            x=sx,
            y=self._move_origin_y + 0.08,
            w=0.24,
            h=0.10,
            color=self._inactive,
            text="CROUCH",
            text_scale=theme.small_scale,
        )
        self._label(x=sx, y=self._move_origin_y + self._move_h + 0.03, text="Actions", scale=theme.small_scale, fg=theme.text_muted)

        mx = sx + 0.28
        my = self._move_origin_y + 0.05
        self._mouse_u = self._box(x=mx + 0.06, y=my + 0.16, w=0.10, h=0.08, color=self._inactive, text="U", text_scale=theme.small_scale)
        self._mouse_l = self._box(x=mx, y=my + 0.08, w=0.10, h=0.08, color=self._inactive, text="L", text_scale=theme.small_scale)
        self._mouse_r = self._box(x=mx + 0.12, y=my + 0.08, w=0.10, h=0.08, color=self._inactive, text="R", text_scale=theme.small_scale)
        self._mouse_d = self._box(x=mx + 0.06, y=my, w=0.10, h=0.08, color=self._inactive, text="D", text_scale=theme.small_scale)
        self._mouse_delta = self._label(x=mx, y=my - 0.03, text="dx 0 | dy 0", scale=theme.small_scale * 0.92, fg=theme.text_muted)
        self._label(x=mx, y=self._move_origin_y + self._move_h + 0.03, text="Mouse", scale=theme.small_scale, fg=theme.text_muted)

        self._root.hide()
        self._visible = False

    def _box(
        self,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        color: tuple[float, float, float, float],
        text: str,
        text_scale: float | None = None,
    ):
        frame = DirectFrame(
            parent=self._panel.content,
            frameColor=self._theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, w, 0.0, h),
            pos=(x, 0.0, y),
        )
        frame["state"] = DGG.DISABLED
        inner = DirectFrame(
            parent=frame,
            frameColor=color,
            relief=DGG.FLAT,
            frameSize=(self._theme.outline_w, w - self._theme.outline_w, self._theme.outline_w, h - self._theme.outline_w),
        )
        inner["state"] = DGG.DISABLED
        DirectLabel(
            parent=frame,
            text=text,
            text_scale=float(text_scale if text_scale is not None else self._theme.label_scale),
            text_align=TextNode.ACenter,
            text_fg=self._theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(w * 0.50, 0.0, h * 0.48),
        )["state"] = DGG.DISABLED
        return inner

    def _label(self, *, x: float, y: float, text: str, scale: float, fg):
        return DirectLabel(
            parent=self._panel.content,
            text=str(text),
            text_scale=float(scale),
            text_align=TextNode.ALeft,
            text_fg=fg,
            frameColor=(0, 0, 0, 0),
            pos=(x, 0.0, y),
        )

    def show(self) -> None:
        self._visible = True
        self._root.show()

    def hide(self) -> None:
        self._visible = False
        self._root.hide()

    def is_visible(self) -> bool:
        return self._visible

    def set_input(
        self,
        *,
        move_forward: int,
        move_right: int,
        jump_pressed: bool,
        jump_held: bool,
        crouch_held: bool,
        look_dx: int,
        look_dy: int,
    ) -> None:
        # Movement cluster.
        self._move_left["frameColor"] = self._active_lr if int(move_right) < 0 else self._inactive
        self._move_right["frameColor"] = self._active_lr if int(move_right) > 0 else self._inactive
        self._move_center_top["frameColor"] = self._active_fwd if int(move_forward) > 0 else self._inactive
        self._move_center_bottom["frameColor"] = self._active_back if int(move_forward) < 0 else self._inactive

        # Action sections.
        jump_on = bool(jump_pressed) or bool(jump_held)
        self._jump_box["frameColor"] = self._active_fwd if jump_on else self._inactive
        self._crouch_box["frameColor"] = self._active_back if bool(crouch_held) else self._inactive

        # Mouse direction section.
        self._mouse_l["frameColor"] = self._active_lr if int(look_dx) < 0 else self._inactive
        self._mouse_r["frameColor"] = self._active_lr if int(look_dx) > 0 else self._inactive
        self._mouse_u["frameColor"] = self._active_fwd if int(look_dy) < 0 else self._inactive
        self._mouse_d["frameColor"] = self._active_back if int(look_dy) > 0 else self._inactive
        self._mouse_delta["text"] = f"dx {int(look_dx)} | dy {int(look_dy)}"
