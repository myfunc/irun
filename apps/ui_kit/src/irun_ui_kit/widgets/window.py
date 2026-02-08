from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from direct.showbase import ShowBaseGlobal
from panda3d.core import NodePath

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.panel import Panel


@dataclass
class Window:
    root: NodePath
    panel: Panel
    content: NodePath

    _dragging: bool
    _drag_off_x: float
    _drag_off_y: float

    def __init__(self, *, aspect2d, theme: Theme, title: str, x: float, y: float, w: float, h: float) -> None:
        # The Panel already creates a local-coordinate container at (x, y).
        self.panel = Panel.build(parent=aspect2d, theme=theme, x=x, y=y, w=w, h=h, title=title, header=True)
        self.root = self.panel.node

        # Content container below the header bar.
        header_h = theme.header_h + (theme.outline_w * 2)
        self.content = DirectFrame(
            parent=self.root,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(theme.pad, w - theme.pad, theme.pad, h - header_h),
        )

        self._dragging = False
        self._drag_off_x = 0.0
        self._drag_off_y = 0.0

        # Titlebar hit area: we bind mouse events to the header strip region.
        # Use an invisible frame covering the header.
        self._title_hit = DirectFrame(
            parent=self.root,
            frameColor=(0, 0, 0, 0),
            relief=DGG.FLAT,
            frameSize=(0.0, w, h - theme.header_h - theme.outline_w, h),
        )
        self._title_hit.bind(DGG.B1PRESS, lambda _evt: self._drag_start())
        self._title_hit.bind(DGG.B1RELEASE, lambda _evt: self._drag_end())
        # Some Panda3D builds do not expose a drag/move event constant for DirectGUI.
        # Instead, we update position each frame while dragging via a task.

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
        self._drag_end()

    def _mouse_aspect(self) -> tuple[float, float] | None:
        if getattr(ShowBaseGlobal, "base", None) is None:
            return None
        base = ShowBaseGlobal.base
        if not base.mouseWatcherNode.hasMouse():
            return None
        m = base.mouseWatcherNode.getMouse()  # render2d coordinates [-1..1]
        aspect = float(base.getAspectRatio())
        return (float(m.getX()) * aspect, float(m.getY()))

    def _drag_start(self) -> None:
        mp = self._mouse_aspect()
        if mp is None:
            return
        mx, my = mp
        px, _py, pz = self.root.getPos()
        self._dragging = True
        self._drag_off_x = mx - float(px)
        self._drag_off_y = my - float(pz)
        self._ensure_drag_task()

    def _drag_end(self) -> None:
        self._dragging = False
        base = getattr(ShowBaseGlobal, "base", None)
        if base is not None:
            try:
                base.taskMgr.remove(f"ui-kit-window-drag-{id(self)}")
            except Exception:
                pass

    def _ensure_drag_task(self) -> None:
        base = getattr(ShowBaseGlobal, "base", None)
        if base is None:
            return
        name = f"ui-kit-window-drag-{id(self)}"
        if base.taskMgr.hasTaskNamed(name):
            return
        base.taskMgr.add(self._drag_task, name)

    def _drag_task(self, task):
        if not self._dragging:
            return task.cont
        mp = self._mouse_aspect()
        if mp is None:
            return task.cont
        mx, my = mp
        self.root.setPos(mx - self._drag_off_x, 0, my - self._drag_off_y)
        return task.cont
