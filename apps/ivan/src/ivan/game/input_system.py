from __future__ import annotations

from panda3d.core import ButtonHandle, KeyboardButton

from ivan.replays import DemoFrame


class _InputCommand:
    def __init__(
        self,
        *,
        look_dx: int = 0,
        look_dy: int = 0,
        look_scale: int = 1,
        move_forward: int = 0,
        move_right: int = 0,
        jump_pressed: bool = False,
        jump_held: bool = False,
        crouch_held: bool = False,
        grapple_pressed: bool = False,
        noclip_toggle_pressed: bool = False,
    ) -> None:
        self.look_dx = int(look_dx)
        self.look_dy = int(look_dy)
        self.look_scale = max(1, int(look_scale))
        self.move_forward = int(move_forward)
        self.move_right = int(move_right)
        self.jump_pressed = bool(jump_pressed)
        self.jump_held = bool(jump_held)
        self.crouch_held = bool(crouch_held)
        self.grapple_pressed = bool(grapple_pressed)
        self.noclip_toggle_pressed = bool(noclip_toggle_pressed)

    def to_demo_frame(self) -> DemoFrame:
        return DemoFrame(
            look_dx=self.look_dx,
            look_dy=self.look_dy,
            move_forward=self.move_forward,
            move_right=self.move_right,
            jump_pressed=self.jump_pressed,
            jump_held=self.jump_held,
            crouch_held=self.crouch_held,
            grapple_pressed=self.grapple_pressed,
            noclip_toggle_pressed=self.noclip_toggle_pressed,
        )

    @classmethod
    def from_demo_frame(cls, frame: DemoFrame, *, look_scale: int) -> "_InputCommand":
        return cls(
            look_dx=frame.look_dx,
            look_dy=frame.look_dy,
            look_scale=look_scale,
            move_forward=frame.move_forward,
            move_right=frame.move_right,
            jump_pressed=frame.jump_pressed,
            jump_held=frame.jump_held,
            crouch_held=frame.crouch_held,
            grapple_pressed=frame.grapple_pressed,
            noclip_toggle_pressed=frame.noclip_toggle_pressed,
        )


def poll_mouse_look_delta(host) -> None:
    if host.cfg.smoke or not host._pointer_locked:
        host._last_mouse = None
        return

    # Primary path: normalized mouse coords (works well with relative mouse mode).
    if host.mouseWatcherNode is not None and host.mouseWatcherNode.hasMouse():
        mx = float(host.mouseWatcherNode.getMouseX())
        my = float(host.mouseWatcherNode.getMouseY())
        if host._last_mouse is None:
            host._last_mouse = (mx, my)
            return
        lmx, lmy = host._last_mouse
        host._last_mouse = (mx, my)

        dx_norm = mx - lmx
        # Keep non-inverted vertical look (mouse up -> look up).
        dy_norm = lmy - my
        host._mouse_dx_accum += dx_norm * (host.win.getXSize() * 0.5)
        host._mouse_dy_accum += dy_norm * (host.win.getYSize() * 0.5)
        return

    # Fallback: pointer delta vs screen center (useful if hasMouse() stays false on some macOS setups).
    cx = host.win.getXSize() // 2
    cy = host.win.getYSize() // 2
    pointer = host.win.getPointer(0)
    dx = float(pointer.getX() - cx)
    dy = float(pointer.getY() - cy)

    if dx == 0.0 and dy == 0.0:
        return
    host._mouse_dx_accum += dx
    host._mouse_dy_accum += dy
    host._center_mouse()


def consume_mouse_look_delta(host) -> tuple[int, int]:
    s = float(host._look_input_scale)
    dx = int(round(host._mouse_dx_accum * s))
    dy = int(round(host._mouse_dy_accum * s))
    host._mouse_dx_accum -= float(dx) / s
    host._mouse_dy_accum -= float(dy) / s
    return (dx, dy)


def is_key_down(host, key_name: str) -> bool:
    if host.mouseWatcherNode is None:
        return False
    k = (key_name or "").lower().strip()
    if not k:
        return False
    if k in {"space", "spacebar"}:
        return bool(host.mouseWatcherNode.isButtonDown(KeyboardButton.space()))
    if len(k) == 1 and ord(k) < 128:
        # ASCII key (layout-dependent) + raw key (layout-independent).
        if host.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key(k)):
            return True
        return bool(host.mouseWatcherNode.isButtonDown(ButtonHandle(f"raw-{k}")))
    if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
        return bool(host.mouseWatcherNode.isButtonDown(ButtonHandle(k)))
    return bool(host.mouseWatcherNode.isButtonDown(ButtonHandle(k)))


def move_axes_from_keyboard(host) -> tuple[int, int]:
    if host.mouseWatcherNode is None:
        return (0, 0)
    fwd = 0
    right = 0
    # Support non-US keyboard layouts by checking Cyrillic equivalents of WASD (RU):
    # W/A/S/D -> Ц/Ф/Ы/В. Arrow keys are also supported as a fallback.
    if is_key_down(host, "w") or is_key_down(host, "ц") or host.mouseWatcherNode.isButtonDown(KeyboardButton.up()):
        fwd += 1
    if is_key_down(host, "s") or is_key_down(host, "ы") or host.mouseWatcherNode.isButtonDown(KeyboardButton.down()):
        fwd -= 1
    if is_key_down(host, "d") or is_key_down(host, "в") or host.mouseWatcherNode.isButtonDown(KeyboardButton.right()):
        right += 1
    if is_key_down(host, "a") or is_key_down(host, "ф") or host.mouseWatcherNode.isButtonDown(KeyboardButton.left()):
        right -= 1
    return (max(-1, min(1, fwd)), max(-1, min(1, right)))


def sample_live_input_command(host, *, menu_open: bool) -> _InputCommand:
    look_dx, look_dy = (0, 0) if menu_open else consume_mouse_look_delta(host)
    move_forward = 0
    move_right = 0
    jump_held = False
    crouch_held = False
    grapple_down = False
    noclip_toggle_down = False
    demo_save_down = False
    if not menu_open:
        move_forward, move_right = move_axes_from_keyboard(host)
        jump_held = is_key_down(host, "space")
        crouch_held = host._is_crouching()
        grapple_down = is_key_down(host, "mouse1")
        noclip_toggle_down = is_key_down(host, host._noclip_toggle_key)
        demo_save_down = is_key_down(host, host._demo_save_key)

    cmd = _InputCommand(
        look_dx=look_dx,
        look_dy=look_dy,
        look_scale=host._look_input_scale,
        move_forward=move_forward,
        move_right=move_right,
        jump_pressed=(not menu_open) and jump_held and (not host._prev_jump_down),
        jump_held=(not menu_open) and jump_held,
        crouch_held=(not menu_open) and crouch_held,
        grapple_pressed=(not menu_open) and grapple_down and (not host._prev_grapple_down),
        noclip_toggle_pressed=(not menu_open) and noclip_toggle_down and (not host._prev_noclip_toggle_down),
    )

    host._prev_jump_down = (not menu_open) and jump_held
    host._prev_grapple_down = (not menu_open) and grapple_down
    host._prev_noclip_toggle_down = (not menu_open) and noclip_toggle_down

    # Save is sampled here so it can be edge-triggered alongside the fixed tick input.
    save_pressed = (not menu_open) and demo_save_down and (not host._prev_demo_save_down)
    host._prev_demo_save_down = (not menu_open) and demo_save_down
    if save_pressed:
        host._save_current_demo()
    return cmd


def normalize_bind_key(key: str) -> str | None:
    k = (key or "").strip().lower()
    if not k:
        return None
    aliases = {
        "space": "space",
        "spacebar": "space",
        "grave": "`",
        "backquote": "`",
        "backtick": "`",
    }
    if k in aliases:
        return aliases[k]
    if len(k) == 1 and ord(k) < 128:
        return k
    if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
        return k
    return None


__all__ = [
    "_InputCommand",
    "consume_mouse_look_delta",
    "is_key_down",
    "move_axes_from_keyboard",
    "normalize_bind_key",
    "poll_mouse_look_delta",
    "sample_live_input_command",
]

