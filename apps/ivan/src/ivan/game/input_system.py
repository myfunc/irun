from __future__ import annotations

import time

from panda3d.core import ButtonHandle, KeyboardButton

from ivan.replays import DemoFrame


_MOVE_FORWARD_KEYS: tuple[str, ...] = ("ц", "z")
_MOVE_LEFT_KEYS: tuple[str, ...] = ("ф", "q")
_MOVE_BACK_KEYS: tuple[str, ...] = ("ы", "і")
_MOVE_RIGHT_KEYS: tuple[str, ...] = ("в",)
_ROLL_LEFT_KEYS: tuple[str, ...] = ("й",)
_ROLL_RIGHT_KEYS: tuple[str, ...] = ("у",)
_RAW_LANE_KEYS: tuple[str, ...] = ("w", "a", "s", "d", "q", "e", "1", "2", "3", "4", "5", "6")

# Non-ASCII layout symbols mapped to the same physical key lane as US WASD.
_NON_ASCII_TO_RAW_WASD: dict[str, str] = {
    "ц": "w",
    "ф": "a",
    "ы": "s",
    "і": "s",
    "в": "d",
    "й": "q",
    "у": "e",
}


def _window_allows_pointer_capture(host) -> bool:
    win = getattr(host, "win", None)
    if win is None:
        return False
    try:
        props = win.getProperties()
    except Exception:
        return False
    try:
        if hasattr(props, "getOpen") and not bool(props.getOpen()):
            return False
    except Exception:
        pass
    try:
        if hasattr(props, "getMinimized") and bool(props.getMinimized()):
            return False
    except Exception:
        pass
    try:
        if hasattr(props, "getForeground") and not bool(props.getForeground()):
            return False
    except Exception:
        pass
    return True


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
        slide_pressed: bool = False,
        grapple_pressed: bool = False,
        noclip_toggle_pressed: bool = False,
        weapon_slot_select: int = 0,
        key_w_held: bool = False,
        key_a_held: bool = False,
        key_s_held: bool = False,
        key_d_held: bool = False,
        key_q_held: bool = False,
        key_e_held: bool = False,
        arrow_up_held: bool = False,
        arrow_down_held: bool = False,
        arrow_left_held: bool = False,
        arrow_right_held: bool = False,
        mouse_left_held: bool = False,
        mouse_right_held: bool = False,
        raw_wasd_available: bool = False,
        raw_arrows_available: bool = False,
        raw_mouse_buttons_available: bool = False,
    ) -> None:
        self.look_dx = int(look_dx)
        self.look_dy = int(look_dy)
        self.look_scale = max(1, int(look_scale))
        self.move_forward = int(move_forward)
        self.move_right = int(move_right)
        self.jump_pressed = bool(jump_pressed)
        self.jump_held = bool(jump_held)
        self.slide_pressed = bool(slide_pressed)
        self.grapple_pressed = bool(grapple_pressed)
        self.noclip_toggle_pressed = bool(noclip_toggle_pressed)
        self.weapon_slot_select = max(0, min(6, int(weapon_slot_select)))
        self.key_w_held = bool(key_w_held)
        self.key_a_held = bool(key_a_held)
        self.key_s_held = bool(key_s_held)
        self.key_d_held = bool(key_d_held)
        self.key_q_held = bool(key_q_held)
        self.key_e_held = bool(key_e_held)
        self.arrow_up_held = bool(arrow_up_held)
        self.arrow_down_held = bool(arrow_down_held)
        self.arrow_left_held = bool(arrow_left_held)
        self.arrow_right_held = bool(arrow_right_held)
        self.mouse_left_held = bool(mouse_left_held)
        self.mouse_right_held = bool(mouse_right_held)
        self.raw_wasd_available = bool(raw_wasd_available)
        self.raw_arrows_available = bool(raw_arrows_available)
        self.raw_mouse_buttons_available = bool(raw_mouse_buttons_available)

    def to_demo_frame(self) -> DemoFrame:
        return self.to_demo_frame_with_telemetry(telemetry=None)

    def to_demo_frame_with_telemetry(self, *, telemetry: dict[str, float | int | bool] | None) -> DemoFrame:
        return DemoFrame(
            look_dx=self.look_dx,
            look_dy=self.look_dy,
            move_forward=self.move_forward,
            move_right=self.move_right,
            jump_pressed=self.jump_pressed,
            jump_held=self.jump_held,
            slide_pressed=self.slide_pressed,
            grapple_pressed=self.grapple_pressed,
            noclip_toggle_pressed=self.noclip_toggle_pressed,
            weapon_slot_select=self.weapon_slot_select,
            key_w_held=self.key_w_held,
            key_a_held=self.key_a_held,
            key_s_held=self.key_s_held,
            key_d_held=self.key_d_held,
            key_q_held=self.key_q_held,
            key_e_held=self.key_e_held,
            arrow_up_held=self.arrow_up_held,
            arrow_down_held=self.arrow_down_held,
            arrow_left_held=self.arrow_left_held,
            arrow_right_held=self.arrow_right_held,
            mouse_left_held=self.mouse_left_held,
            mouse_right_held=self.mouse_right_held,
            raw_wasd_available=self.raw_wasd_available,
            raw_arrows_available=self.raw_arrows_available,
            raw_mouse_buttons_available=self.raw_mouse_buttons_available,
            telemetry=(dict(telemetry) if isinstance(telemetry, dict) else None),
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
            slide_pressed=frame.slide_pressed,
            grapple_pressed=frame.grapple_pressed,
            noclip_toggle_pressed=frame.noclip_toggle_pressed,
            weapon_slot_select=getattr(frame, "weapon_slot_select", 0),
            key_w_held=frame.key_w_held,
            key_a_held=frame.key_a_held,
            key_s_held=frame.key_s_held,
            key_d_held=frame.key_d_held,
            key_q_held=getattr(frame, "key_q_held", False),
            key_e_held=getattr(frame, "key_e_held", False),
            arrow_up_held=frame.arrow_up_held,
            arrow_down_held=frame.arrow_down_held,
            arrow_left_held=frame.arrow_left_held,
            arrow_right_held=frame.arrow_right_held,
            mouse_left_held=frame.mouse_left_held,
            mouse_right_held=frame.mouse_right_held,
            raw_wasd_available=frame.raw_wasd_available,
            raw_arrows_available=frame.raw_arrows_available,
            raw_mouse_buttons_available=frame.raw_mouse_buttons_available,
        )


def poll_mouse_look_delta(host) -> None:
    if host.cfg.smoke or not host._pointer_locked:
        host._last_mouse = None
        setattr(host, "_mouse_capture_blocked", True)
        return
    if not _window_allows_pointer_capture(host):
        host._last_mouse = None
        host._mouse_dx_accum = 0.0
        host._mouse_dy_accum = 0.0
        setattr(host, "_mouse_capture_blocked", True)
        return

    # Center-snap approach: read cursor pixel offset from window center, accumulate,
    # then snap the cursor back to center.  This keeps the cursor confined reliably
    # in windowed mode on all platforms (Windows + macOS) and avoids the cursor
    # drifting to the window edge and escaping.
    cx = host.win.getXSize() // 2
    cy = host.win.getYSize() // 2
    if bool(getattr(host, "_mouse_capture_blocked", False)):
        setattr(host, "_mouse_capture_blocked", False)
        host.win.movePointer(0, cx, cy)
        return
    pointer = host.win.getPointer(0)
    dx = float(pointer.getX() - cx)
    dy = float(pointer.getY() - cy)

    if dx == 0.0 and dy == 0.0:
        return
    host._mouse_dx_accum += dx
    host._mouse_dy_accum += dy
    host.win.movePointer(0, cx, cy)


def consume_mouse_look_delta(host) -> tuple[int, int]:
    s = float(host._look_input_scale)
    dx = int(round(host._mouse_dx_accum * s))
    dy = int(round(host._mouse_dy_accum * s))
    host._mouse_dx_accum -= float(dx) / s
    host._mouse_dy_accum -= float(dy) / s
    return (dx, dy)


def _button_down(host, *, key_name: str) -> bool:
    if host.mouseWatcherNode is None:
        return False
    return bool(host.mouseWatcherNode.isButtonDown(ButtonHandle(str(key_name))))


def _any_layout_key_down(host, keys: tuple[str, ...]) -> bool:
    return any(is_key_down(host, key) for key in keys)


def _keyboard_map_getter(win):
    getter = getattr(win, "get_keyboard_map", None)
    if callable(getter):
        return getter
    getter = getattr(win, "getKeyboardMap", None)
    if callable(getter):
        return getter
    return None


def _button_map_lookup(button_map, raw_key: str):
    raw = str(raw_key).lower().strip()
    if not raw:
        return None
    raw_variants = (raw, f"raw-{raw}", f"raw_{raw}")
    getter = getattr(button_map, "get_mapped_button", None)
    if callable(getter):
        for name in raw_variants:
            mapped = getter(str(name))
            mapped_name = mapped.getName() if isinstance(mapped, ButtonHandle) and hasattr(mapped, "getName") else str(mapped)
            if isinstance(mapped, ButtonHandle) and str(mapped_name).lower().strip() not in {"", "none"}:
                return mapped
    getter = getattr(button_map, "getMappedButton", None)
    if callable(getter):
        for name in raw_variants:
            mapped = getter(str(name))
            mapped_name = mapped.getName() if isinstance(mapped, ButtonHandle) and hasattr(mapped, "getName") else str(mapped)
            if isinstance(mapped, ButtonHandle) and str(mapped_name).lower().strip() not in {"", "none"}:
                return mapped
    return None


def _cached_layout_map(host) -> dict[str, ButtonHandle]:
    cache = getattr(host, "_input_layout_map_cache", None)
    if isinstance(cache, dict):
        return cache
    cache = {}
    setattr(host, "_input_layout_map_cache", cache)
    return cache


def _refresh_layout_map_if_needed(host, *, force: bool = False) -> None:
    win = getattr(host, "win", None)
    if win is None:
        return
    getter = _keyboard_map_getter(win)
    if getter is None:
        return
    now = float(time.monotonic())
    last_raw = getattr(host, "_input_layout_map_refresh_s", None)
    last = float(last_raw) if isinstance(last_raw, (int, float)) else -99999.0
    if not force and isinstance(last_raw, (int, float)) and last > 0.0 and (now - last) < 0.75:
        return
    try:
        button_map = getter()
    except Exception:
        return
    out: dict[str, ButtonHandle] = {}
    for raw in _RAW_LANE_KEYS:
        try:
            mapped = _button_map_lookup(button_map, raw)
        except Exception:
            mapped = None
        if isinstance(mapped, ButtonHandle):
            out[raw] = mapped
    setattr(host, "_input_layout_map_cache", out)
    setattr(host, "_input_layout_map_refresh_s", now)


def _is_raw_lane_down(host, *, raw_key: str) -> bool:
    if host.mouseWatcherNode is None:
        return False
    raw = str(raw_key).lower().strip()
    if raw not in _RAW_LANE_KEYS:
        return False
    _refresh_layout_map_if_needed(host)
    mapped = _cached_layout_map(host).get(raw)
    if isinstance(mapped, ButtonHandle) and host.mouseWatcherNode.isButtonDown(mapped):
        return True
    # Fallbacks for runtimes that don't expose keyboard-map APIs.
    if _button_down(host, key_name=f"raw-{raw}"):
        return True
    if _button_down(host, key_name=f"raw_{raw}"):
        return True
    return bool(host.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key(raw)))


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
        if _is_raw_lane_down(host, raw_key=k):
            return True
        if _button_down(host, key_name=f"raw-{k}"):
            return True
        if _button_down(host, key_name=f"raw_{k}"):
            return True
        return _button_down(host, key_name=k)
    if len(k) == 1:
        # Non-ASCII symbol path for non-US layouts.
        if _button_down(host, key_name=k):
            return True
        raw_fallback = _NON_ASCII_TO_RAW_WASD.get(k)
        if raw_fallback:
            return _button_down(host, key_name=f"raw-{raw_fallback}")
        return False
    if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
        return _button_down(host, key_name=k)
    return _button_down(host, key_name=k)


def move_axes_from_keyboard(host) -> tuple[int, int]:
    if host.mouseWatcherNode is None:
        return (0, 0)
    fwd = 0
    right = 0
    # Layout-agnostic movement keys:
    # - physical WASD lane via keyboard map/raw fallback
    # - common symbol aliases for RU/UA/AZERTY
    # - arrows as always-on fallback
    if _is_raw_lane_down(host, raw_key="w") or _any_layout_key_down(host, _MOVE_FORWARD_KEYS) or host.mouseWatcherNode.isButtonDown(KeyboardButton.up()):
        fwd += 1
    if _is_raw_lane_down(host, raw_key="s") or _any_layout_key_down(host, _MOVE_BACK_KEYS) or host.mouseWatcherNode.isButtonDown(KeyboardButton.down()):
        fwd -= 1
    if _is_raw_lane_down(host, raw_key="d") or _any_layout_key_down(host, _MOVE_RIGHT_KEYS) or host.mouseWatcherNode.isButtonDown(KeyboardButton.right()):
        right += 1
    if _is_raw_lane_down(host, raw_key="a") or _any_layout_key_down(host, _MOVE_LEFT_KEYS) or host.mouseWatcherNode.isButtonDown(KeyboardButton.left()):
        right -= 1
    return (max(-1, min(1, fwd)), max(-1, min(1, right)))


def sample_live_input_command(host, *, menu_open: bool) -> _InputCommand:
    look_dx, look_dy = (0, 0) if menu_open else consume_mouse_look_delta(host)
    move_forward = 0
    move_right = 0
    jump_held = False
    slide_down = False
    fire_down = False
    grapple_down = False
    noclip_toggle_down = False
    demo_save_down = False
    key_w_held = False
    key_a_held = False
    key_s_held = False
    key_d_held = False
    key_q_held = False
    key_e_held = False
    arrow_up_held = False
    arrow_down_held = False
    arrow_left_held = False
    arrow_right_held = False
    weapon_slot_select = 0
    if not menu_open:
        move_forward, move_right = move_axes_from_keyboard(host)
        key_w_held = _is_raw_lane_down(host, raw_key="w") or _any_layout_key_down(host, _MOVE_FORWARD_KEYS)
        key_a_held = _is_raw_lane_down(host, raw_key="a") or _any_layout_key_down(host, _MOVE_LEFT_KEYS)
        key_s_held = _is_raw_lane_down(host, raw_key="s") or _any_layout_key_down(host, _MOVE_BACK_KEYS)
        key_d_held = _is_raw_lane_down(host, raw_key="d") or _any_layout_key_down(host, _MOVE_RIGHT_KEYS)
        key_q_held = _is_raw_lane_down(host, raw_key="q") or _any_layout_key_down(host, _ROLL_LEFT_KEYS)
        key_e_held = _is_raw_lane_down(host, raw_key="e") or _any_layout_key_down(host, _ROLL_RIGHT_KEYS)
        arrow_up_held = bool(host.mouseWatcherNode and host.mouseWatcherNode.isButtonDown(KeyboardButton.up()))
        arrow_down_held = bool(host.mouseWatcherNode and host.mouseWatcherNode.isButtonDown(KeyboardButton.down()))
        arrow_left_held = bool(host.mouseWatcherNode and host.mouseWatcherNode.isButtonDown(KeyboardButton.left()))
        arrow_right_held = bool(host.mouseWatcherNode and host.mouseWatcherNode.isButtonDown(KeyboardButton.right()))
        jump_held = is_key_down(host, "space")
        slide_down = is_key_down(host, "shift")
        # Combat fire is bound to LMB; grapple is bound to RMB.
        fire_down = is_key_down(host, "mouse1")
        grapple_down = is_key_down(host, "mouse3")
        noclip_toggle_down = is_key_down(host, host._noclip_toggle_key)
        demo_save_down = is_key_down(host, host._demo_save_key)
    slot_prev_raw = getattr(host, "_prev_weapon_slot_down", None)
    slot_prev = list(slot_prev_raw) if isinstance(slot_prev_raw, list) else [False, False, False, False, False, False]
    if len(slot_prev) != 6:
        slot_prev = [False, False, False, False, False, False]
    for idx, key in enumerate(("1", "2", "3", "4", "5", "6")):
        down = (not menu_open) and is_key_down(host, key)
        if down and not bool(slot_prev[idx]):
            weapon_slot_select = idx + 1
        slot_prev[idx] = bool(down)
    host._prev_weapon_slot_down = slot_prev

    cmd = _InputCommand(
        look_dx=look_dx,
        look_dy=look_dy,
        look_scale=host._look_input_scale,
        move_forward=move_forward,
        move_right=move_right,
        jump_pressed=(not menu_open) and jump_held and (not host._prev_jump_down),
        jump_held=(not menu_open) and jump_held,
        # Slide is hold-based (press to engage, release to stop).
        slide_pressed=(not menu_open) and slide_down,
        grapple_pressed=(not menu_open) and grapple_down and (not host._prev_grapple_down),
        noclip_toggle_pressed=(not menu_open) and noclip_toggle_down and (not host._prev_noclip_toggle_down),
        weapon_slot_select=int(weapon_slot_select),
        key_w_held=(not menu_open) and key_w_held,
        key_a_held=(not menu_open) and key_a_held,
        key_s_held=(not menu_open) and key_s_held,
        key_d_held=(not menu_open) and key_d_held,
        key_q_held=(not menu_open) and key_q_held,
        key_e_held=(not menu_open) and key_e_held,
        arrow_up_held=(not menu_open) and arrow_up_held,
        arrow_down_held=(not menu_open) and arrow_down_held,
        arrow_left_held=(not menu_open) and arrow_left_held,
        arrow_right_held=(not menu_open) and arrow_right_held,
        mouse_left_held=(not menu_open) and fire_down,
        mouse_right_held=(not menu_open) and grapple_down,
        raw_wasd_available=(not menu_open),
        raw_arrows_available=(not menu_open),
        raw_mouse_buttons_available=(not menu_open),
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
