from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from types import SimpleNamespace

from ivan.game import RunnerDemo
from ivan.game import app as app_mod
from ivan.game import netcode as netcode_mod
from ivan.game import tuning_profiles as profiles_mod
from ivan.net.protocol import InputCommand, decode_input_packet
from ivan.net.relevance import GoldSrcPvsRelevance
from ivan.physics.tuning import PhysicsTuning
from ivan.net.server import MultiplayerServer
from ivan.games import RaceCourse, RaceEvent
from ivan.course.time_trial import make_marker_cylinder
from ivan.world.goldsrc_visibility import GoldSrcBspVis
from panda3d.core import LVector3f


class _FakeUI:
    def __init__(self) -> None:
        self.last_status = ""
        self.last_profiles: tuple[list[str], str] | None = None

    def set_status(self, text: str) -> None:
        self.last_status = str(text)

    def set_profiles(self, names: list[str], active: str) -> None:
        self.last_profiles = (list(names), str(active))


class _FakeNetClient:
    def __init__(self) -> None:
        self.respawn_calls = 0
        self.interact_calls = 0

    def send_respawn(self) -> None:
        self.respawn_calls += 1

    def send_interact(self) -> None:
        self.interact_calls += 1


class _FakePauseUI:
    def __init__(self) -> None:
        self.open_to_network = False
        self.keybind_status = ""
        self.connect_target: tuple[str, int] | None = None
        self.multiplayer_status = ""

    def set_open_to_network(self, value: bool) -> None:
        self.open_to_network = bool(value)

    def set_keybind_status(self, text: str) -> None:
        self.keybind_status = str(text)

    def set_connect_target(self, host: str, port: int) -> None:
        self.connect_target = (str(host), int(port))

    def set_multiplayer_status(self, text: str) -> None:
        self.multiplayer_status = str(text)


class _FakeNoclipPlayer:
    def __init__(self) -> None:
        self.pos = LVector3f(0.0, 0.0, 0.0)
        self.vel = LVector3f(0.0, 0.0, 0.0)
        self.grounded = True

    def set_external_velocity(self, *, vel: LVector3f, reason: str = "external") -> None:
        _ = reason
        self.vel = LVector3f(vel)


class _FakeNode:
    def __init__(self, name: str = "node") -> None:
        self.name = str(name)
        self.parent: _FakeNode | None = None
        self.children: list[_FakeNode] = []
        self.scale: tuple[float, float, float] | None = None
        self.color: tuple[float, float, float, float] | None = None
        self.pos: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.hpr: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.removed = False

    def attachNewNode(self, name: str) -> "_FakeNode":
        child = _FakeNode(name=name)
        child.parent = self
        self.children.append(child)
        return child

    def reparentTo(self, parent: "_FakeNode") -> None:
        self.parent = parent
        parent.children.append(self)

    def setScale(self, x: float, y: float, z: float) -> None:
        self.scale = (float(x), float(y), float(z))

    def setColor(self, r: float, g: float, b: float, a: float) -> None:
        self.color = (float(r), float(g), float(b), float(a))

    def setPos(self, x: float | LVector3f, y: float | None = None, z: float | None = None) -> None:
        if isinstance(x, LVector3f):
            self.pos = (float(x.x), float(x.y), float(x.z))
            return
        self.pos = (float(x), float(y or 0.0), float(z or 0.0))

    def setHpr(self, h: float, p: float, r: float) -> None:
        self.hpr = (float(h), float(p), float(r))

    def removeNode(self) -> None:
        self.removed = True


class _FakeLoader:
    def __init__(self) -> None:
        self.models: list[_FakeNode] = []

    def loadModel(self, _path: str) -> _FakeNode:
        node = _FakeNode(name="model")
        self.models.append(node)
        return node


class _FakeWindowProps:
    def __init__(self, *, fullscreen: bool) -> None:
        self._fullscreen = bool(fullscreen)

    def getFullscreen(self) -> bool:
        return bool(self._fullscreen)


class _FakeWindow:
    def __init__(self, *, width: int, height: int, fullscreen: bool) -> None:
        self._w = int(width)
        self._h = int(height)
        self._props = _FakeWindowProps(fullscreen=fullscreen)
        self.requested_sizes: list[tuple[int, int]] = []

    def getProperties(self) -> _FakeWindowProps:
        return self._props

    def getXSize(self) -> int:
        return int(self._w)

    def getYSize(self) -> int:
        return int(self._h)

    def requestProperties(self, props) -> None:
        get_x = getattr(props, "getXSize", None)
        get_y = getattr(props, "getYSize", None)
        if callable(get_x) and callable(get_y):
            self._w = int(get_x())
            self._h = int(get_y())
            self.requested_sizes.append((self._w, self._h))


def _sample_race_course() -> RaceCourse:
    mission = make_marker_cylinder(pos=LVector3f(0.0, 0.0, 1.0), radius=2.5, half_z=2.0)
    start = make_marker_cylinder(pos=LVector3f(8.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    finish = make_marker_cylinder(pos=LVector3f(16.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    return RaceCourse(mission_marker=mission, start=start, checkpoints=(), finish=finish)


def test_network_respawn_button_sends_server_request() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._net_connected = True
    demo._net_client = _FakeNetClient()
    demo._net_pending_inputs = [SimpleNamespace(seq=1, cmd="cmd")]
    demo._net_predicted_states = [SimpleNamespace(seq=1)]
    demo._net_last_acked_seq = 0
    demo._net_seq_counter = 3
    demo.ui = _FakeUI()
    local_respawn_called = {"value": False}
    demo._do_respawn = lambda *, from_mode: local_respawn_called.__setitem__("value", True)

    RunnerDemo._on_respawn_pressed(demo)

    assert demo._net_client.respawn_calls == 1
    assert local_respawn_called["value"] is True
    assert demo._net_pending_inputs == []
    assert demo._net_predicted_states == []
    assert demo._net_last_acked_seq == 3
    assert "Respawn requested" in demo.ui.last_status


def test_respawn_button_offline_uses_local_respawn() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._feel_capture_open = False
    demo._net_connected = False
    demo._net_client = None
    demo.ui = _FakeUI()
    calls = {"count": 0, "from_mode": None}

    def _local_respawn(*, from_mode: bool) -> None:
        calls["count"] += 1
        calls["from_mode"] = bool(from_mode)

    demo._do_respawn = _local_respawn
    RunnerDemo._on_respawn_pressed(demo)

    assert calls["count"] == 1
    assert calls["from_mode"] is False


def test_respawn_button_ignored_while_feel_capture_open() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._feel_capture_open = True
    demo.ui = _FakeUI()
    calls = {"count": 0}
    demo._do_respawn = lambda *, from_mode: calls.__setitem__("count", int(calls["count"]) + 1)

    RunnerDemo._on_respawn_pressed(demo)

    assert calls["count"] == 0
    assert "Feel capture is open" in demo.ui.last_status


def test_interact_button_network_path_uses_reliable_client_message() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._mode = "game"
    demo.player = SimpleNamespace(pos=LVector3f(0.0, 0.0, 1.0))
    demo._net_connected = True
    demo._net_client = _FakeNetClient()
    demo._race_editor_enabled = False
    demo._pause_menu_open = False
    demo._debug_menu_open = False
    demo._replay_browser_open = False
    demo._console_open = False
    demo._feel_capture_open = False
    demo._net_interact_pending = True

    RunnerDemo._on_interact_pressed(demo)

    assert demo._net_client.interact_calls == 1
    assert demo._net_interact_pending is False


def test_embedded_server_receives_host_tuning_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeEmbeddedServer:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def start(self) -> None:
            captured["started"] = True

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._embedded_server = None
    demo._open_to_network = True
    demo._runtime_connect_port = 7777
    demo._current_map_json = "/tmp/test_map.json"
    demo._current_tuning_snapshot = lambda: {"jump_height": 1.2, "jump_apex_time": 0.3, "surf_enabled": True}
    demo.cfg = SimpleNamespace(net_host=None)

    import ivan.game as game_mod

    monkeypatch.setattr(game_mod, "EmbeddedHostServer", _FakeEmbeddedServer)
    monkeypatch.setattr(game_mod.time, "sleep", lambda _v: None)

    ok = RunnerDemo._start_embedded_server(demo)
    assert ok is True
    assert captured["started"] is True
    assert captured["host"] == "0.0.0.0"
    assert captured["tcp_port"] == 7777
    assert captured["udp_port"] == 7778
    assert captured["map_json"] == "/tmp/test_map.json"
    assert captured["initial_tuning"] == {"jump_height": 1.2, "jump_apex_time": 0.3, "surf_enabled": True}


def test_embedded_server_uses_current_player_spawn_override(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeEmbeddedServer:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def start(self) -> None:
            captured["started"] = True

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._embedded_server = None
    demo._open_to_network = True
    demo._runtime_connect_port = 7777
    demo._current_map_json = "/tmp/test_map.map"
    demo._current_tuning_snapshot = lambda: {"jump_height": 1.2}
    demo.cfg = SimpleNamespace(net_host=None)
    demo.player = SimpleNamespace(pos=LVector3f(12.5, -8.0, 3.25))
    demo._yaw = 123.0

    import ivan.game as game_mod

    monkeypatch.setattr(game_mod, "EmbeddedHostServer", _FakeEmbeddedServer)
    monkeypatch.setattr(game_mod.time, "sleep", lambda _v: None)

    ok = RunnerDemo._start_embedded_server(demo)
    assert ok is True
    assert captured["started"] is True
    assert captured["initial_spawn"] == (12.5, -8.0, 3.25)
    assert captured["initial_spawn_yaw"] == 123.0


def test_open_to_network_uses_active_client_tuning_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeEmbeddedServer:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def start(self) -> None:
            captured["started"] = True

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._embedded_server = None
    demo._open_to_network = False
    demo._net_connected = False
    demo._runtime_connect_host = None
    demo._runtime_connect_port = 7777
    demo._current_map_json = "/tmp/test_map.json"
    demo.pause_ui = _FakePauseUI()
    demo.cfg = SimpleNamespace(net_host=None)
    demo._stop_embedded_server = lambda: None
    demo._current_tuning_snapshot = lambda: {
        "run_t90": 0.04656740038574615,
        "ground_stop_t90": 0.16841168101466534,
        "surf_enabled": True,
        "air_gain_t90": 0.9 / 31.738659286499026,
        "grapple_pull_strength": 30.263092041015625,
    }
    demo._connect_multiplayer_if_requested = lambda: RunnerDemo._start_embedded_server(demo)

    import ivan.game as game_mod

    monkeypatch.setattr(game_mod, "EmbeddedHostServer", _FakeEmbeddedServer)
    monkeypatch.setattr(game_mod.time, "sleep", lambda _v: None)

    RunnerDemo._on_toggle_open_network(demo, True)

    assert demo.pause_ui.open_to_network is True
    assert captured["started"] is True
    assert captured["initial_tuning"] == {
        "run_t90": 0.04656740038574615,
        "ground_stop_t90": 0.16841168101466534,
        "surf_enabled": True,
        "air_gain_t90": 0.9 / 31.738659286499026,
        "grapple_pull_strength": 30.263092041015625,
    }


def test_open_to_network_restarts_embedded_server_before_connect() -> None:
    host = SimpleNamespace()
    host._open_to_network = False
    host._runtime_connect_host = "example.com"
    host._runtime_connect_port = 7777
    host._net_connected = False
    host.pause_ui = _FakePauseUI()
    calls = {"stop": 0, "connect": 0}
    host._stop_embedded_server = lambda: calls.__setitem__("stop", calls["stop"] + 1)
    host._connect_multiplayer_if_requested = lambda: calls.__setitem__("connect", calls["connect"] + 1)

    netcode_mod.on_toggle_open_network(host, True)

    assert calls["stop"] == 1
    assert calls["connect"] == 1
    assert host._runtime_connect_host is None
    assert host.pause_ui.connect_target == ("127.0.0.1", 7777)


def test_connect_multiplayer_applies_server_welcome_spawn(monkeypatch) -> None:
    class _FakeClient:
        def __init__(self, *, host: str, tcp_port: int, name: str) -> None:
            self.host = host
            self.tcp_port = tcp_port
            self.name = name
            self.server_map_json = None
            self.can_configure = True
            self.player_id = 3
            self.server_tuning_version = 0
            self.server_tuning = None
            self.server_spawn = (12.0, -7.0, 4.5)
            self.server_spawn_yaw = 215.0

        def close(self) -> None:
            return

    monkeypatch.setattr(app_mod, "MultiplayerClient", _FakeClient)
    monkeypatch.setattr(app_mod, "update_state", lambda **_kwargs: None)

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._disconnect_multiplayer = lambda: None
    demo._embedded_server = None
    demo._open_to_network = False
    demo._runtime_connect_host = "127.0.0.1"
    demo._runtime_connect_port = 7777
    demo.cfg = SimpleNamespace(net_name="tester")
    demo._current_map_json = "/tmp/test.map"
    demo._net_client = None
    demo._net_connected = False
    demo._net_can_configure = False
    demo._net_player_id = 0
    demo._net_seq_counter = 0
    demo._net_last_server_tick = 0
    demo._net_last_acked_seq = 0
    demo._net_local_respawn_seq = 0
    demo._net_last_snapshot_local_time = 0.0
    demo._net_authoritative_tuning_version = 0
    demo._net_cfg_apply_pending_version = 0
    demo._net_cfg_apply_sent_at = 0.0
    demo._net_pending_inputs = []
    demo._net_predicted_states = []
    demo._net_snapshot_intervals = []
    demo._net_server_tick_offset_ready = False
    demo._net_server_tick_offset_ticks = 0.0
    demo._net_reconcile_pos_offset = LVector3f(0, 0, 0)
    demo._net_reconcile_yaw_offset = 0.0
    demo._net_reconcile_pitch_offset = 0.0
    demo._net_perf_last_publish = 0.0
    demo._net_perf_text = ""
    demo._apply_authoritative_tuning = lambda *, tuning, version: None
    demo._camera_observer = SimpleNamespace(reset=lambda: None)
    demo._camera_tilt_observer = SimpleNamespace(reset=lambda: None)
    demo._camera_height_observer = SimpleNamespace(reset=lambda: None)
    demo._camera_feedback_observer = SimpleNamespace(reset=lambda: None)
    demo._net_perf = SimpleNamespace(reset=lambda: None)
    snap_calls = {"count": 0}
    demo._push_sim_snapshot = lambda: snap_calls.__setitem__("count", snap_calls["count"] + 1)
    demo.player = SimpleNamespace(pos=LVector3f(1.0, 2.0, 3.0), vel=LVector3f(4.0, 5.0, 6.0))
    demo._yaw = 12.0
    demo._pitch = 7.0
    demo.ui = _FakeUI()
    demo.pause_ui = _FakePauseUI()
    demo.error_log = SimpleNamespace(log_message=lambda **_kwargs: None)
    demo.error_console = SimpleNamespace(refresh=lambda **_kwargs: None)
    demo._stop_embedded_server = lambda: None

    RunnerDemo._connect_multiplayer_if_requested(demo)

    assert demo._net_connected is True
    assert demo._net_player_id == 3
    assert abs(float(demo.player.pos.x) - 12.0) < 1e-6
    assert abs(float(demo.player.pos.y) - (-7.0)) < 1e-6
    assert abs(float(demo.player.pos.z) - 4.5) < 1e-6
    assert abs(float(demo.player.vel.length())) < 1e-9
    assert abs(float(demo._yaw) - 215.0) < 1e-6
    assert abs(float(demo._pitch) - 0.0) < 1e-6
    assert snap_calls["count"] == 1


def test_resolve_server_map_reference_rebases_apps_ivan_path(monkeypatch, tmp_path: Path) -> None:
    app_root = tmp_path / "repo" / "apps" / "ivan"
    target = app_root / "assets" / "maps" / "demo" / "demo_alt.map"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// map", encoding="utf-8")

    monkeypatch.setattr(app_mod, "ivan_app_root", lambda: app_root)

    demo = RunnerDemo.__new__(RunnerDemo)
    resolved = RunnerDemo._resolve_server_map_reference(
        demo,
        server_map_json="/Users/host-user/repo/apps/ivan/assets/maps/demo/demo_alt.map",
    )
    assert resolved is not None
    assert Path(str(resolved)).resolve() == target.resolve()


def test_connect_multiplayer_loads_resolved_server_map_path(monkeypatch, tmp_path: Path) -> None:
    app_root = tmp_path / "repo" / "apps" / "ivan"
    target = app_root / "assets" / "maps" / "demo" / "demo_alt.map"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// map", encoding="utf-8")
    monkeypatch.setattr(app_mod, "ivan_app_root", lambda: app_root)

    class _FakeClient:
        def __init__(self, *, host: str, tcp_port: int, name: str) -> None:
            self.host = host
            self.tcp_port = tcp_port
            self.name = name
            self.server_map_json = "/Users/host-user/repo/apps/ivan/assets/maps/demo/demo_alt.map"
            self.can_configure = True
            self.player_id = 1
            self.server_tuning_version = 0
            self.server_tuning = None
            self.server_spawn = (0.0, 0.0, 2.0)
            self.server_spawn_yaw = 0.0

        def close(self) -> None:
            return

    monkeypatch.setattr(app_mod, "MultiplayerClient", _FakeClient)

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._disconnect_multiplayer = lambda: None
    demo._embedded_server = None
    demo._open_to_network = False
    demo._runtime_connect_host = "127.0.0.1"
    demo._runtime_connect_port = 7777
    demo.cfg = SimpleNamespace(net_name="tester")
    demo._current_map_json = "/different/local/path.map"
    demo._net_client = None
    demo._net_connected = False
    demo._net_player_id = 0
    demo._net_interact_pending = False
    demo.pause_ui = _FakePauseUI()
    demo.ui = _FakeUI()
    demo.error_log = SimpleNamespace(log_message=lambda **_kwargs: None)
    demo.error_console = SimpleNamespace(refresh=lambda **_kwargs: None)
    started: dict[str, str] = {}
    demo._start_game = lambda *, map_json, lighting=None: started.__setitem__("map_json", str(map_json))

    RunnerDemo._connect_multiplayer_if_requested(demo)

    assert Path(started["map_json"]).resolve() == target.resolve()


def test_connect_multiplayer_fails_if_server_map_is_unavailable(monkeypatch) -> None:
    class _FakeClient:
        def __init__(self, *, host: str, tcp_port: int, name: str) -> None:
            self.host = host
            self.tcp_port = tcp_port
            self.name = name
            self.server_map_json = "/missing/host/path/unavailable.map"
            self.can_configure = True
            self.player_id = 1
            self.server_tuning_version = 0
            self.server_tuning = None
            self.server_spawn = (0.0, 0.0, 2.0)
            self.server_spawn_yaw = 0.0

        def close(self) -> None:
            return

    monkeypatch.setattr(app_mod, "MultiplayerClient", _FakeClient)
    monkeypatch.setattr(app_mod, "ivan_app_root", lambda: Path("/nonexistent/app/root"))

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._disconnect_multiplayer = lambda: None
    demo._embedded_server = None
    demo._open_to_network = False
    demo._runtime_connect_host = "127.0.0.1"
    demo._runtime_connect_port = 7777
    demo.cfg = SimpleNamespace(net_name="tester")
    demo._current_map_json = "/different/local/path.map"
    demo._net_client = None
    demo._net_connected = False
    demo._net_player_id = 0
    demo._net_interact_pending = False
    demo.pause_ui = _FakePauseUI()
    demo.ui = _FakeUI()
    msgs: list[str] = []
    demo.error_log = SimpleNamespace(log_message=lambda **kwargs: msgs.append(str(kwargs.get("message") or "")))
    demo.error_console = SimpleNamespace(refresh=lambda **_kwargs: None)
    demo._start_game = lambda *, map_json, lighting=None: (_ for _ in ()).throw(AssertionError("must not start game"))

    RunnerDemo._connect_multiplayer_if_requested(demo)

    assert demo._net_client is None
    assert demo._net_connected is False
    assert "server map" in demo.pause_ui.multiplayer_status.lower()
    assert any("server map is unavailable locally" in m.lower() for m in msgs)


def test_connect_multiplayer_host_mode_does_not_fallback_when_port_is_busy(monkeypatch) -> None:
    class _ShouldNotConnectClient:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("MultiplayerClient should not be created when host bind fails")

    monkeypatch.setattr(app_mod, "MultiplayerClient", _ShouldNotConnectClient)

    demo = RunnerDemo.__new__(RunnerDemo)
    demo._disconnect_multiplayer = lambda: None
    demo._embedded_server = None
    demo._open_to_network = True
    demo._runtime_connect_host = None
    demo._runtime_connect_port = 7777
    demo._start_embedded_server = lambda: False
    demo.cfg = SimpleNamespace(net_name="tester")
    demo.ui = _FakeUI()
    demo.pause_ui = _FakePauseUI()
    demo._net_client = None

    RunnerDemo._connect_multiplayer_if_requested(demo)

    assert demo._net_client is None
    assert "busy" in demo.pause_ui.multiplayer_status.lower()


def test_handle_kill_plane_skips_local_respawn_while_network_connected() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.player = SimpleNamespace(pos=LVector3f(0.0, 0.0, -11.0))
    demo.scene = SimpleNamespace(kill_z=-10.0)
    demo._net_connected = True
    demo._net_client = object()
    calls = {"count": 0}
    demo._do_respawn = lambda *, from_mode: calls.__setitem__("count", calls["count"] + 1)

    RunnerDemo._handle_kill_plane(demo)
    assert calls["count"] == 0

    demo._net_connected = False
    demo._net_client = None
    RunnerDemo._handle_kill_plane(demo)
    assert calls["count"] == 1


def test_disconnect_from_menu_clears_runtime_connect_target(monkeypatch) -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._runtime_connect_host = "203.0.113.42"
    demo._runtime_connect_port = 7777
    demo._open_to_network = False
    demo.pause_ui = _FakePauseUI()
    called = {"disconnect": 0}

    def _fake_disconnect(_host) -> None:
        called["disconnect"] += 1

    monkeypatch.setattr(netcode_mod, "disconnect_multiplayer", _fake_disconnect)

    netcode_mod.on_disconnect_server_from_menu(demo)

    assert called["disconnect"] == 1
    assert demo._runtime_connect_host is None
    assert demo.pause_ui.connect_target == ("127.0.0.1", 7777)


def test_current_tuning_snapshot_reflects_active_client_values() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.tuning = PhysicsTuning()
    demo.tuning.jump_height = 1.7
    demo.tuning.jump_apex_time = 0.33
    demo.tuning.surf_enabled = True
    demo.tuning.air_speed_mult = 1.42

    snap = RunnerDemo._current_tuning_snapshot(demo)

    assert float(snap["jump_height"]) == 1.7
    assert float(snap["jump_apex_time"]) == 0.33
    assert bool(snap["surf_enabled"]) is True
    assert float(snap["air_speed_mult"]) == 1.42


def test_noclip_forward_uses_view_pitch_direction() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.player = _FakeNoclipPlayer()
    demo.tuning = PhysicsTuning(noclip_speed=5.0)
    demo._yaw = 0.0
    demo._pitch = 45.0

    RunnerDemo._step_noclip(
        demo,
        dt=1.0,
        move_forward=1,
        move_right=0,
        jump_held=False,
        slide_pressed=False,
    )

    assert demo.player.vel.y > 0.0
    assert demo.player.vel.z > 0.0
    assert demo.player.pos.y > 0.0
    assert demo.player.pos.z > 0.0


def test_noclip_toggle_is_blocked_in_multiplayer_gameplay() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._net_connected = True
    demo._race_editor_enabled = False
    demo.tuning = PhysicsTuning(noclip_enabled=True)
    demo.ui = _FakeUI()

    RunnerDemo._toggle_noclip(demo)

    assert bool(demo.tuning.noclip_enabled) is False
    assert "disabled in multiplayer" in demo.ui.last_status.lower()


def test_remote_player_visual_is_white_and_character_sized() -> None:
    host = SimpleNamespace(
        _remote_players={},
        world_root=_FakeNode(name="world-root"),
        loader=_FakeLoader(),
        tuning=PhysicsTuning(player_radius=0.42, player_half_height=1.05),
    )

    rp = netcode_mod.ensure_remote_player_visual(host, player_id=2, name="friend")

    assert rp.player_id == 2
    assert len(host.loader.models) == 2
    body = host.loader.models[0]
    head = host.loader.models[1]
    assert body.scale is not None
    assert abs(float(body.scale[0]) - 0.84) < 1e-6
    assert abs(float(body.scale[1]) - 0.84) < 1e-6
    assert abs(float(body.scale[2]) - 2.10) < 1e-6
    assert body.color == (1.0, 1.0, 1.0, 1.0)
    assert head.color is not None
    assert min(head.color[:3]) >= 0.9


def test_poll_network_snapshot_notifies_when_new_remote_player_joins(monkeypatch) -> None:
    class _FakeSnapshotClient:
        def __init__(self, snapshots: list[dict]) -> None:
            self._snapshots = list(snapshots)

        def poll(self) -> dict | None:
            if not self._snapshots:
                return None
            return dict(self._snapshots.pop(0))

    def _row(*, pid: int, name: str) -> dict:
        return {
            "id": int(pid),
            "n": str(name),
            "x": 0.0,
            "y": 0.0,
            "z": 1.0,
            "yaw": 0.0,
            "pitch": 0.0,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "ack": 0,
            "hp": 100,
            "rs": 0,
        }

    # Avoid graphics setup in this test; keep only join-notification behavior.
    def _fake_ensure(host_obj, *, player_id: int, name: str):
        rp = host_obj._remote_players.get(int(player_id))
        if rp is not None:
            return rp
        node = _FakeNode(name=f"remote-{int(player_id)}")
        rp = netcode_mod._RemotePlayerVisual(
            player_id=int(player_id),
            root_np=node,
            head_np=node,
            name=str(name),
        )
        host_obj._remote_players[int(player_id)] = rp
        return rp

    monkeypatch.setattr(netcode_mod, "ensure_remote_player_visual", _fake_ensure)

    statuses: list[str] = []
    notices: list[str] = []
    host = SimpleNamespace(
        _net_connected=True,
        _net_client=_FakeSnapshotClient(
            snapshots=[
                {"tick": 1, "players": [_row(pid=1, name="self"), _row(pid=2, name="buddy")]},
                {"tick": 2, "players": [_row(pid=1, name="self"), _row(pid=2, name="buddy")]},
            ]
        ),
        _net_last_server_tick=0,
        _net_last_snapshot_local_time=0.0,
        _net_perf=SimpleNamespace(
            snapshot_count=0,
            snapshot_dt_sum=0.0,
            snapshot_dt_max=0.0,
            reconcile_count=0,
            reconcile_pos_err_sum=0.0,
            reconcile_pos_err_max=0.0,
            replay_input_sum=0,
            replay_input_max=0,
            replay_time_sum_ms=0.0,
            replay_time_max_ms=0.0,
        ),
        _net_snapshot_intervals=[],
        _net_interp_delay_ticks=6.0,
        _sim_tick_rate_hz=60,
        _net_cfg_apply_pending_version=0,
        _net_cfg_apply_sent_at=0.0,
        _net_server_tick_offset_ready=False,
        _net_server_tick_offset_ticks=0.0,
        _net_server_tick_offset_smooth=0.12,
        _net_authoritative_tuning_version=0,
        _apply_authoritative_tuning=lambda **_kwargs: None,
        _net_games_version=0,
        _net_player_id=1,
        _local_hp=100,
        player=SimpleNamespace(pos=LVector3f(0.0, 0.0, 1.0), vel=LVector3f(0.0, 0.0, 0.0)),
        _playback_active=False,
        _net_local_respawn_seq=0,
        _net_pending_inputs=[],
        _net_predicted_states=[],
        _net_last_acked_seq=0,
        _yaw=0.0,
        _pitch=0.0,
        _net_reconcile_pos_offset=LVector3f(0.0, 0.0, 0.0),
        _net_reconcile_yaw_offset=0.0,
        _net_reconcile_pitch_offset=0.0,
        _camera_observer=SimpleNamespace(reset=lambda: None),
        _camera_tilt_observer=SimpleNamespace(reset=lambda: None),
        _camera_height_observer=SimpleNamespace(reset=lambda: None),
        _camera_feedback_observer=SimpleNamespace(reset=lambda: None),
        _start_new_demo_recording=lambda: None,
        _reconcile_local_from_server=lambda **_kwargs: None,
        _remote_players={},
        _net_seen_remote_players=set(),
        ui=SimpleNamespace(set_status=lambda msg: statuses.append(str(msg))),
        race_ui_feedback=SimpleNamespace(notice=lambda **kwargs: notices.append(str(kwargs.get("text") or ""))),
    )

    netcode_mod.poll_network_snapshot(host)
    netcode_mod.poll_network_snapshot(host)

    join_statuses = [s for s in statuses if "joined the server." in s]
    join_notices = [s for s in notices if "joined the server." in s]
    assert join_statuses == ["buddy joined the server."]
    assert join_notices == ["buddy joined the server."]


def test_window_resize_event_persists_window_size_on_windows(monkeypatch) -> None:
    calls: list[dict[str, int | bool]] = []
    monkeypatch.setattr(app_mod, "update_state", lambda **kwargs: calls.append(kwargs))
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.cfg = SimpleNamespace(smoke=False)
    demo._window_resize_persist_enabled = True
    demo._last_persisted_window_size = (1280, 720)
    demo.win = _FakeWindow(width=1600, height=900, fullscreen=False)

    RunnerDemo._on_window_event(demo, demo.win)
    RunnerDemo._on_window_event(demo, demo.win)

    assert calls == [{"fullscreen": False, "window_width": 1600, "window_height": 900}]
    assert demo._last_persisted_window_size == (1600, 900)


def test_window_resize_event_is_ignored_off_windows_and_fullscreen(monkeypatch) -> None:
    calls: list[dict[str, int | bool]] = []
    monkeypatch.setattr(app_mod, "update_state", lambda **kwargs: calls.append(kwargs))
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.cfg = SimpleNamespace(smoke=False)
    demo._last_persisted_window_size = (1280, 720)

    demo._window_resize_persist_enabled = False
    demo.win = _FakeWindow(width=1600, height=900, fullscreen=False)
    RunnerDemo._on_window_event(demo, demo.win)

    demo._window_resize_persist_enabled = True
    demo.win = _FakeWindow(width=1600, height=900, fullscreen=True)
    RunnerDemo._on_window_event(demo, demo.win)

    assert calls == []


def test_window_resize_event_clamps_pathological_window_shape(monkeypatch) -> None:
    calls: list[dict[str, int | bool]] = []
    monkeypatch.setattr(app_mod, "update_state", lambda **kwargs: calls.append(kwargs))
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.cfg = SimpleNamespace(smoke=False)
    demo._window_resize_persist_enabled = True
    demo._last_persisted_window_size = (1280, 720)
    demo.win = _FakeWindow(width=600, height=1000, fullscreen=False)

    RunnerDemo._on_window_event(demo, demo.win)

    assert calls == [{"fullscreen": False, "window_width": 1778, "window_height": 1000}]
    assert demo._last_persisted_window_size == (1778, 1000)
    assert demo.win.requested_sizes == [(1778, 1000)]


def test_reconcile_uses_ack_state_and_replays_unacked_inputs() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._playback_active = False
    demo._net_last_acked_seq = 4
    demo._net_pending_inputs = [
        SimpleNamespace(seq=5, cmd="cmd5"),
        SimpleNamespace(seq=6, cmd="cmd6"),
    ]
    demo._net_predicted_states = [
        SimpleNamespace(seq=5, pos=LVector3f(10.0, 0.0, 0.0), vel=LVector3f(1.0, 0.0, 0.0), yaw=0.0, pitch=0.0),
        SimpleNamespace(seq=6, pos=LVector3f(12.0, 0.0, 0.0), vel=LVector3f(1.0, 0.0, 0.0), yaw=0.0, pitch=0.0),
    ]
    demo._net_reconcile_pos_offset = LVector3f(0.0, 0.0, 0.0)
    demo._yaw = 0.0
    demo._pitch = 0.0
    demo._angle_delta_deg = lambda a, b: float(b) - float(a)
    replayed: list[str] = []
    appended: list[int] = []
    demo._simulate_input_tick = (
        lambda *, cmd, menu_open, network_send, record_demo, capture_snapshot: replayed.append(cmd)
    )
    demo._append_predicted_state = lambda *, seq: appended.append(int(seq))
    demo._push_sim_snapshot = lambda: None
    demo._net_perf = SimpleNamespace(
        reconcile_count=0,
        reconcile_pos_err_sum=0.0,
        reconcile_pos_err_max=0.0,
        replay_input_sum=0,
        replay_input_max=0,
        replay_time_sum_ms=0.0,
        replay_time_max_ms=0.0,
    )
    demo.player = SimpleNamespace(pos=LVector3f(5.0, 0.0, 0.0), vel=LVector3f(0.0, 0.0, 0.0))

    RunnerDemo._reconcile_local_from_server(
        demo,
        x=10.6,
        y=0.0,
        z=0.0,
        vx=1.0,
        vy=0.0,
        vz=0.0,
        yaw=0.0,
        pitch=0.0,
        ack=5,
    )

    assert demo._net_last_acked_seq == 5
    assert [p.seq for p in demo._net_pending_inputs] == [6]
    assert replayed == ["cmd6"]
    assert appended == [6]


def test_apply_profile_in_network_owner_pushes_to_server() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._profiles = {"p1": {"jump_height": 1.3, "jump_apex_time": 0.30}}
    demo._active_profile_name = "surf_bhop_c2"
    demo._profile_names = lambda: ["p1"]
    demo._net_connected = True
    demo._net_can_configure = True
    demo.ui = _FakeUI()
    calls = {"apply": 0, "send": 0}
    demo._apply_profile_snapshot = lambda values, persist: calls.__setitem__("apply", calls["apply"] + 1)
    demo._send_tuning_to_server = lambda: calls.__setitem__("send", calls["send"] + 1)

    RunnerDemo._apply_profile(demo, "p1")

    assert demo._active_profile_name == "p1"
    assert calls["apply"] == 1
    assert calls["send"] == 1
    assert demo.ui.last_profiles == (["p1"], "p1")


def test_apply_profile_readonly_client_is_blocked() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo._profiles = {"p1": {"jump_height": 1.3, "jump_apex_time": 0.30}}
    demo._active_profile_name = "surf_bhop_c2"
    demo._profile_names = lambda: ["p1", "surf_bhop_c2"]
    demo._net_connected = True
    demo._net_can_configure = False
    demo._net_authoritative_tuning = {"jump_height": 1.0, "jump_apex_time": 0.22}
    demo.ui = _FakeUI()
    calls = {"apply": 0}

    def _apply(values, persist):
        calls["apply"] += 1

    demo._apply_profile_snapshot = _apply

    RunnerDemo._apply_profile(demo, "p1")

    assert demo._active_profile_name == "surf_bhop_c2"
    assert calls["apply"] == 1
    assert "host-only" in demo.ui.last_status
    assert demo.ui.last_profiles == (["p1", "surf_bhop_c2"], "surf_bhop_c2")


def test_dedicated_server_defaults_match_surf_bhop_c2_core_values(monkeypatch) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=None)
    try:
        assert abs(float(srv.tuning.jump_height) - 1.0108081703186036) < 1e-6
        assert abs(float(srv.tuning.jump_apex_time) - 0.22585349306495618) < 1e-6
        assert abs(float(srv.tuning.max_ground_speed) - 6.622355737686157) < 1e-6
        assert abs(float(srv.tuning.run_t90) - 0.04656740038574615) < 1e-6
        assert abs(float(srv.tuning.ground_stop_t90) - 0.16841168101466534) < 1e-6
        assert abs(float(srv.tuning.air_speed_mult) - (6.845157165527343 / 6.622355737686157)) < 1e-6
        assert bool(srv.tuning.surf_enabled) is True
        assert bool(srv.tuning.autojump_enabled) is True
        assert bool(srv.tuning.coyote_buffer_enabled) is True
        assert abs(float(srv.tuning.grace_period) - 0.2329816741943359) < 1e-6
    finally:
        srv.close()


def test_server_snapshot_uses_per_client_relevance_filter(monkeypatch) -> None:
    class _FakeSock:
        def __init__(self) -> None:
            self.sent: list[tuple[bytes, tuple[str, int]]] = []

        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

        def sendto(self, payload: bytes, addr: tuple[str, int]) -> None:
            self.sent.append((bytes(payload), (str(addr[0]), int(addr[1]))))

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=None)
    try:
        vis = GoldSrcBspVis(
            source_bsp="test.bsp",
            source_mtime_ns=0,
            root_node=0,
            planes=[(1.0, 0.0, 0.0, 0.0)],
            nodes=[(0, -1, -2)],
            leaves=[(0, 0, 0), (1, 0, 0)],
            leaf_faces=[],
            visdata=bytes([0x01, 0x02]),
            world_first_face=0,
            world_num_faces=0,
        )
        srv._relevance = GoldSrcPvsRelevance(vis=vis, map_scale=1.0, distance_fallback=0.0)

        def _mk_state(pid: int, x: float) -> object:
            return server_mod._ClientState(
                player_id=int(pid),
                token=f"token-{pid}",
                name=f"p{pid}",
                tcp_sock=_FakeSock(),
                udp_addr=("127.0.0.1", 7000 + int(pid)),
                ctrl=SimpleNamespace(pos=LVector3f(float(x), 0.0, 0.0), vel=LVector3f(0.0, 0.0, 0.0)),
                yaw=0.0,
                pitch=0.0,
                hp=100,
                respawn_seq=0,
                last_input=InputCommand(
                    seq=int(pid),
                    server_tick_hint=0,
                    look_dx=0,
                    look_dy=0,
                    look_scale=1,
                    move_forward=0,
                    move_right=0,
                    jump_pressed=False,
                    jump_held=False,
                    slide_pressed=False,
                    grapple_pressed=False,
                ),
                rewind_history=deque(maxlen=8),
            )

        st1 = _mk_state(pid=1, x=3.0)    # leaf 0
        st2 = _mk_state(pid=2, x=-9.0)   # leaf 1
        st3 = _mk_state(pid=3, x=7.0)    # leaf 0
        srv._clients_by_token = {
            "token-1": st1,
            "token-2": st2,
            "token-3": st3,
        }

        srv._broadcast_snapshot()

        packets_by_port: dict[int, dict] = {}
        for raw, addr in srv._udp_sock.sent:
            packets_by_port[int(addr[1])] = json.loads(raw.decode("utf-8"))

        ids_1 = [int(row["id"]) for row in packets_by_port[7001]["players"]]
        ids_2 = [int(row["id"]) for row in packets_by_port[7002]["players"]]
        ids_3 = [int(row["id"]) for row in packets_by_port[7003]["players"]]
        assert ids_1 == [1, 3]
        assert ids_2 == [2]
        assert ids_3 == [1, 3]
    finally:
        srv.close()


def test_decode_input_packet_reads_interact_pressed_flag() -> None:
    payload = json.dumps(
        {
            "t": "in",
            "token": "abc123",
            "seq": 7,
            "st": 100,
            "dx": 0,
            "dy": 0,
            "ls": 256,
            "mf": 0,
            "mr": 0,
            "jp": False,
            "jh": False,
            "sp": False,
            "gp": False,
            "ip": True,
        },
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    parsed = decode_input_packet(payload)
    assert parsed is not None
    _, cmd = parsed
    assert cmd.interact_pressed is True


def test_server_snapshot_includes_games_payload_and_event_ring(monkeypatch) -> None:
    class _FakeSock:
        def __init__(self) -> None:
            self.sent: list[tuple[bytes, tuple[str, int]]] = []

        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

        def sendto(self, payload: bytes, addr: tuple[str, int]) -> None:
            self.sent.append((bytes(payload), (str(addr[0]), int(addr[1]))))

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=None,
        initial_race_course=_sample_race_course(),
    )
    try:
        st = server_mod._ClientState(
            player_id=1,
            token="t1",
            name="p1",
            tcp_sock=_FakeSock(),
            udp_addr=("127.0.0.1", 7001),
            ctrl=SimpleNamespace(pos=LVector3f(0.0, 0.0, 1.0), vel=LVector3f(0.0, 0.0, 0.0)),
            yaw=0.0,
            pitch=0.0,
            hp=100,
            respawn_seq=0,
            last_input=InputCommand(
                seq=1,
                server_tick_hint=0,
                look_dx=0,
                look_dy=0,
                look_scale=1,
                move_forward=0,
                move_right=0,
                jump_pressed=False,
                jump_held=False,
                slide_pressed=False,
                grapple_pressed=False,
            ),
            rewind_history=deque(maxlen=8),
        )
        srv._clients_by_token = {"t1": st}
        srv._append_race_events([RaceEvent(kind="race_intro")])
        srv._broadcast_snapshot()

        assert srv._udp_sock.sent
        raw, _addr = srv._udp_sock.sent[-1]
        packet = json.loads(raw.decode("utf-8"))
        assert int(packet.get("games_v") or 0) >= 1
        games = packet.get("games")
        assert isinstance(games, dict)
        defs = games.get("definitions")
        assert isinstance(defs, list) and defs and defs[0].get("type") == "race"
        game_state = packet.get("game_state")
        assert isinstance(game_state, dict) and isinstance(game_state.get("race"), dict)
        evs = packet.get("game_events")
        assert isinstance(evs, list) and evs and evs[-1].get("kind") == "race_intro"
    finally:
        srv.close()


def test_server_interact_during_running_race_does_not_enroll_late_player(monkeypatch) -> None:
    class _FakeSock:
        def __init__(self) -> None:
            self.sent: list[tuple[bytes, tuple[str, int]]] = []

        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

        def sendto(self, payload: bytes, addr: tuple[str, int]) -> None:
            self.sent.append((bytes(payload), (str(addr[0]), int(addr[1]))))

    import ivan.net.server as server_mod

    class _FakeCtrl:
        def __init__(self, pos: LVector3f) -> None:
            self.pos = LVector3f(pos)
            self.vel = LVector3f(0.0, 0.0, 0.0)
            self.grounded = True

        def step_with_intent(self, *, dt, intent, yaw_deg, pitch_deg) -> None:
            _ = (dt, intent, yaw_deg, pitch_deg)

        def detach_grapple(self) -> None:
            return

        def respawn(self) -> None:
            self.pos = LVector3f(0.0, 0.0, 1.0)
            self.vel = LVector3f(0.0, 0.0, 0.0)

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=None, initial_race_course=_sample_race_course())
    try:
        st1 = server_mod._ClientState(
            player_id=1,
            token="t1",
            name="p1",
            tcp_sock=_FakeSock(),
            udp_addr=("127.0.0.1", 7001),
            ctrl=_FakeCtrl(LVector3f(0.0, 0.0, 1.0)),
            yaw=0.0,
            pitch=0.0,
            hp=100,
            respawn_seq=0,
            last_input=InputCommand(
                seq=1,
                server_tick_hint=0,
                look_dx=0,
                look_dy=0,
                look_scale=1,
                move_forward=0,
                move_right=0,
                jump_pressed=False,
                jump_held=False,
                slide_pressed=False,
                grapple_pressed=False,
            ),
            rewind_history=deque(maxlen=8),
        )
        st2 = server_mod._ClientState(
            player_id=2,
            token="t2",
            name="p2",
            tcp_sock=_FakeSock(),
            udp_addr=("127.0.0.1", 7002),
            ctrl=_FakeCtrl(LVector3f(0.0, 0.0, 1.0)),
            yaw=0.0,
            pitch=0.0,
            hp=100,
            respawn_seq=0,
            last_input=InputCommand(
                seq=1,
                server_tick_hint=0,
                look_dx=0,
                look_dy=0,
                look_scale=1,
                move_forward=0,
                move_right=0,
                jump_pressed=False,
                jump_held=False,
                slide_pressed=False,
                grapple_pressed=False,
                interact_pressed=True,
            ),
            rewind_history=deque(maxlen=8),
        )
        srv._clients_by_token = {"t1": st1, "t2": st2}

        # Start race with player 1 only.
        _ = srv._race_runtime.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.0)
        _ = srv._race_runtime.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.1)
        _ = srv._race_runtime.tick(now=1.1, player_positions={1: LVector3f(0.0, 0.0, 1.0)})
        _ = srv._race_runtime.tick(now=2.1, player_positions={1: LVector3f(0.0, 0.0, 1.0)})
        _ = srv._race_runtime.tick(now=3.1, player_positions={1: LVector3f(0.0, 0.0, 1.0)})
        _ = srv._race_runtime.tick(now=4.1, player_positions={1: LVector3f(0.0, 0.0, 1.0)})
        assert srv._race_runtime.status == "running"
        assert srv._race_runtime.participants == {1}

        # Player 2 pressing interact inside mission marker during running should be ignored.
        srv._simulate_tick()
        assert srv._race_runtime.status == "running"
        assert srv._race_runtime.participants == {1}
    finally:
        srv.close()


def test_server_process_tcp_interact_message_joins_race_lobby(monkeypatch) -> None:
    class _FakeSock:
        def __init__(self) -> None:
            self.sent: list[tuple[bytes, tuple[str, int]]] = []

        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

        def sendto(self, payload: bytes, addr: tuple[str, int]) -> None:
            self.sent.append((bytes(payload), (str(addr[0]), int(addr[1]))))

    class _FakeClientSock:
        def __init__(self, payload: bytes) -> None:
            self._payload = bytes(payload)
            self._sent_once = False

        def recv(self, _n: int) -> bytes:
            if not self._sent_once:
                self._sent_once = True
                return bytes(self._payload)
            raise BlockingIOError()

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=None, initial_race_course=_sample_race_course())
    try:
        client_sock = _FakeClientSock(b'{"t":"interact"}\n')
        st = server_mod._ClientState(
            player_id=1,
            token="t1",
            name="p1",
            tcp_sock=client_sock,
            udp_addr=("127.0.0.1", 7001),
            ctrl=SimpleNamespace(pos=LVector3f(0.0, 0.0, 1.0), vel=LVector3f(0.0, 0.0, 0.0)),
            yaw=0.0,
            pitch=0.0,
            hp=100,
            respawn_seq=0,
            last_input=InputCommand(
                seq=1,
                server_tick_hint=0,
                look_dx=0,
                look_dy=0,
                look_scale=1,
                move_forward=0,
                move_right=0,
                jump_pressed=False,
                jump_held=False,
                slide_pressed=False,
                grapple_pressed=False,
            ),
            rewind_history=deque(maxlen=8),
        )
        srv._clients_by_token = {"t1": st}
        srv._tcp_clients = {client_sock: b""}

        srv._process_tcp()

        assert srv._race_runtime.status == "lobby"
        assert srv._race_runtime.participants == {1}
        assert list(srv._race_event_ring)
        assert list(srv._race_event_ring)[-1]["kind"] == "race_lobby_join"
    finally:
        srv.close()


def test_server_loads_direct_map_spawn_and_kill_plane(monkeypatch, tmp_path) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    class _ConvertResult:
        def __init__(self) -> None:
            self.spawn_position = (-11.787, -108.5643, -0.030684304)
            self.spawn_yaw = 45.0
            self.bounds_min = (-20.0, -120.0, 0.05)
            self.triangles = [{"p": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]}]
            self.collision_triangles = [[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0]]

    import ivan.net.server as server_mod

    map_file = tmp_path / "test.map"
    map_file.write_text("// test map", encoding="utf-8")

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    monkeypatch.setattr(server_mod, "resolve_bundle_handle", lambda _m: None)
    monkeypatch.setattr("ivan.maps.map_converter.convert_map_file", lambda *_a, **_kw: _ConvertResult())

    srv = MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=str(map_file))
    try:
        assert abs(float(srv.spawn_point.x) - (-11.787)) < 1e-6
        assert abs(float(srv.spawn_point.y) - (-108.5643)) < 1e-6
        # +1.2 eye-safe offset is applied for .map parity with client scene load.
        assert abs(float(srv.spawn_point.z) - (1.169315696)) < 1e-6
        assert abs(float(srv.spawn_yaw) - 45.0) < 1e-6
        assert abs(float(srv.kill_z) - (-4.95)) < 1e-6
        assert len(srv.collision_triangles or []) == 1
    finally:
        srv.close()


def test_server_load_direct_map_raises_when_conversion_fails(monkeypatch, tmp_path) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    map_file = tmp_path / "broken.map"
    map_file.write_text("// invalid map", encoding="utf-8")

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    monkeypatch.setattr(server_mod, "resolve_bundle_handle", lambda _m: None)

    def _raise_convert(*_args, **_kwargs):
        raise ValueError("convert failed")

    monkeypatch.setattr("ivan.maps.map_converter.convert_map_file", _raise_convert)

    try:
        MultiplayerServer(host="127.0.0.1", tcp_port=0, udp_port=0, map_json=str(map_file))
        assert False, "Expected RuntimeError for broken .map conversion"
    except RuntimeError as exc:
        assert "failed to convert .map" in str(exc).lower()


def test_server_initial_spawn_override_is_host_only(monkeypatch) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=None,
        initial_spawn=(7.0, -3.5, 2.25),
        initial_spawn_yaw=270.0,
    )
    try:
        assert srv._host_spawn_override is not None
        sp_host = srv._spawn_point_for_player(player_id=1)
        assert abs(float(sp_host.x) - 7.0) < 1e-9
        assert abs(float(sp_host.y) - (-3.5)) < 1e-9
        assert abs(float(sp_host.z) - 2.25) < 1e-9
        # Base spawn remains authoritative for non-host players.
        assert abs(float(srv.spawn_point.x) - 0.0) < 1e-9
        assert abs(float(srv.spawn_point.y) - 35.0) < 1e-9
        assert abs(float(srv.spawn_point.z) - 1.9) < 1e-6
        assert abs(float(srv._spawn_yaw_for_player(player_id=1)) - 270.0) < 1e-9
        assert abs(float(srv.spawn_yaw) - 0.0) < 1e-9
    finally:
        srv.close()


def test_server_map_sessions_apply_initial_spawn_only_to_host_player(monkeypatch) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json="maps/test_map.json",
        initial_spawn=(10.0, 20.0, 3.0),
        initial_spawn_yaw=135.0,
    )
    try:
        base = LVector3f(srv.spawn_point)
        sp1 = srv._spawn_point_for_player(player_id=1)
        sp2 = srv._spawn_point_for_player(player_id=2)
        assert abs(float(sp1.x) - 10.0) < 1e-6
        assert abs(float(sp1.y) - 20.0) < 1e-6
        assert abs(float(sp1.z) - 3.0) < 1e-6
        # Non-host players should use map/server base spawn, not host runtime override.
        d2_from_base = math.hypot(float(sp2.x - base.x), float(sp2.y - base.y))
        d2_from_host_override = math.hypot(float(sp2.x - sp1.x), float(sp2.y - sp1.y))
        assert d2_from_base < d2_from_host_override
        assert abs(float(srv._spawn_yaw_for_player(player_id=1)) - 135.0) < 1e-6
        assert abs(float(srv._spawn_yaw_for_player(player_id=2)) - float(srv.spawn_yaw)) < 1e-6
    finally:
        srv.close()


def test_server_spawn_falls_back_when_host_override_is_out_of_bounds(monkeypatch, tmp_path) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    map_json = tmp_path / "map.json"
    map_json.write_text(
        json.dumps(
            {
                "triangles": [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]],
                "spawn": {"position": [1.0, 2.0, 0.0], "yaw": 45.0},
                "bounds": {"min": [-10.0, -10.0, -2.0], "max": [10.0, 10.0, 6.0]},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    monkeypatch.setattr(
        server_mod,
        "resolve_bundle_handle",
        lambda _m: SimpleNamespace(map_json=map_json),
    )

    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=str(map_json),
        initial_spawn=(999999.0, 999999.0, 999999.0),
        initial_spawn_yaw=90.0,
    )
    try:
        sp1 = srv._spawn_point_for_player(player_id=1)
        # Host override is rejected as out-of-bounds, so fallback uses authoritative map spawn.
        assert abs(float(sp1.x) - 1.0) < 1e-6
        assert abs(float(sp1.y) - 2.0) < 1e-6
        assert abs(float(sp1.z) - 1.2) < 1e-6
    finally:
        srv.close()


def test_server_assigns_small_spawn_offsets_for_additional_players(monkeypatch) -> None:
    class _FakeSock:
        sent: list[bytes]

        def __init__(self) -> None:
            self.sent = []

        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

        def sendall(self, payload: bytes) -> None:
            self.sent.append(bytes(payload))

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=None,
        initial_spawn=(10.0, 20.0, 3.0),
        initial_spawn_yaw=0.0,
    )
    try:
        sp1 = srv._spawn_point_for_player(player_id=1)
        sp2 = srv._spawn_point_for_player(player_id=2)
        sp7 = srv._spawn_point_for_player(player_id=7)
        assert abs(float(sp1.x) - 10.0) < 1e-6
        assert abs(float(sp1.y) - 20.0) < 1e-6
        assert abs(float(sp1.z) - 3.0) < 1e-6
        # Second player should be offset from base spawn to avoid overlap.
        assert abs(float(sp2.x) - float(sp1.x)) > 1e-6 or abs(float(sp2.y) - float(sp1.y)) > 1e-6
        # Ring grows after six offset slots.
        base = srv.spawn_point
        d2 = math.hypot(float(sp2.x - base.x), float(sp2.y - base.y))
        d7 = math.hypot(float(sp7.x - base.x), float(sp7.y - base.y))
        assert d7 > d2
    finally:
        srv.close()


def test_server_falls_back_to_base_spawn_when_offset_slot_has_no_ground(monkeypatch) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=None,
        initial_spawn=(10.0, 20.0, 3.0),
        initial_spawn_yaw=0.0,
    )
    try:
        base = LVector3f(srv.spawn_point)

        def _support_only_base(*, pos: LVector3f) -> bool:
            return abs(float(pos.x) - float(base.x)) < 1e-6 and abs(float(pos.y) - float(base.y)) < 1e-6

        monkeypatch.setattr(srv, "_spawn_has_ground_support", _support_only_base)
        sp2 = srv._spawn_point_for_player(player_id=2)
        assert abs(float(sp2.x) - float(base.x)) < 1e-6
        assert abs(float(sp2.y) - float(base.y)) < 1e-6
        assert abs(float(sp2.z) - float(base.z)) < 1e-6
    finally:
        srv.close()


def test_server_find_safe_spawn_near_uses_fallback_when_candidate_is_unsupported(monkeypatch) -> None:
    class _FakeSock:
        def setsockopt(self, *_args) -> None:
            return

        def bind(self, *_args) -> None:
            return

        def listen(self, *_args) -> None:
            return

        def setblocking(self, *_args) -> None:
            return

        def close(self) -> None:
            return

    import ivan.net.server as server_mod

    monkeypatch.setattr(server_mod.socket, "socket", lambda *_a, **_kw: _FakeSock())
    srv = MultiplayerServer(
        host="127.0.0.1",
        tcp_port=0,
        udp_port=0,
        map_json=None,
    )
    try:
        fallback = LVector3f(5.0, 6.0, 1.9)
        candidate = LVector3f(100.0, 200.0, -20.0)

        def _support_only_fallback(*, pos: LVector3f) -> bool:
            return abs(float(pos.x) - float(fallback.x)) < 1e-6 and abs(float(pos.y) - float(fallback.y)) < 1e-6

        monkeypatch.setattr(srv, "_spawn_has_ground_support", _support_only_fallback)
        safe = srv._find_safe_spawn_near(candidate=candidate, fallback=fallback, reason="test-unsupported")
        assert abs(float(safe.x) - float(fallback.x)) < 1e-6
        assert abs(float(safe.y) - float(fallback.y)) < 1e-6
        assert abs(float(safe.z) - float(fallback.z)) < 1e-6
    finally:
        srv.close()


def test_player_half_height_change_autoscales_eye_height_and_persists_both_fields() -> None:
    host = SimpleNamespace()
    host._net_connected = False
    host._net_can_configure = False
    host._net_authoritative_tuning = {}
    host.ui = _FakeUI()
    host.player = SimpleNamespace(apply_hull_settings=lambda: None)
    host.scene = None
    host._active_profile_name = "p1"
    host._profiles = {"p1": {}}
    host._suspend_tuning_persist = False
    persisted: list[str] = []
    host._persist_tuning_field = lambda field: persisted.append(str(field))
    host._send_tuning_to_server = lambda: None
    host.tuning = PhysicsTuning()
    host.tuning.player_half_height = 1.20

    profiles_mod.on_tuning_change(host, "player_half_height")

    expected_eye = 1.20 * (0.625 / 1.05)
    assert abs(float(host.tuning.player_eye_height) - float(expected_eye)) < 1e-6
    assert float(host._profiles["p1"]["player_half_height"]) == 1.20
    assert abs(float(host._profiles["p1"]["player_eye_height"]) - float(expected_eye)) < 1e-6
    assert "player_half_height" in persisted
    assert "player_eye_height" in persisted


def test_character_scale_lock_derives_radius_and_step_from_half_height() -> None:
    host = SimpleNamespace()
    host._net_connected = False
    host._net_can_configure = False
    host._net_authoritative_tuning = {}
    host.ui = _FakeUI()
    host.player = SimpleNamespace(apply_hull_settings=lambda: None)
    host.scene = None
    host._active_profile_name = "p1"
    host._profiles = {"p1": {}}
    host._suspend_tuning_persist = False
    persisted: list[str] = []
    host._persist_tuning_field = lambda field: persisted.append(str(field))
    host._send_tuning_to_server = lambda: None
    host.tuning = PhysicsTuning(character_scale_lock_enabled=True)
    host.tuning.player_half_height = 1.30

    profiles_mod.on_tuning_change(host, "player_half_height")

    assert abs(float(host.tuning.player_radius) - (1.30 * (0.42 / 1.05))) < 1e-6
    assert abs(float(host.tuning.step_height) - (1.30 * (0.55 / 1.05))) < 1e-6
    assert "player_half_height" in persisted
    assert "player_eye_height" in persisted
    assert "player_radius" in persisted
    assert "step_height" in persisted
