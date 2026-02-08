from __future__ import annotations

from dataclasses import dataclass

from direct.task import Task
from panda3d.core import ButtonHandle, KeyboardButton, LVector3f, NodePath


@dataclass
class OrbitCameraSettings:
    orbit_sensitivity: float = 180.0  # deg per normalized screen unit
    pan_sensitivity: float = 1.25  # world-units per normalized screen unit (scaled by distance)
    dolly_sensitivity: float = 0.13  # exponential step per wheel tick / drag
    min_distance: float = 0.15
    max_distance: float = 50000.0
    pitch_min: float = -89.0
    pitch_max: float = 89.0


class OrbitCameraController:
    """
    Editor-style orbit camera around a target point.

    Bindings (viewport-only; caller should gate by a hit test):
    - Orbit: RMB drag OR Alt+LMB drag
    - Pan:   MMB drag OR Alt+Shift+LMB drag
    - Dolly: wheel_up/down OR Alt+Ctrl+LMB drag
    - Focus: caller sets target/distance; we expose helpers.
    """

    def __init__(
        self,
        *,
        base,
        camera_np: NodePath,
        world_root: NodePath,
        initial_target: LVector3f,
        initial_yaw_deg: float,
        initial_pitch_deg: float,
        initial_distance: float,
        settings: OrbitCameraSettings | None = None,
        mouse_lens_fn=None,  # fn() -> (lx, ly) in [-1..1] within viewport, else None
    ) -> None:
        self.base = base
        self.world_root = world_root
        self.camera = camera_np
        self.settings = settings or OrbitCameraSettings()
        self._mouse_lens_fn = mouse_lens_fn or self._mouse_lens_default

        # Pivot node lives in world space; camera is a child with a -Y offset.
        self.pivot = world_root.attachNewNode("baker.editor_camera_pivot")
        self.target = LVector3f(initial_target)
        self.yaw = float(initial_yaw_deg)
        self.pitch = float(initial_pitch_deg)
        self.distance = float(initial_distance)

        try:
            self.camera.reparentTo(self.pivot)
        except Exception:
            pass

        self._drag_mode: str | None = None  # orbit | pan | dolly
        self._drag_last: tuple[float, float] | None = None
        self._drag_moved: bool = False

        self._apply()
        self._bind_inputs()
        self.base.taskMgr.add(self._task, "baker.editor_camera")

    def destroy(self) -> None:
        try:
            self.base.taskMgr.remove("baker.editor_camera")
        except Exception:
            pass
        try:
            self.pivot.removeNode()
        except Exception:
            pass

    def _bind_inputs(self) -> None:
        self.base.accept("mouse1", self._on_lmb_down)
        self.base.accept("mouse1-up", self._on_mouse_up)
        self.base.accept("mouse2", self._on_mmb_down)
        self.base.accept("mouse2-up", self._on_mouse_up)
        self.base.accept("mouse3", self._on_rmb_down)
        self.base.accept("mouse3-up", self._on_mouse_up)
        self.base.accept("wheel_up", lambda: self._wheel(+1))
        self.base.accept("wheel_down", lambda: self._wheel(-1))
        self.base.accept("escape", self._cancel_drag)

    def _mouse_lens_default(self) -> tuple[float, float] | None:
        # Fallback: treat the entire window as the viewport.
        mw = getattr(self.base, "mouseWatcherNode", None)
        if mw is None or not mw.hasMouse():
            return None
        return (float(mw.getMouseX()), float(mw.getMouseY()))

    def _is_down(self, name: str) -> bool:
        mw = getattr(self.base, "mouseWatcherNode", None)
        if mw is None:
            return False
        k = (name or "").lower().strip()
        if not k:
            return False
        if k in {"shift", "control", "alt"}:
            return bool(mw.isButtonDown(ButtonHandle(k)))
        if len(k) == 1 and ord(k) < 128:
            if mw.isButtonDown(KeyboardButton.ascii_key(k)):
                return True
            return bool(mw.isButtonDown(ButtonHandle(f"raw-{k}")))
        return bool(mw.isButtonDown(ButtonHandle(k)))

    def _begin_drag(self, mode: str) -> None:
        mp = self._mouse_lens_fn()
        if mp is None:
            return
        self._drag_mode = str(mode)
        self._drag_last = (float(mp[0]), float(mp[1]))
        self._drag_moved = False

    def _on_lmb_down(self) -> None:
        # Trackpad-friendly combos.
        if self._is_down("alt") and self._is_down("shift"):
            self._begin_drag("pan")
            return
        if self._is_down("alt") and self._is_down("control"):
            self._begin_drag("dolly")
            return
        if self._is_down("alt"):
            self._begin_drag("orbit")

    def _on_mmb_down(self) -> None:
        self._begin_drag("pan")

    def _on_rmb_down(self) -> None:
        self._begin_drag("orbit")

    def _on_mouse_up(self) -> None:
        self._drag_mode = None
        self._drag_last = None

    def _cancel_drag(self) -> None:
        self._on_mouse_up()

    def did_drag_move(self) -> bool:
        return bool(self._drag_moved)

    def consume_drag_moved(self) -> bool:
        """
        Return whether the last drag interaction moved the camera, then reset the flag.

        This is used to distinguish a click (for selection) from a navigation drag.
        """

        moved = bool(self._drag_moved)
        self._drag_moved = False
        return moved

    def _wheel(self, direction: int) -> None:
        mp = self._mouse_lens_fn()
        if mp is None:
            return
        d = 1 if int(direction) > 0 else -1
        self._dolly(step=-d)

    def _dolly(self, *, step: float) -> None:
        s = self.settings
        # Exponential dolly feels consistent across scales.
        factor = pow(2.718281828, float(step) * float(s.dolly_sensitivity))
        self.distance *= float(factor)
        self.distance = max(float(s.min_distance), min(float(s.max_distance), float(self.distance)))
        self._apply()

    def focus(self, *, target: LVector3f, distance: float | None = None) -> None:
        self.target = LVector3f(target)
        if distance is not None:
            self.distance = float(distance)
        self._apply()

    def apply(self) -> None:
        """Re-apply current yaw/pitch/target/distance to the scene graph."""
        self._apply()

    def _apply(self) -> None:
        s = self.settings
        self.pitch = max(float(s.pitch_min), min(float(s.pitch_max), float(self.pitch)))
        self.distance = max(float(s.min_distance), min(float(s.max_distance), float(self.distance)))
        try:
            self.pivot.setPos(self.world_root, self.target)
        except Exception:
            try:
                self.pivot.setPos(self.target)
            except Exception:
                pass
        try:
            self.pivot.setHpr(float(self.yaw), float(self.pitch), 0.0)
        except Exception:
            pass
        try:
            self.camera.setPos(0.0, -float(self.distance), 0.0)
        except Exception:
            pass

    def _pan(self, *, dx: float, dy: float) -> None:
        # Scale pan with distance so it stays usable.
        s = self.settings
        scale = float(s.pan_sensitivity) * max(0.25, float(self.distance) * 0.0025)

        # Move the target along camera right/up in world space.
        try:
            q = self.camera.getQuat(self.world_root)
            right = q.getRight()
            up = q.getUp()
        except Exception:
            right = LVector3f(1, 0, 0)
            up = LVector3f(0, 0, 1)

        self.target += right * (-dx * scale)
        self.target += up * (dy * scale)
        self._apply()

    def _orbit(self, *, dx: float, dy: float) -> None:
        s = self.settings
        self.yaw += float(dx) * float(s.orbit_sensitivity)
        self.pitch += float(dy) * float(s.orbit_sensitivity)
        self._apply()

    def _task(self, task: Task) -> int:
        try:
            mode = self._drag_mode
            if not mode:
                return Task.cont

            mp = self._mouse_lens_fn()
            if mp is None:
                return Task.cont

            last = self._drag_last
            if last is None:
                self._drag_last = (float(mp[0]), float(mp[1]))
                return Task.cont

            lx, ly = last
            dx = float(mp[0]) - float(lx)
            dy = float(mp[1]) - float(ly)
            self._drag_last = (float(mp[0]), float(mp[1]))

            if abs(dx) > 1e-4 or abs(dy) > 1e-4:
                self._drag_moved = True

            if mode == "orbit":
                self._orbit(dx=dx, dy=dy)
            elif mode == "pan":
                self._pan(dx=dx, dy=dy)
            elif mode == "dolly":
                # Drag up/down to dolly.
                self._dolly(step=dy * 10.0)
            return Task.cont
        except Exception:
            return Task.cont
