from __future__ import annotations

"""
Interactive UI passport prototype (standalone).

Note: We render on `aspect2d` (not `pixel2d`) because DirectGUI behaves most reliably there.
All sizes are computed in aspect2d units so nothing explodes at different window sizes.

Run with the Ivan venv (Panda3D installed there):
  /Users/myfunc/myprojects/irun/apps/ivan/.venv/bin/python /Users/myfunc/myprojects/irun/ui-passports/run_prototype.py
"""

from dataclasses import dataclass
import argparse
from pathlib import Path

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectEntry, DirectFrame, DirectLabel, DirectOptionMenu, DirectSlider
from direct.showbase import ShowBaseGlobal
from direct.showbase.ShowBase import ShowBase
from panda3d.core import TextNode, loadPrcFileData


@dataclass(frozen=True)
class Theme:
    # ps2_cyan-ish
    bg: tuple[float, float, float, float] = (0.06, 0.06, 0.07, 1.0)
    panel: tuple[float, float, float, float] = (0.16, 0.16, 0.18, 0.98)
    panel2: tuple[float, float, float, float] = (0.22, 0.22, 0.25, 0.98)
    outline: tuple[float, float, float, float] = (0.55, 0.56, 0.59, 1.0)
    header: tuple[float, float, float, float] = (0.00, 0.90, 0.92, 1.0)
    text: tuple[float, float, float, float] = (236 / 255, 238 / 255, 244 / 255, 1.0)
    text_muted: tuple[float, float, float, float] = (170 / 255, 175 / 255, 188 / 255, 1.0)
    ink: tuple[float, float, float, float] = (0.06, 0.06, 0.08, 1.0)
    danger: tuple[float, float, float, float] = (255 / 255, 86 / 255, 120 / 255, 1.0)


@dataclass(frozen=True)
class Panel:
    node: DirectFrame
    w: float
    h: float
    header_h: float
    inner_pad: float


class PrototypeApp(ShowBase):
    def __init__(self, *, smoke_screenshot: str | None, win_w: int, win_h: int) -> None:
        loadPrcFileData("", f"win-size {int(win_w)} {int(win_h)}")
        loadPrcFileData("", "window-title IRUN UI Passport Prototype")
        loadPrcFileData("", "sync-video 1")
        loadPrcFileData("", "show-frame-rate-meter 0")

        super().__init__()
        self.disableMouse()

        self.t = Theme()
        self.setBackgroundColor(*self.t.bg)

        self._list_selected = 2
        self._list_buttons: list[DirectButton] = []
        self._checkbox_checked = False
        self._checkbox_mark: DirectLabel | None = None
        self._slider: DirectSlider | None = None
        self._slider_value: DirectLabel | None = None
        self._status: DirectLabel | None = None
        self._dropdown_values = ["surf_bhop", "bhop", "surf", "classic"]
        self._dropdown_idx = 0
        self._dropdown_btn: DirectButton | None = None

        self._build()
        if smoke_screenshot:
            out = Path(smoke_screenshot).expanduser()
            self.taskMgr.doMethodLater(0.2, self._smoke, "smoke-shot", extraArgs=[out], appendTask=True)
        self.accept("escape", self.userExit)
        self.accept("q", self.userExit)

    def _smoke(self, out: Path, task):
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            # Ensure at least one frame has been rendered.
            self.graphicsEngine.renderFrame()
            self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(str(out))
        finally:
            self.userExit()
        return task.done

    def _aspect_ratio(self) -> float:
        if getattr(ShowBaseGlobal, "base", None) is None:
            return 16 / 9
        return float(ShowBaseGlobal.base.getAspectRatio())

    def _set_status(self, msg: str) -> None:
        if self._status is not None:
            self._status["text"] = msg

    def _repaint_list(self) -> None:
        for i, b in enumerate(self._list_buttons):
            label = b["text"][0].lstrip("> ").strip()
            if i == self._list_selected:
                b["text"] = ("> " + label,) * 4
                b["frameColor"] = (self.t.panel2, self.t.panel2, self.t.header, self.t.panel2)
            else:
                b["text"] = (label,) * 4
                b["frameColor"] = (self.t.panel2, self.t.panel2, self.t.panel2, self.t.panel2)

    def _on_list(self, idx: int) -> None:
        self._list_selected = int(idx)
        self._repaint_list()
        self._set_status(f"Selected: {idx}")

    def _toggle_checkbox(self) -> None:
        self._checkbox_checked = not self._checkbox_checked
        if self._checkbox_mark is not None:
            self._checkbox_mark["text"] = "X" if self._checkbox_checked else ""
        self._set_status(f"VSync: {'ON' if self._checkbox_checked else 'OFF'}")

    def _on_slider(self) -> None:
        if self._slider is None:
            return
        try:
            v = float(self._slider["value"])
        except Exception:
            return
        vi = int(round(v))
        if self._slider_value is not None:
            self._slider_value["text"] = str(vi)
        self._set_status(f"Sensitivity: {vi}")

    def _on_entry(self, text: str) -> None:
        self._set_status(f"Entry: {text}")

    def _on_profile(self, item: str) -> None:
        self._set_status(f"Profile: {item}")

    def _toggle_dropdown(self) -> None:
        self._dropdown_idx = (self._dropdown_idx + 1) % len(self._dropdown_values)
        if self._dropdown_btn is not None:
            v = self._dropdown_values[self._dropdown_idx]
            self._dropdown_btn["text"] = (v, v, v, v)
        self._set_status(f"Profile: {self._dropdown_values[self._dropdown_idx]}")

    def _panel(self, *, x0: float, x1: float, y0: float, y1: float, title: str) -> Panel:
        """
        Build a panel in aspect2d using LOCAL coordinates for children.

        We attach a container frame positioned at (x0, y0) and then use frameSize in [0..w, 0..h].
        This avoids mixing absolute coordinates into child frameSize/pos (the source of the huge overlays).
        """

        w = float(x1 - x0)
        h = float(y1 - y0)
        header_h = 0.085
        inner_pad = 0.010
        title_off_y = 0.060

        # Outline container at (x0, y0) with local 0..w / 0..h.
        out = DirectFrame(
            parent=self.aspect2d,
            frameColor=self.t.outline,
            frameSize=(0.0, w, 0.0, h),
            relief=DGG.FLAT,
            pos=(x0, 0, y0),
        )

        # Inner fill.
        inner = DirectFrame(
            parent=out,
            frameColor=self.t.panel,
            frameSize=(inner_pad, w - inner_pad, inner_pad, h - inner_pad),
            relief=DGG.FLAT,
        )

        # Header.
        DirectFrame(
            parent=inner,
            frameColor=self.t.header,
            frameSize=(inner_pad, w - inner_pad, (h - inner_pad - header_h), (h - inner_pad)),
            relief=DGG.FLAT,
        )
        DirectLabel(
            parent=inner,
            text=title,
            text_scale=0.052,
            text_align=TextNode.ALeft,
            text_fg=self.t.ink,
            frameColor=(0, 0, 0, 0),
            pos=(inner_pad + 0.035, 0, h - inner_pad - title_off_y),
        )
        return Panel(node=inner, w=w, h=h, header_h=header_h, inner_pad=inner_pad)

    def _btn(
        self,
        *,
        parent,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        frame_color,
        command,
        text_fg=None,
    ) -> DirectButton:
        text_scale = 0.045
        b = DirectButton(
            parent=parent,
            text=(label, label, label, label),
            text_scale=text_scale,
            text_align=TextNode.ALeft,
            # Baseline tweak: keep glyphs centered inside the button.
            text_pos=(-w / 2 + 0.05, -text_scale * 0.35),
            text_fg=text_fg or self.t.text,
            frameColor=frame_color,
            relief=DGG.FLAT,
            frameSize=(-w / 2, w / 2, -h / 2, h / 2),
            pos=(x, 0, y),
            command=command,
        )
        return b

    def _build(self) -> None:
        aspect = self._aspect_ratio()

        top = 0.94
        bottom = -0.88
        margin_x = 0.06
        left_margin = -aspect + margin_x
        right_margin = aspect - margin_x
        col_gap = 0.10
        left_w = (right_margin - left_margin - col_gap) * 0.49
        right_w = (right_margin - left_margin - col_gap) - left_w

        left = self._panel(
            x0=left_margin,
            x1=left_margin + left_w,
            y0=bottom,
            y1=top,
            title="WINDOW / LIST",
        )
        right = self._panel(
            x0=left_margin + left_w + col_gap,
            x1=right_margin,
            y0=bottom,
            y1=top,
            title="CONTROLS",
        )

        DirectLabel(
            parent=self.aspect2d,
            text="Click around. Esc/Q: quit.",
            text_scale=0.040,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(left_margin, 0, 0.985),
        )

        # Common panel padding in local coordinates.
        pad = 0.07

        # LEFT: list
        list_w = left.w - (pad * 2)
        list_h_btn = 0.115
        list_gap = 0.028
        list_x = left.w / 2.0
        y = left.h - left.header_h - pad - (list_h_btn / 2.0)
        step = list_h_btn + list_gap

        items = ["New Game", "Continue", "Map Selector", "Key Bindings", "Settings", "Quit"]
        for i, label in enumerate(items):
            b = self._btn(
                parent=left.node,
                x=list_x,
                y=y,
                w=list_w,
                h=list_h_btn,
                label=label,
                frame_color=self.t.panel2,
                command=self._on_list,
            )
            b["extraArgs"] = [i]
            self._list_buttons.append(b)
            y -= step
        self._repaint_list()

        # Tooltip (bottom, above status).
        status_h = 0.070
        tooltip_h = 0.170
        tooltip_w = list_w
        tooltip_x = left.w / 2.0
        tooltip_y = pad + status_h + (tooltip_h / 2.0) + 0.020
        tip = DirectFrame(
            parent=left.node,
            frameColor=self.t.panel2,
            relief=DGG.FLAT,
            frameSize=(-tooltip_w / 2, tooltip_w / 2, -tooltip_h / 2, tooltip_h / 2),
            pos=(tooltip_x, 0, tooltip_y),
        )
        DirectLabel(
            parent=tip,
            text="Tooltip: focused item help goes here.",
            text_scale=0.034,
            text_align=TextNode.ALeft,
            text_fg=self.t.text,
            frameColor=(0, 0, 0, 0),
            pos=(-tooltip_w / 2 + 0.03, 0, 0.04),
        )
        DirectLabel(
            parent=tip,
            text="Rule: anchored; doesn't overlap cursor.",
            text_scale=0.030,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(-tooltip_w / 2 + 0.03, 0, -0.04),
        )

        # Status bar (bottom).
        status_w = list_w
        status_x = left.w / 2.0
        status_y = pad + (status_h / 2.0)
        status = DirectFrame(
            parent=left.node,
            frameColor=self.t.panel2,
            relief=DGG.FLAT,
            frameSize=(-status_w / 2, status_w / 2, -status_h / 2, status_h / 2),
            pos=(status_x, 0, status_y),
        )
        self._status = DirectLabel(
            parent=status,
            text="Status: ready.",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(-status_w / 2 + 0.03, 0, -0.01),
        )

        # RIGHT: controls stack (all local coords)
        ctrl_w = right.w - (pad * 2)
        ctrl_x = right.w / 2.0
        ry = right.h - right.header_h - pad - (list_h_btn / 2.0)
        ctrl_step = list_h_btn + 0.040

        self._btn(
            parent=right.node,
            x=ctrl_x,
            y=ry,
            w=ctrl_w,
            h=list_h_btn,
            label="Primary",
            frame_color=self.t.panel2,
            command=lambda: self._set_status("Clicked: Primary"),
        )
        ry -= ctrl_step
        self._btn(
            parent=right.node,
            x=ctrl_x,
            y=ry,
            w=ctrl_w,
            h=list_h_btn,
            label="Danger",
            frame_color=self.t.danger,
            command=lambda: self._set_status("Clicked: Danger"),
        )
        ry -= ctrl_step

        # Checkbox row.
        DirectLabel(
            parent=right.node,
            text="Checkbox:",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(pad, 0, ry + 0.028),
        )
        cb = DirectButton(
            parent=right.node,
            text="",
            frameColor=self.t.panel2,
            relief=DGG.FLAT,
            frameSize=(-0.03, 0.03, -0.03, 0.03),
            pos=(pad + 0.30, 0, ry + 0.030),
            command=self._toggle_checkbox,
        )
        self._checkbox_mark = DirectLabel(
            parent=cb,
            text="",
            text_scale=0.050,
            text_align=TextNode.ACenter,
            text_fg=self.t.header,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.02),
        )
        DirectLabel(
            parent=right.node,
            text="VSync",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text,
            frameColor=(0, 0, 0, 0),
            pos=(pad + 0.38, 0, ry + 0.028),
        )
        ry -= 0.125

        # Slider row.
        DirectLabel(
            parent=right.node,
            text="Slider: sensitivity",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(pad, 0, ry + 0.028),
        )
        self._slider = DirectSlider(
            parent=right.node,
            range=(0, 100),
            value=66,
            pageSize=1,
            command=self._on_slider,
            thumb_frameColor=self.t.header,
            frameColor=self.t.panel2,
            relief=DGG.FLAT,
            frameSize=(-0.35, 0.35, -0.01, 0.01),
            pos=(pad + 0.72, 0, ry + 0.034),
        )
        self._slider_value = DirectLabel(
            parent=right.node,
            text="66",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text,
            frameColor=(0, 0, 0, 0),
            pos=(right.w - pad - 0.10, 0, ry + 0.028),
        )
        ry -= 0.125

        # Entry row (render as a non-editable field to avoid DirectEntry sizing oddities).
        DirectLabel(
            parent=right.node,
            text="Entry:",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(pad, 0, ry + 0.028),
        )
        self._btn(
            parent=right.node,
            x=ctrl_x,
            y=ry,
            w=ctrl_w,
            h=0.095,
            label="mouse_sensitivity = 0.11",
            frame_color=(0.92, 0.92, 0.92, 1.0),
            text_fg=(0.08, 0.08, 0.10, 1.0),
            command=lambda: self._set_status("Entry clicked (stub)"),
        )
        ry -= 0.125

        # Dropdown row (simple cycling button, avoids DirectOptionMenu popup overlap).
        DirectLabel(
            parent=right.node,
            text="Dropdown:",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=self.t.text_muted,
            frameColor=(0, 0, 0, 0),
            pos=(pad, 0, ry + 0.028),
        )
        v0 = self._dropdown_values[self._dropdown_idx]
        self._dropdown_btn = self._btn(
            parent=right.node,
            x=ctrl_x,
            y=ry,
            w=ctrl_w,
            h=0.095,
            label=v0,
            frame_color=self.t.panel2,
            command=self._toggle_dropdown,
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-screenshot", default=None)
    ap.add_argument("--win-size", default="1280x720")
    args = ap.parse_args()
    try:
        win_w_s, win_h_s = str(args.win_size).lower().split("x", 1)
        win_w, win_h = int(win_w_s), int(win_h_s)
    except Exception:
        win_w, win_h = 1280, 720
    PrototypeApp(smoke_screenshot=args.smoke_screenshot, win_w=win_w, win_h=win_h).run()


if __name__ == "__main__":
    main()
