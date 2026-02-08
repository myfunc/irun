from __future__ import annotations

from direct.task import Task
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import ButtonHandle, KeyboardButton, LVector3f, MouseButton, WindowProperties


class FlyCameraController:
    """Minimal fly camera: WASD/QE move + mouse/trackpad look (editor-style).

    This is intentionally small and app-local (Baker-only) for now.
    """

    def __init__(
        self,
        *,
        base,
        camera_np,
        initial_yaw_deg: float = 0.0,
        initial_pitch_deg: float = 0.0,
        move_speed: float = 10.0,
        fast_multiplier: float = 4.0,
        mouse_sensitivity: float = 0.12,
        on_pointer_lock_changed=None,
        on_input_debug=None,
    ) -> None:
        self.base = base
        self.camera_np = camera_np
        self.yaw = float(initial_yaw_deg)
        self.pitch = float(initial_pitch_deg)
        self.move_speed = float(move_speed)
        self.fast_multiplier = float(fast_multiplier)
        self.mouse_sensitivity = float(mouse_sensitivity)

        # Editor-style: unlocked by default; hold RMB to look.
        self._pointer_locked = False
        self._last_center: tuple[int, int] | None = None
        self._on_pointer_lock_changed = on_pointer_lock_changed
        self._on_input_debug = on_input_debug
        self._debug_enabled = False
        self._force_locked = False  # Toggle via Tab for trackpad setups that can't reliably hold RMB.

        self.base.disableMouse()
        self._bind_inputs()
        self._apply_pointer_lock(False)

        self.base.taskMgr.add(self._task, "baker.fly_camera")

    def _bind_inputs(self) -> None:
        self.base.accept("escape", lambda: self._apply_pointer_lock(False))
        self.base.accept("f1", self.toggle_debug)
        self.base.accept("tab", self._toggle_force_lock)

    def toggle_debug(self) -> None:
        self._debug_enabled = not self._debug_enabled
        cb = self._on_input_debug
        if cb is not None:
            try:
                cb("" if not self._debug_enabled else "Input debug: ON (F1 to toggle)")
            except Exception:
                pass

    def _toggle_force_lock(self) -> None:
        self._force_locked = not self._force_locked
        self._apply_pointer_lock(self._force_locked)

    def _apply_pointer_lock(self, locked: bool) -> None:
        self._pointer_locked = bool(locked)
        if self.base.win is None:
            return
        if not hasattr(self.base.win, "requestProperties"):
            return

        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        # Relative mode is important for editor-style mouse look.
        props.setMouseMode(WindowProperties.M_relative if self._pointer_locked else WindowProperties.M_absolute)
        self.base.win.requestProperties(props)

        # Reset center tracking so we don't get a huge delta the first frame.
        self._last_center = None
        cb = self._on_pointer_lock_changed
        if cb is not None:
            try:
                cb(bool(self._pointer_locked))
            except Exception:
                pass

    def is_pointer_locked(self) -> bool:
        return bool(self._pointer_locked)

    def _is_down(self, button) -> bool:
        try:
            mw = getattr(self.base, "mouseWatcherNode", None)
            if mw is None:
                return False
            return bool(mw.isButtonDown(button))
        except Exception:
            return False

    def _is_key_down(self, key_name: str) -> bool:
        """
        Layout-tolerant key check.

        Mirrors Ivan's input approach:
        - ASCII key: check both `ascii_key()` and `raw-<k>` (layout-independent).
        - Otherwise: fall back to ButtonHandle(name).
        """

        mw = getattr(self.base, "mouseWatcherNode", None)
        if mw is None:
            return False
        k = (key_name or "").lower().strip()
        if not k:
            return False
        if k in {"space", "spacebar"}:
            return bool(mw.isButtonDown(KeyboardButton.space()))
        if len(k) == 1 and ord(k) < 128:
            if mw.isButtonDown(KeyboardButton.ascii_key(k)):
                return True
            return bool(mw.isButtonDown(ButtonHandle(f"raw-{k}")))
        if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
            return bool(mw.isButtonDown(ButtonHandle(k)))
        return bool(mw.isButtonDown(ButtonHandle(k)))

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return lo if x < lo else hi if x > hi else x

    def _update_pointer_lock_from_mouse(self) -> None:
        if self._force_locked:
            return

        # Hold mouse button to look. Trackpads/right-click remaps can arrive as mouse1/2/3.
        rmb = (
            self._is_down(MouseButton.one())
            or self._is_down(MouseButton.two())
            or self._is_down(MouseButton.three())
        )
        if rmb and not self._pointer_locked:
            self._apply_pointer_lock(True)
        if (not rmb) and self._pointer_locked:
            self._apply_pointer_lock(False)

    def _update_look(self) -> None:
        self._update_pointer_lock_from_mouse()
        if not self._pointer_locked:
            return
        if self.base.win is None:
            return

        # Recenter pointer every frame and use delta-from-center.
        w = int(self.base.win.getXSize())
        h = int(self.base.win.getYSize())
        if w <= 0 or h <= 0:
            return
        cx = w // 2
        cy = h // 2

        pointer = self.base.win.getPointer(0)
        mx = int(pointer.getX())
        my = int(pointer.getY())

        # Some window managers can report stale pointer positions right after resize.
        if self._last_center is None:
            self.base.win.movePointer(0, cx, cy)
            self._last_center = (cx, cy)
            return

        dx = float(mx - cx)
        dy = float(my - cy)

        self.yaw -= dx * self.mouse_sensitivity
        self.pitch -= dy * self.mouse_sensitivity
        self.pitch = self._clamp(self.pitch, -89.0, 89.0)

        self.camera_np.setHpr(self.yaw, self.pitch, 0.0)
        self.base.win.movePointer(0, cx, cy)

    def _update_move(self, *, dt: float) -> None:
        if dt <= 0.0:
            return

        shift = bool(self._is_key_down("shift"))
        speed = self.move_speed * (self.fast_multiplier if shift else 1.0)

        # Local movement axes in Panda3D: Y is forward, X is right, Z is up.
        fwd = LVector3f(0, 1, 0)
        right = LVector3f(1, 0, 0)
        up = LVector3f(0, 0, 1)

        move = LVector3f(0, 0, 0)
        # W/A/S/D -> Ц/Ф/Ы/В. Arrow keys as a fallback.
        if self._is_key_down("w") or self._is_key_down("ц") or self._is_down(KeyboardButton.up()):
            move += fwd
        if self._is_key_down("s") or self._is_key_down("ы") or self._is_down(KeyboardButton.down()):
            move -= fwd
        if self._is_key_down("d") or self._is_key_down("в") or self._is_down(KeyboardButton.right()):
            move += right
        if self._is_key_down("a") or self._is_key_down("ф") or self._is_down(KeyboardButton.left()):
            move -= right
        if self._is_key_down("e") or self._is_key_down("у"):
            move += up
        if self._is_key_down("q") or self._is_key_down("й"):
            move -= up

        if move.lengthSquared() <= 1e-10:
            return

        move.normalize()
        move *= speed * float(dt)

        # Apply movement in camera space.
        self.camera_np.setPos(self.camera_np, move)

    def _emit_debug(self, *, dt: float) -> None:
        if not self._debug_enabled:
            return
        cb = self._on_input_debug
        if cb is None:
            return
        keys: list[str] = []
        if self._is_key_down("w") or self._is_key_down("ц") or self._is_down(KeyboardButton.up()):
            keys.append("FWD")
        if self._is_key_down("s") or self._is_key_down("ы") or self._is_down(KeyboardButton.down()):
            keys.append("BACK")
        if self._is_key_down("a") or self._is_key_down("ф") or self._is_down(KeyboardButton.left()):
            keys.append("LEFT")
        if self._is_key_down("d") or self._is_key_down("в") or self._is_down(KeyboardButton.right()):
            keys.append("RIGHT")
        if self._is_key_down("q") or self._is_key_down("й"):
            keys.append("DOWN")
        if self._is_key_down("e") or self._is_key_down("у"):
            keys.append("UP")
        if self._is_key_down("shift"):
            keys.append("FAST")
        mb = (
            self._is_down(MouseButton.one())
            or self._is_down(MouseButton.two())
            or self._is_down(MouseButton.three())
        )
        if mb:
            keys.append("MB")
        try:
            cb(
                f"keys={'+'.join(keys) if keys else '(none)'} "
                f"dt={dt:.4f} "
                f"pointer={'locked' if self._pointer_locked else 'unlocked'} "
                f"tab_lock={'on' if self._force_locked else 'off'}"
            )
        except Exception:
            pass

    def _task(self, task: Task) -> int:
        try:
            # Task.dt is not guaranteed to exist; use the global clock.
            dt = float(globalClock.getDt())
            self._update_look()
            self._update_move(dt=dt)
            self._emit_debug(dt=dt)
            return Task.cont
        except Exception:
            cb = self._on_input_debug
            if cb is not None:
                try:
                    cb("Input debug: EXCEPTION in fly camera (see log)")
                except Exception:
                    pass
            # Never hard-crash input tasks.
            return Task.cont
