from __future__ import annotations

import errno
import math
import time
from dataclasses import dataclass, field

from panda3d.core import LVector3f

from ivan.physics.tuning import PhysicsTuning
from ivan.state import update_state


@dataclass
class _RemotePlayerVisual:
    player_id: int
    root_np: object
    head_np: object
    hp: int = 100
    name: str = "player"
    respawn_seq: int = 0
    sample_ticks: list[int] = field(default_factory=list)
    sample_pos: list[LVector3f] = field(default_factory=list)
    sample_vel: list[LVector3f] = field(default_factory=list)
    sample_yaw: list[float] = field(default_factory=list)


@dataclass
class _PredictedInput:
    seq: int
    cmd: object


@dataclass
class _PredictedState:
    seq: int
    pos: LVector3f
    vel: LVector3f
    yaw: float
    pitch: float


@dataclass
class _NetPerfStats:
    snapshot_count: int = 0
    snapshot_dt_sum: float = 0.0
    snapshot_dt_max: float = 0.0
    reconcile_count: int = 0
    reconcile_pos_err_sum: float = 0.0
    reconcile_pos_err_max: float = 0.0
    replay_input_sum: int = 0
    replay_input_max: int = 0
    replay_time_sum_ms: float = 0.0
    replay_time_max_ms: float = 0.0

    def reset(self) -> None:
        self.snapshot_count = 0
        self.snapshot_dt_sum = 0.0
        self.snapshot_dt_max = 0.0
        self.reconcile_count = 0
        self.reconcile_pos_err_sum = 0.0
        self.reconcile_pos_err_max = 0.0
        self.replay_input_sum = 0
        self.replay_input_max = 0
        self.replay_time_sum_ms = 0.0
        self.replay_time_max_ms = 0.0


def append_predicted_state(host, *, seq: int) -> None:
    if host.player is None:
        return
    host._net_predicted_states.append(
        _PredictedState(
            seq=int(seq),
            pos=LVector3f(host.player.pos),
            vel=LVector3f(host.player.vel),
            yaw=float(host._yaw),
            pitch=float(host._pitch),
        )
    )
    if len(host._net_predicted_states) > 256:
        host._net_predicted_states = host._net_predicted_states[-256:]


def state_for_ack(host, ack: int) -> _PredictedState | None:
    ack_i = int(ack)
    for st in reversed(host._net_predicted_states):
        if int(st.seq) == ack_i:
            return st
    return None


def reconcile_local_from_server(
    host,
    *,
    x: float,
    y: float,
    z: float,
    vx: float,
    vy: float,
    vz: float,
    yaw: float,
    pitch: float,
    ack: int,
) -> None:
    if host.player is None or host._playback_active:
        return
    ack_i = int(ack)
    ack_advanced = ack_i > int(host._net_last_acked_seq)
    ack_state = state_for_ack(host, ack_i) if ack_advanced else None
    if ack_advanced:
        host._net_last_acked_seq = ack_i
        host._net_pending_inputs = [p for p in host._net_pending_inputs if int(p.seq) > ack_i]
        host._net_predicted_states = [s for s in host._net_predicted_states if int(s.seq) > ack_i]

    server_pos = LVector3f(x, y, z)
    server_vel = LVector3f(vx, vy, vz)
    if ack_state is not None:
        ref_pos = LVector3f(ack_state.pos)
        ref_vel = LVector3f(ack_state.vel)
        ref_yaw = float(ack_state.yaw)
        ref_pitch = float(ack_state.pitch)
    else:
        ref_pos = LVector3f(host.player.pos)
        ref_vel = LVector3f(host.player.vel)
        ref_yaw = float(host._yaw)
        ref_pitch = float(host._pitch)

    pos_err = float((server_pos - ref_pos).length())
    vel_err = float((server_vel - ref_vel).length())
    yaw_err = abs(float(host._angle_delta_deg(ref_yaw, float(yaw))))
    pitch_err = abs(float(host._angle_delta_deg(ref_pitch, float(pitch))))
    needs_correction = pos_err > 0.02 or vel_err > 0.20 or yaw_err > 0.35 or pitch_err > 0.35
    if not needs_correction:
        return
    host._net_perf.reconcile_count += 1
    host._net_perf.reconcile_pos_err_sum += float(pos_err)
    host._net_perf.reconcile_pos_err_max = max(float(host._net_perf.reconcile_pos_err_max), float(pos_err))

    if ack_advanced:
        pre_reconcile_pos = LVector3f(host.player.pos)
        host.player.pos = LVector3f(server_pos)
        host.player.vel = LVector3f(server_vel)
        host._yaw = float(yaw)
        host._pitch = float(pitch)
        t_replay_start = time.monotonic()
        replay_count = 0
        for p in host._net_pending_inputs:
            host._simulate_input_tick(
                cmd=p.cmd,
                menu_open=False,
                network_send=False,
                record_demo=False,
                capture_snapshot=False,
            )
            # Use host method so tests/overrides can hook prediction history behavior.
            host._append_predicted_state(seq=int(p.seq))
            replay_count += 1
        host._push_sim_snapshot()
        replay_ms = max(0.0, (time.monotonic() - t_replay_start) * 1000.0)
        host._net_perf.replay_input_sum += int(replay_count)
        host._net_perf.replay_input_max = max(int(host._net_perf.replay_input_max), int(replay_count))
        host._net_perf.replay_time_sum_ms += float(replay_ms)
        host._net_perf.replay_time_max_ms = max(float(host._net_perf.replay_time_max_ms), float(replay_ms))
        post_reconcile_pos = LVector3f(host.player.pos)
        host._net_reconcile_pos_offset += pre_reconcile_pos - post_reconcile_pos
        return

    if not host._net_pending_inputs:
        host.player.pos = LVector3f(server_pos)
        host.player.vel = LVector3f(server_vel)
        host._yaw = float(yaw)
        host._pitch = float(pitch)


def disconnect_multiplayer(host) -> None:
    if host._net_client is not None:
        try:
            host._net_client.close()
        except Exception:
            pass
    host._net_client = None
    host._net_connected = False
    host._net_can_configure = False
    host._net_player_id = 0
    host._net_seq_counter = 0
    host._net_last_server_tick = 0
    host._net_last_acked_seq = 0
    host._net_local_respawn_seq = 0
    host._net_last_snapshot_local_time = 0.0
    host._net_pending_inputs.clear()
    host._net_predicted_states.clear()
    host._net_authoritative_tuning = {}
    host._net_authoritative_tuning_version = 0
    host._net_snapshot_intervals.clear()
    host._net_server_tick_offset_ready = False
    host._net_server_tick_offset_ticks = 0.0
    host._net_reconcile_pos_offset = LVector3f(0, 0, 0)
    host._net_reconcile_yaw_offset = 0.0
    host._net_reconcile_pitch_offset = 0.0
    host._camera_observer.reset()
    host._camera_tilt_observer.reset()
    if hasattr(host, "_camera_height_observer"):
        host._camera_height_observer.reset()
    if hasattr(host, "_camera_feedback_observer"):
        host._camera_feedback_observer.reset()
    host._net_cfg_apply_pending_version = 0
    host._net_cfg_apply_sent_at = 0.0
    host._net_perf.reset()
    host._net_perf_last_publish = 0.0
    host._net_perf_text = ""
    clear_remote_players(host)
    host.pause_ui.set_multiplayer_status("Not connected.")


def on_toggle_open_network(host, enabled: bool) -> None:
    host._open_to_network = bool(enabled)
    host.pause_ui.set_open_to_network(host._open_to_network)
    if host._open_to_network:
        host._runtime_connect_host = None
        host.pause_ui.set_keybind_status("Starting local host...")
        host.pause_ui.set_connect_target(host="127.0.0.1", port=int(host._runtime_connect_port))
        host._connect_multiplayer_if_requested()
        if host._net_connected:
            host.pause_ui.set_keybind_status("Open to network enabled.")
        else:
            host.pause_ui.set_keybind_status("Failed to start local host.")
    else:
        disconnect_multiplayer(host)
        host._stop_embedded_server()
        host.pause_ui.set_keybind_status("Open to network disabled (local offline mode).")


def on_connect_server_from_menu(host, host_text: str, port_text: str) -> None:
    host_clean = str(host_text or "").strip()
    if not host_clean:
        host.pause_ui.set_multiplayer_status("Host/IP is required.")
        return
    try:
        port = int(str(port_text).strip())
    except Exception:
        host.pause_ui.set_multiplayer_status("Port must be a number.")
        return
    if port <= 0 or port > 65535:
        host.pause_ui.set_multiplayer_status("Port must be between 1 and 65535.")
        return

    update_state(last_net_host=host_clean, last_net_port=int(port))
    host._runtime_connect_host = host_clean
    host._runtime_connect_port = int(port)
    host.pause_ui.set_connect_target(host=host._runtime_connect_host, port=host._runtime_connect_port)
    if host._open_to_network:
        host._open_to_network = False
        host.pause_ui.set_open_to_network(False)
        host._stop_embedded_server()
    host._connect_multiplayer_if_requested()


def on_disconnect_server_from_menu(host) -> None:
    disconnect_multiplayer(host)
    if host._open_to_network:
        host._open_to_network = False
        host.pause_ui.set_open_to_network(False)
        host._stop_embedded_server()


def clear_remote_players(host) -> None:
    for rp in host._remote_players.values():
        try:
            rp.root_np.removeNode()
        except Exception:
            pass
    host._remote_players.clear()
    host._net_pending_inputs.clear()
    host._net_predicted_states.clear()


def ensure_remote_player_visual(host, *, player_id: int, name: str) -> _RemotePlayerVisual:
    rp = host._remote_players.get(int(player_id))
    if rp is not None:
        return rp
    # Simple two-box avatar: body + head.
    body = host.loader.loadModel("models/box")
    body.reparentTo(host.world_root)
    body.setScale(0.28, 0.28, 0.92)
    body.setColor(0.22, 0.72, 0.95, 1.0)
    head = host.loader.loadModel("models/box")
    head.reparentTo(body)
    head.setPos(0.0, 0.0, 1.20)
    head.setScale(0.18, 0.18, 0.18)
    head.setColor(0.95, 0.85, 0.70, 1.0)
    rp = _RemotePlayerVisual(player_id=int(player_id), root_np=body, head_np=head, name=str(name or "player"))
    host._remote_players[int(player_id)] = rp
    return rp


def poll_network_snapshot(host) -> None:
    if not host._net_connected or host._net_client is None:
        return
    snap = host._net_client.poll()
    if not isinstance(snap, dict):
        return
    tick = int(snap.get("tick") or 0)
    now_mono = time.monotonic()
    host._net_last_server_tick = max(host._net_last_server_tick, tick)
    if host._net_last_snapshot_local_time > 0.0:
        dt_snap = max(0.0, float(now_mono - float(host._net_last_snapshot_local_time)))
        if dt_snap > 0.0:
            host._net_perf.snapshot_count += 1
            host._net_perf.snapshot_dt_sum += float(dt_snap)
            host._net_perf.snapshot_dt_max = max(float(host._net_perf.snapshot_dt_max), float(dt_snap))
            host._net_snapshot_intervals.append(dt_snap)
            if len(host._net_snapshot_intervals) > 64:
                host._net_snapshot_intervals = host._net_snapshot_intervals[-64:]
            mean = sum(host._net_snapshot_intervals) / float(len(host._net_snapshot_intervals))
            var = sum((d - mean) * (d - mean) for d in host._net_snapshot_intervals) / float(
                len(host._net_snapshot_intervals)
            )
            std = math.sqrt(max(0.0, var))
            delay_sec = mean + std * 2.0 + 0.005
            host._net_interp_delay_ticks = max(2.0, min(12.0, delay_sec * float(host._sim_tick_rate_hz)))
    host._net_last_snapshot_local_time = float(now_mono)
    if (
        int(host._net_cfg_apply_pending_version) > 0
        and host._net_cfg_apply_sent_at > 0.0
        and (float(now_mono) - float(host._net_cfg_apply_sent_at)) >= 0.8
    ):
        host.ui.set_status(
            "Waiting for server config acknowledgement..."
            f" (cfg_v target={int(host._net_cfg_apply_pending_version)})"
        )
    tick_offset_sample = float(tick) - float(now_mono) * float(host._sim_tick_rate_hz)
    if not host._net_server_tick_offset_ready:
        host._net_server_tick_offset_ready = True
        host._net_server_tick_offset_ticks = float(tick_offset_sample)
    else:
        k = max(0.01, min(1.0, float(host._net_server_tick_offset_smooth)))
        host._net_server_tick_offset_ticks += (float(tick_offset_sample) - float(host._net_server_tick_offset_ticks)) * k
    cfg_v = int(snap.get("cfg_v") or 0)
    cfg_tuning = snap.get("tuning")
    if isinstance(cfg_tuning, dict) and int(cfg_v) > int(host._net_authoritative_tuning_version):
        normalized: dict[str, float | bool] = {}
        for field in PhysicsTuning.__annotations__.keys():
            value = cfg_tuning.get(field)
            if isinstance(value, bool):
                normalized[field] = bool(value)
            elif isinstance(value, (int, float)):
                normalized[field] = float(value)
        if normalized:
            host._apply_authoritative_tuning(tuning=normalized, version=int(cfg_v))
    players = snap.get("players")
    if not isinstance(players, list):
        return

    seen: set[int] = set()
    for row in players:
        if not isinstance(row, dict):
            continue
        pid = int(row.get("id") or 0)
        if pid <= 0:
            continue
        seen.add(pid)
        x = float(row.get("x") or 0.0)
        y = float(row.get("y") or 0.0)
        z = float(row.get("z") or 0.0)
        yaw = float(row.get("yaw") or 0.0)
        pitch = float(row.get("pitch") or 0.0)
        vx = float(row.get("vx") or 0.0)
        vy = float(row.get("vy") or 0.0)
        vz = float(row.get("vz") or 0.0)
        ack = int(row.get("ack") or 0)
        hp = int(row.get("hp") or 0)
        rs = int(row.get("rs") or 0)
        if pid == host._net_player_id:
            host._local_hp = max(0, hp)
            if host.player is not None and not host._playback_active:
                if int(rs) > int(host._net_local_respawn_seq):
                    host._net_local_respawn_seq = int(rs)
                    host._net_pending_inputs.clear()
                    host._net_predicted_states.clear()
                    host._net_last_acked_seq = max(int(host._net_last_acked_seq), int(ack))
                    host.player.pos = LVector3f(x, y, z)
                    host.player.vel = LVector3f(vx, vy, vz)
                    host._yaw = float(yaw)
                    host._pitch = float(pitch)
                    host._net_reconcile_pos_offset = LVector3f(0, 0, 0)
                    host._net_reconcile_yaw_offset = 0.0
                    host._net_reconcile_pitch_offset = 0.0
                    host._camera_observer.reset()
                    host._camera_tilt_observer.reset()
                    if hasattr(host, "_camera_height_observer"):
                        host._camera_height_observer.reset()
                    if hasattr(host, "_camera_feedback_observer"):
                        host._camera_feedback_observer.reset()
                    if not host._playback_active:
                        host._start_new_demo_recording()
                    continue
                host._reconcile_local_from_server(
                    x=x,
                    y=y,
                    z=z,
                    vx=vx,
                    vy=vy,
                    vz=vz,
                    yaw=yaw,
                    pitch=pitch,
                    ack=ack,
                )
            continue
        rp = ensure_remote_player_visual(host, player_id=pid, name=str(row.get("n") or "player"))
        if int(rs) > int(rp.respawn_seq):
            rp.respawn_seq = int(rs)
            rp.sample_ticks.clear()
            rp.sample_pos.clear()
            rp.sample_vel.clear()
            rp.sample_yaw.clear()
        rp.sample_ticks.append(int(tick))
        rp.sample_pos.append(LVector3f(x, y, z))
        rp.sample_vel.append(LVector3f(vx, vy, vz))
        rp.sample_yaw.append(float(yaw))
        if len(rp.sample_ticks) > 48:
            rp.sample_ticks = rp.sample_ticks[-48:]
            rp.sample_pos = rp.sample_pos[-48:]
            rp.sample_vel = rp.sample_vel[-48:]
            rp.sample_yaw = rp.sample_yaw[-48:]
        rp.hp = max(0, hp)

    stale = [pid for pid in host._remote_players.keys() if pid not in seen]
    for pid in stale:
        rp = host._remote_players.pop(pid)
        try:
            rp.root_np.removeNode()
        except Exception:
            pass


def render_remote_players(host, *, alpha: float) -> None:
    if host._net_server_tick_offset_ready:
        now_mono = float(time.monotonic())
        est_server_tick = float(now_mono) * float(host._sim_tick_rate_hz) + float(host._net_server_tick_offset_ticks)
        est_server_tick = max(float(host._net_last_server_tick), est_server_tick)
    elif host._net_last_snapshot_local_time > 0.0:
        est_server_tick = float(host._net_last_server_tick) + (
            float(time.monotonic()) - float(host._net_last_snapshot_local_time)
        ) * float(host._sim_tick_rate_hz)
    else:
        est_server_tick = float(host._net_last_server_tick)
    target_tick = est_server_tick - float(host._net_interp_delay_ticks)
    for rp in host._remote_players.values():
        if not rp.sample_ticks:
            continue
        i1 = 0
        while i1 < len(rp.sample_ticks) and float(rp.sample_ticks[i1]) < float(target_tick):
            i1 += 1
        if i1 <= 0:
            p = rp.sample_pos[0]
            y = rp.sample_yaw[0]
        elif i1 >= len(rp.sample_ticks):
            p = rp.sample_pos[-1]
            y = rp.sample_yaw[-1]
            # Short dead reckoning to reduce "stuck remote players" when snapshots stall.
            if rp.sample_vel:
                dt_ticks = float(target_tick) - float(rp.sample_ticks[-1])
                if dt_ticks > 0.0:
                    dt_ticks = min(float(dt_ticks), float(host._net_remote_extrapolate_max_ticks))
                    dt_s = dt_ticks / float(host._sim_tick_rate_hz)
                    v = rp.sample_vel[-1]
                    p = LVector3f(
                        float(p.x) + float(v.x) * float(dt_s),
                        float(p.y) + float(v.y) * float(dt_s),
                        float(p.z) + float(v.z) * float(dt_s),
                    )
        else:
            t0 = float(rp.sample_ticks[i1 - 1])
            t1 = float(rp.sample_ticks[i1])
            denom = max(1e-6, t1 - t0)
            a = max(0.0, min(1.0, (float(target_tick) - t0) / denom))
            p = host._lerp_vec(rp.sample_pos[i1 - 1], rp.sample_pos[i1], a)
            y = host._lerp_angle_deg(rp.sample_yaw[i1 - 1], rp.sample_yaw[i1], a)
        try:
            rp.root_np.setPos(p)
            rp.root_np.setHpr(y, 0, 0)
        except Exception:
            pass


def start_embedded_server(host) -> bool:
    if host._embedded_server is not None:
        return True
    bind_host = "0.0.0.0" if host._open_to_network else "127.0.0.1"
    try:
        host._embedded_server = host.EmbeddedHostServer(  # type: ignore[attr-defined]
            host=bind_host,
            tcp_port=int(host._runtime_connect_port),
            udp_port=int(host._runtime_connect_port) + 1,
            map_json=host._current_map_json,
            initial_tuning=host._current_tuning_snapshot(),
        )
        host._embedded_server.start()
    except OSError as e:
        host._embedded_server = None
        if e.errno in (errno.EADDRINUSE, 48):
            return False
        raise
    time.sleep(0.12)
    return True


__all__ = [
    "_NetPerfStats",
    "_PredictedInput",
    "_PredictedState",
    "_RemotePlayerVisual",
    "append_predicted_state",
    "clear_remote_players",
    "disconnect_multiplayer",
    "ensure_remote_player_visual",
    "on_connect_server_from_menu",
    "on_disconnect_server_from_menu",
    "on_toggle_open_network",
    "poll_network_snapshot",
    "reconcile_local_from_server",
    "render_remote_players",
    "state_for_ack",
]
