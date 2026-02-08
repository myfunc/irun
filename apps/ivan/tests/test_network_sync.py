from __future__ import annotations

from types import SimpleNamespace

from ivan.game import RunnerDemo
from ivan.physics.tuning import PhysicsTuning
from ivan.net.server import MultiplayerServer
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

    def send_respawn(self) -> None:
        self.respawn_calls += 1


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
    demo._current_tuning_snapshot = lambda: {"gravity": 33.0, "surf_enabled": True}
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
    assert captured["initial_tuning"] == {"gravity": 33.0, "surf_enabled": True}


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
    demo._current_tuning_snapshot = lambda: {
        "gravity": 39.6196435546875,
        "surf_enabled": True,
        "jump_accel": 31.738659286499026,
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
        "gravity": 39.6196435546875,
        "surf_enabled": True,
        "jump_accel": 31.738659286499026,
        "grapple_pull_strength": 30.263092041015625,
    }


def test_current_tuning_snapshot_reflects_active_client_values() -> None:
    demo = RunnerDemo.__new__(RunnerDemo)
    demo.tuning = PhysicsTuning()
    demo.tuning.gravity = 41.0
    demo.tuning.surf_enabled = True
    demo.tuning.max_air_speed = 9.25

    snap = RunnerDemo._current_tuning_snapshot(demo)

    assert float(snap["gravity"]) == 41.0
    assert bool(snap["surf_enabled"]) is True
    assert float(snap["max_air_speed"]) == 9.25


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
    demo._profiles = {"p1": {"gravity": 30.0}}
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
    demo._profiles = {"p1": {"gravity": 30.0}}
    demo._active_profile_name = "surf_bhop_c2"
    demo._profile_names = lambda: ["p1", "surf_bhop_c2"]
    demo._net_connected = True
    demo._net_can_configure = False
    demo._net_authoritative_tuning = {"gravity": 39.6}
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
        assert abs(float(srv.tuning.gravity) - 39.6196435546875) < 1e-6
        assert abs(float(srv.tuning.jump_height) - 1.0108081703186036) < 1e-6
        assert abs(float(srv.tuning.max_ground_speed) - 6.622355737686157) < 1e-6
        assert abs(float(srv.tuning.max_air_speed) - 6.845157165527343) < 1e-6
        assert bool(srv.tuning.surf_enabled) is True
        assert bool(srv.tuning.autojump_enabled) is True
        assert bool(srv.tuning.enable_jump_buffer) is True
    finally:
        srv.close()
