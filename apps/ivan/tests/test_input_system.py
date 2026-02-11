from __future__ import annotations

from types import SimpleNamespace

from ivan.game import input_system


class _FakeProps:
    def __init__(self, *, foreground: bool = True, minimized: bool = False, opened: bool = True) -> None:
        self._foreground = bool(foreground)
        self._minimized = bool(minimized)
        self._opened = bool(opened)

    def getForeground(self) -> bool:
        return bool(self._foreground)

    def getMinimized(self) -> bool:
        return bool(self._minimized)

    def getOpen(self) -> bool:
        return bool(self._opened)


class _FakePointer:
    def __init__(self, win: "_FakeWin") -> None:
        self._win = win

    def getX(self) -> int:
        return int(self._win.pointer_x)

    def getY(self) -> int:
        return int(self._win.pointer_y)


class _FakeWin:
    def __init__(self, *, width: int = 1280, height: int = 720, props: _FakeProps | None = None) -> None:
        self._w = int(width)
        self._h = int(height)
        self._props = props if props is not None else _FakeProps()
        self.pointer_x = self._w // 2
        self.pointer_y = self._h // 2
        self.moves: list[tuple[int, int]] = []

    def getProperties(self) -> _FakeProps:
        return self._props

    def getXSize(self) -> int:
        return int(self._w)

    def getYSize(self) -> int:
        return int(self._h)

    def getPointer(self, _idx: int) -> _FakePointer:
        return _FakePointer(self)

    def movePointer(self, _idx: int, x: int, y: int) -> None:
        self.moves.append((int(x), int(y)))
        self.pointer_x = int(x)
        self.pointer_y = int(y)


class _FakeMouseWatcher:
    def __init__(self, *, pressed: set[str] | None = None) -> None:
        self._pressed = {str(x) for x in (pressed or set())}

    def isButtonDown(self, button) -> bool:
        name = button.getName() if hasattr(button, "getName") else str(button)
        return str(name) in self._pressed


class _FakeButtonMap:
    def __init__(self, *, mapping: dict[str, str]) -> None:
        self._mapping = dict(mapping)

    def getMappedButton(self, raw_key: str):
        from panda3d.core import ButtonHandle

        return ButtonHandle(self._mapping.get(str(raw_key), str(raw_key)))


class _FakeWinWithKeyboardMap:
    def __init__(self, *, mapping: dict[str, str]) -> None:
        self._mapping = dict(mapping)

    def getKeyboardMap(self):
        return _FakeButtonMap(mapping=self._mapping)


def _make_host(*, win: _FakeWin) -> SimpleNamespace:
    return SimpleNamespace(
        cfg=SimpleNamespace(smoke=False),
        _pointer_locked=True,
        _last_mouse=None,
        _mouse_dx_accum=0.0,
        _mouse_dy_accum=0.0,
        _mouse_capture_blocked=False,
        win=win,
    )


def _make_sample_host() -> SimpleNamespace:
    return SimpleNamespace(
        _look_input_scale=256,
        _mouse_dx_accum=0.0,
        _mouse_dy_accum=0.0,
        mouseWatcherNode=None,
        _prev_jump_down=False,
        _prev_grapple_down=False,
        _prev_noclip_toggle_down=False,
        _prev_demo_save_down=False,
        _prev_weapon_slot_down=[False, False, False, False, False, False],
        _noclip_toggle_key="v",
        _demo_save_key="f",
        _save_current_demo=lambda: None,
    )


def test_poll_mouse_look_delta_ignores_pointer_capture_when_window_not_foreground() -> None:
    props = _FakeProps(foreground=False, minimized=False, opened=True)
    win = _FakeWin(props=props)
    host = _make_host(win=win)
    win.pointer_x += 27
    win.pointer_y -= 13

    input_system.poll_mouse_look_delta(host)

    assert host._mouse_dx_accum == 0.0
    assert host._mouse_dy_accum == 0.0
    assert host._mouse_capture_blocked is True
    assert win.moves == []


def test_poll_mouse_look_delta_recenters_once_after_focus_returns_without_spike() -> None:
    props = _FakeProps(foreground=False, minimized=False, opened=True)
    win = _FakeWin(props=props)
    host = _make_host(win=win)
    win.pointer_x += 30
    win.pointer_y += 18

    # Focus lost: no capture.
    input_system.poll_mouse_look_delta(host)
    assert host._mouse_capture_blocked is True
    assert host._mouse_dx_accum == 0.0
    assert host._mouse_dy_accum == 0.0

    # Focus regained: first frame should only recenter and swallow delta.
    props._foreground = True
    input_system.poll_mouse_look_delta(host)
    assert host._mouse_capture_blocked is False
    assert host._mouse_dx_accum == 0.0
    assert host._mouse_dy_accum == 0.0
    assert win.moves[-1] == (win.getXSize() // 2, win.getYSize() // 2)

    # Subsequent frame: regular delta capture resumes.
    win.pointer_x += 5
    win.pointer_y -= 2
    input_system.poll_mouse_look_delta(host)
    assert host._mouse_dx_accum == 5.0
    assert host._mouse_dy_accum == -2.0


def test_sample_live_input_command_uses_lmb_for_fire_and_rmb_for_grapple(monkeypatch) -> None:
    host = _make_sample_host()
    pressed = {"mouse1", "mouse3"}
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, key: key in pressed)

    cmd = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd.mouse_left_held is True
    assert cmd.mouse_right_held is True
    assert cmd.grapple_pressed is True

    # Hold RMB on the next tick should not retrigger edge-only grapple attach.
    cmd2 = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd2.mouse_left_held is True
    assert cmd2.mouse_right_held is True
    assert cmd2.grapple_pressed is False


def test_sample_live_input_command_lmb_alone_does_not_trigger_grapple(monkeypatch) -> None:
    host = _make_sample_host()
    pressed = {"mouse1"}
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, key: key in pressed)

    cmd = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd.mouse_left_held is True
    assert cmd.mouse_right_held is False
    assert cmd.grapple_pressed is False


def test_is_key_down_supports_non_ascii_raw_fallback_for_wasd_lane() -> None:
    host = SimpleNamespace(mouseWatcherNode=_FakeMouseWatcher(pressed={"raw-s"}))
    assert input_system.is_key_down(host, "і") is True


def test_move_axes_from_keyboard_supports_ru_and_ua_symbols(monkeypatch) -> None:
    host = SimpleNamespace(mouseWatcherNode=_FakeMouseWatcher())
    pressed = {"ц", "в"}
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, key: key in pressed)

    fwd, right = input_system.move_axes_from_keyboard(host)
    assert (fwd, right) == (1, 1)

    pressed = {"і", "ф"}
    fwd2, right2 = input_system.move_axes_from_keyboard(host)
    assert (fwd2, right2) == (-1, -1)


def test_move_axes_from_keyboard_supports_azerty_aliases(monkeypatch) -> None:
    host = SimpleNamespace(mouseWatcherNode=_FakeMouseWatcher())
    pressed = {"z", "q"}
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, key: key in pressed)

    fwd, right = input_system.move_axes_from_keyboard(host)
    assert (fwd, right) == (1, -1)


def test_move_axes_from_keyboard_uses_keyboard_map_for_physical_wasd_lane() -> None:
    host = SimpleNamespace(
        mouseWatcherNode=_FakeMouseWatcher(pressed={"slash"}),
        win=_FakeWinWithKeyboardMap(mapping={"w": "slash"}),
    )
    fwd, right = input_system.move_axes_from_keyboard(host)
    assert (fwd, right) == (1, 0)


def test_sample_live_input_command_detects_slots_5_and_6_on_edge(monkeypatch) -> None:
    host = _make_sample_host()
    pressed: set[str] = {"5"}
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, key: key in pressed)

    cmd_5 = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd_5.weapon_slot_select == 5

    cmd_hold = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd_hold.weapon_slot_select == 0

    pressed = {"6"}
    cmd_6 = input_system.sample_live_input_command(host, menu_open=False)
    assert cmd_6.weapon_slot_select == 6


def test_sample_live_input_command_tracks_qe_held_flags(monkeypatch) -> None:
    host = _make_sample_host()
    host.mouseWatcherNode = _FakeMouseWatcher()
    pressed_raw = {"q", "e"}
    monkeypatch.setattr(input_system, "_is_raw_lane_down", lambda _host, raw_key: raw_key in pressed_raw)
    monkeypatch.setattr(input_system, "_any_layout_key_down", lambda _host, _keys: False)
    monkeypatch.setattr(input_system, "move_axes_from_keyboard", lambda _host: (0, 0))
    monkeypatch.setattr(input_system, "is_key_down", lambda _host, _key: False)

    cmd = input_system.sample_live_input_command(host, menu_open=False)

    assert cmd.key_q_held is True
    assert cmd.key_e_held is True
