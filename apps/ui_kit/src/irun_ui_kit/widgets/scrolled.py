from __future__ import annotations

from dataclasses import dataclass

from direct.gui.DirectGui import DirectScrolledFrame
from direct.gui import DirectGuiGlobals as DGG
from direct.showbase import ShowBaseGlobal
from panda3d.core import MouseButton
from panda3d.core import KeyboardButton
from panda3d.core import NodePath

from irun_ui_kit.theme import Theme


@dataclass
class Scrolled:
    """
    Thin wrapper around DirectScrolledFrame with themed colors and a stable API.

    Coordinate system:
    - The returned canvas is a normal NodePath. Callers are responsible for laying out children.
    - We keep canvasSize in a conventional bottom-up range (0..canvas_h).
    """

    frame: DirectScrolledFrame
    canvas: NodePath
    w: float
    h: float
    canvas_h: float
    scrollbar_w: float
    _dragging: bool = False
    _drag_last_my: float = 0.0
    _drag_last_ptr_y: float = 0.0

    @staticmethod
    def build(
        *,
        parent,
        theme: Theme,
        x: float,
        y: float,
        w: float,
        h: float,
        canvas_h: float,
    ) -> "Scrolled":
        # Reserve space so content doesn't sit under the scrollbar.
        # (DirectScrolledFrame's built-in bar overlays the frame by default.)
        scrollbar_w = max(0.060, theme.pad * 1.40)
        content_w = max(0.01, float(w) - float(scrollbar_w))
        out = DirectScrolledFrame(
            parent=parent,
            frameColor=theme.panel,
            frameSize=(0.0, w, 0.0, h),
            canvasSize=(0.0, content_w, 0.0, max(h, canvas_h)),
            relief=DGG.FLAT,
            autoHideScrollBars=False,
            manageScrollBars=True,
            verticalScroll_frameColor=theme.panel2,
            verticalScroll_thumb_frameColor=theme.outline,
            verticalScroll_incButton_frameColor=theme.panel2,
            verticalScroll_decButton_frameColor=theme.panel2,
            pos=(x, 0, y),
        )
        canvas = out.getCanvas()
        try:
            out["verticalScroll_frameSize"] = (content_w, float(w), 0.0, float(h))
        except Exception:
            pass
        try:
            out.horizontalScroll.hide()
        except Exception:
            pass
        sc = Scrolled(
            frame=out,
            canvas=canvas,
            w=float(w),
            h=float(h),
            canvas_h=float(max(h, canvas_h)),
            scrollbar_w=float(scrollbar_w),
        )
        sc._bind_drag_capture()
        return sc

    def content_w(self) -> float:
        return max(0.01, float(self.w) - float(self.scrollbar_w))

    def _mouse_y(self) -> float | None:
        base = getattr(ShowBaseGlobal, "base", None)
        if base is None:
            return None
        if not base.mouseWatcherNode.hasMouse():
            return None
        return float(base.mouseWatcherNode.getMouse().getY())

    def _pointer_y(self) -> float | None:
        base = getattr(ShowBaseGlobal, "base", None)
        if base is None or getattr(base, "win", None) is None:
            return None
        try:
            if int(base.win.getNumPointers()) <= 0:
                return None
            p = base.win.getPointer(0)
            return float(p.getY())
        except Exception:
            return None

    def _set_bar_value(self, value01: float) -> None:
        v = max(0.0, min(1.0, float(value01)))
        try:
            # Prefer API call when available to ensure the scrolled frame updates its canvas transform.
            self.frame.verticalScroll.setValue(v)
            return
        except Exception:
            pass
        try:
            self.frame.verticalScroll["value"] = v
        except Exception:
            pass

    def _bind_drag_capture(self) -> None:
        """
        DirectGUI drag tracking is hover-scoped: scrollbar dragging can stop when the cursor leaves the widget.
        We add a small global-ish capture loop while the primary button is down.
        """

        def start(_evt=None) -> None:
            self._drag_start()

        def end(_evt=None) -> None:
            self._drag_end()

        # Don't bail out on any single bind failure. Panda3D builds vary in which sub-widgets are exposed.
        try:
            self.frame.verticalScroll.bind(DGG.B1PRESS, start)
        except Exception:
            pass
        try:
            self.frame.verticalScroll.bind(DGG.B1RELEASE, end)
        except Exception:
            pass

        # Best-effort: bind thumb/buttons if available in this Panda build.
        for name in ("thumb", "incButton", "decButton"):
            try:
                node = getattr(self.frame.verticalScroll, name)
            except Exception:
                node = None
            if node is None:
                continue
            try:
                node.bind(DGG.B1PRESS, start)
                node.bind(DGG.B1RELEASE, end)
            except Exception:
                pass

    def _drag_start(self) -> None:
        my = self._mouse_y()
        py = self._pointer_y()
        if my is None and py is None:
            return
        self._dragging = True
        self._drag_last_my = float(my or 0.0)
        self._drag_last_ptr_y = float(py or 0.0)
        self._ensure_drag_task()

    def _drag_end(self) -> None:
        self._dragging = False
        base = getattr(ShowBaseGlobal, "base", None)
        if base is None:
            return
        try:
            base.taskMgr.remove(f"ui-kit-scrolled-drag-{id(self)}")
        except Exception:
            pass

    def _ensure_drag_task(self) -> None:
        base = getattr(ShowBaseGlobal, "base", None)
        if base is None:
            return
        name = f"ui-kit-scrolled-drag-{id(self)}"
        if base.taskMgr.hasTaskNamed(name):
            return
        base.taskMgr.add(self._drag_task, name)

    def _drag_task(self, task):
        if not self._dragging:
            return task.cont

        base = getattr(ShowBaseGlobal, "base", None)
        if base is None or base.mouseWatcherNode is None:
            return task.cont
        try:
            down = bool(base.mouseWatcherNode.isButtonDown(MouseButton.one())) or bool(
                base.mouseWatcherNode.isButtonDown(KeyboardButton.mouse1())
            )
            if not down:
                self._drag_end()
                return task.cont
        except Exception:
            pass

        my = self._mouse_y()
        if my is not None:
            dy = float(my) - float(self._drag_last_my)
            self._drag_last_my = float(my)
        else:
            py = self._pointer_y()
            if py is None:
                return task.cont
            # Pointer Y units are pixels and platform-dependent; normalize by window height.
            dy_px = float(py) - float(self._drag_last_ptr_y)
            self._drag_last_ptr_y = float(py)
            win_h = 1.0
            try:
                win_h = float(base.win.getYSize())
            except Exception:
                win_h = 1.0
            dy = dy_px / max(1.0, win_h)

        # Approximate mapping from mouse delta to scrollbar value delta.
        # Drag up (positive dy) should scroll up (lower value).
        try:
            bar = self.frame.verticalScroll
            cur = float(bar["value"])
            nxt = cur - (dy / max(0.001, float(self.h)))
            self._set_bar_value(nxt)
        except Exception:
            pass

        return task.cont

    def set_canvas_h(self, canvas_h: float) -> None:
        self.canvas_h = float(max(self.h, canvas_h))
        self.frame["canvasSize"] = (0.0, self.content_w(), 0.0, self.canvas_h)

    def scroll_wheel(self, direction: int) -> None:
        d = 1 if int(direction) > 0 else -1
        try:
            bar = self.frame.verticalScroll
            cur = float(bar["value"])
            self._set_bar_value(cur - d * 0.020)
        except Exception:
            pass

    def destroy(self) -> None:
        try:
            self.frame.destroy()
        except Exception:
            pass
