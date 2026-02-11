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
        _prev_weapon_slot_down=[False, False, False, False],
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
