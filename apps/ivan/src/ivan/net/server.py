from __future__ import annotations

import json
import math
import os
import secrets
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from panda3d.core import LVector3f, NodePath, PandaNode

from ivan.common.aabb import AABB
from ivan.console.control_server import ConsoleControlServer
from ivan.console.server_bindings import build_server_console
from ivan.console.line_bus import ThreadSafeLineBus
from ivan.maps.bundle_io import resolve_bundle_handle
from ivan.net.relevance import GoldSrcPvsRelevance, build_goldsrc_pvs_relevance_from_map
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.motion.intent import MotionIntent
from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.net.protocol import (
    InputCommand,
    PROTOCOL_VERSION,
    decode_input_packet,
    decode_json_line,
    encode_json,
    encode_snapshot_packet,
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class _ClientState:
    player_id: int
    token: str
    name: str
    tcp_sock: socket.socket
    udp_addr: tuple[str, int] | None
    ctrl: PlayerController
    yaw: float
    pitch: float
    hp: int
    respawn_seq: int
    last_input: InputCommand
    rewind_history: deque[tuple[int, LVector3f]]


class MultiplayerServer:
    def __init__(
        self,
        *,
        host: str,
        tcp_port: int,
        udp_port: int,
        map_json: str | None,
        initial_tuning: dict[str, float | bool] | None = None,
        initial_spawn: tuple[float, float, float] | None = None,
        initial_spawn_yaw: float | None = None,
    ) -> None:
        self.host = str(host)
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.map_json = str(map_json) if map_json else None

        self.tick_rate_hz = 60
        self.fixed_dt = 1.0 / float(self.tick_rate_hz)
        self.snapshot_rate_hz = 30
        self.snapshot_dt = 1.0 / float(self.snapshot_rate_hz)

        self.tuning = PhysicsTuning()
        self.tuning.noclip_enabled = False
        self._apply_tuning_snapshot(initial_tuning if isinstance(initial_tuning, dict) else self._default_server_tuning())

        self.spawn_point = LVector3f(0, 35, 1.9)
        self.spawn_yaw = 0.0
        self.kill_z = -18.0
        self._relevance: GoldSrcPvsRelevance | None = None

        self.aabbs: list[AABB] = []
        self.collision_triangles: list[list[float]] | None = None
        self._load_map_bundle()
        if isinstance(initial_spawn, tuple) and len(initial_spawn) == 3:
            try:
                self.spawn_point = LVector3f(
                    float(initial_spawn[0]),
                    float(initial_spawn[1]),
                    float(initial_spawn[2]),
                )
            except Exception:
                pass
        if isinstance(initial_spawn_yaw, (int, float)):
            self.spawn_yaw = float(initial_spawn_yaw)

        root_np = NodePath(PandaNode("server-root"))
        self.collision = CollisionWorld(
            aabbs=self.aabbs,
            triangles=self.collision_triangles,
            triangle_collision_mode=bool(self.collision_triangles),
            player_radius=float(self.tuning.player_radius),
            player_half_height=float(self.tuning.player_half_height),
            render=root_np,
        )

        self._next_player_id = 1
        self._clients_by_token: dict[str, _ClientState] = {}
        self._tcp_clients: dict[socket.socket, bytes] = {}
        self._tick = 0
        self._config_owner_token: str | None = None
        self._tuning_version: int = 1

        self._tcp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp_listener.bind((self.host, self.tcp_port))
        self._tcp_listener.listen(32)
        self._tcp_listener.setblocking(False)

        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._udp_sock.bind((self.host, self.udp_port))
        self._udp_sock.setblocking(False)

        # Minimal server console (no in-server UI). Primarily driven via MCP/control socket.
        self.console = build_server_console(self)
        self._console_bus = ThreadSafeLineBus(max_lines=1000)
        self.console.register_listener(self._console_bus.listener)
        self._console_control_port = int(os.environ.get("IRUN_IVAN_SERVER_CONSOLE_PORT", "39001"))
        self.console_control = ConsoleControlServer(console=self.console, host="127.0.0.1", port=int(self._console_control_port))
        try:
            self.console_control.start()
        except Exception:
            self.console_control = None
        self._closed = False

    @staticmethod
    def _normalize_tuning_snapshot(values: dict[str, float | bool] | None) -> dict[str, float | bool]:
        if not isinstance(values, dict):
            return {}
        fields = set(PhysicsTuning.__annotations__.keys())
        out: dict[str, float | bool] = {}
        for k, v in values.items():
            if k not in fields:
                continue
            if isinstance(v, bool):
                out[k] = bool(v)
            elif isinstance(v, (int, float)):
                out[k] = float(v)
        return out

    @staticmethod
    def _default_server_tuning() -> dict[str, float | bool]:
        # Match IVAN runtime default profile (surf_bhop_c2) when no explicit host tuning is provided.
        base = PhysicsTuning()
        out: dict[str, float | bool] = {}
        for field in PhysicsTuning.__annotations__.keys():
            value = getattr(base, field)
            out[field] = bool(value) if isinstance(value, bool) else float(value)
        out.update(
            {
                "surf_enabled": True,
                "autojump_enabled": True,
                "coyote_buffer_enabled": True,
                "jump_height": 1.0108081703186036,
                "jump_apex_time": 0.22585349306495618,
                "max_ground_speed": 6.622355737686157,
                "run_t90": 0.04656740038574615,
                "ground_stop_t90": 0.16841168101466534,
                "air_speed_mult": 6.845157165527343 / 6.622355737686157,
                "air_gain_t90": 0.9 / 31.738659286499026,
                "wallrun_sink_t90": 0.22,
                "mouse_sensitivity": 0.09978364143371583,
                "grace_period": 0.2329816741943359,
                "wall_jump_cooldown": 0.9972748947143555,
                "surf_accel": 23.521632385253906,
                "surf_gravity_scale": 0.33837084770202636,
                "surf_min_normal_z": 0.05,
                "surf_max_normal_z": 0.72,
                "grapple_enabled": True,
                "grapple_attach_shorten_speed": 7.307412719726562,
                "grapple_attach_shorten_time": 0.35835513305664063,
                "grapple_pull_strength": 30.263092041015625,
                "grapple_min_length": 0.7406494271755218,
                "grapple_rope_half_width": 0.015153287963867187,
            }
        )
        return out

    def _tuning_snapshot(self) -> dict[str, float | bool]:
        out: dict[str, float | bool] = {}
        for field in PhysicsTuning.__annotations__.keys():
            value = getattr(self.tuning, field)
            out[field] = bool(value) if isinstance(value, bool) else float(value)
        return out

    def _apply_tuning_snapshot(self, values: dict[str, float | bool] | None) -> None:
        snap = self._normalize_tuning_snapshot(values)
        if not snap:
            return
        for field, value in snap.items():
            setattr(self.tuning, field, value)
        for st in getattr(self, "_clients_by_token", {}).values():
            try:
                st.ctrl.apply_hull_settings()
            except Exception:
                pass

    def _client_state_by_tcp(self, cs: socket.socket) -> _ClientState | None:
        for st in self._clients_by_token.values():
            if st.tcp_sock is cs:
                return st
        return None

    @staticmethod
    def _safe_close_socket(sock: socket.socket | None) -> None:
        if sock is None:
            return
        try:
            sock.close()
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if getattr(self, "console_control", None) is not None:
            try:
                self.console_control.close()
            except Exception:
                pass
        for cs in list(self._tcp_clients.keys()):
            self._safe_close_socket(cs)
        self._tcp_clients.clear()
        self._clients_by_token.clear()
        self._safe_close_socket(self._tcp_listener)
        self._safe_close_socket(self._udp_sock)

    def _load_map_bundle(self) -> None:
        self._relevance = None
        if not self.map_json:
            return
        handle = resolve_bundle_handle(self.map_json)
        if handle is None:
            self._load_map_file_for_server()
            return
        # Advertise the concrete map.json path so clients can load the same map on connect.
        self.map_json = str(handle.map_json)
        payload_path = handle.map_json
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except Exception:
            return
        try:
            self._relevance = build_goldsrc_pvs_relevance_from_map(
                map_json=payload_path,
                payload=payload,
            )
        except Exception:
            self._relevance = None
        spawn = payload.get("spawn")
        if isinstance(spawn, dict):
            pos = spawn.get("position")
            yaw = spawn.get("yaw")
            if isinstance(pos, list) and len(pos) == 3:
                try:
                    self.spawn_point = LVector3f(float(pos[0]), float(pos[1]), float(pos[2]) + 1.2)
                except Exception:
                    pass
            if isinstance(yaw, (int, float)):
                self.spawn_yaw = float(yaw)
        bounds = payload.get("bounds")
        if isinstance(bounds, dict):
            bmin = bounds.get("min")
            if isinstance(bmin, list) and len(bmin) == 3:
                try:
                    self.kill_z = float(bmin[2]) - 5.0
                except Exception:
                    pass

        tris = payload.get("triangles")
        if not isinstance(tris, list) or not tris:
            return

        pos_tris: list[list[float]] = []
        first = tris[0]
        if isinstance(first, dict):
            for t in tris:
                if not isinstance(t, dict):
                    continue
                p = t.get("p")
                if isinstance(p, list) and len(p) == 9:
                    try:
                        pos_tris.append([float(x) for x in p])
                    except Exception:
                        pass
            coll = payload.get("collision_triangles")
            if isinstance(coll, list) and coll and isinstance(coll[0], list):
                ctri: list[list[float]] = []
                for t in coll:
                    if isinstance(t, list) and len(t) == 9:
                        try:
                            ctri.append([float(x) for x in t])
                        except Exception:
                            pass
                self.collision_triangles = ctri if ctri else pos_tris
            else:
                self.collision_triangles = pos_tris
            return

        if isinstance(first, list):
            for t in tris:
                if isinstance(t, list) and len(t) == 9:
                    try:
                        pos_tris.append([float(x) for x in t])
                    except Exception:
                        pass
            self.collision_triangles = pos_tris

    def _load_map_file_for_server(self) -> None:
        """
        Load direct TrenchBroom `.map` files for authoritative server simulation.

        Without this path, host-on-.map mode runs the server with an empty world, causing
        respawn loops and apparent teleports into void positions.
        """

        if not self.map_json:
            return
        map_file = Path(str(self.map_json)).expanduser().resolve()
        if not map_file.exists() or not map_file.is_file() or map_file.suffix.lower() != ".map":
            return
        self.map_json = str(map_file)
        try:
            from ivan.maps.map_converter import convert_map_file
            from ivan.maps.bundle_io import _default_materials_dirs, _default_wad_search_dirs
            from ivan.state import state_dir

            tex_cache = state_dir() / "cache" / "server_map_textures" / map_file.stem
            tex_cache.mkdir(parents=True, exist_ok=True)
            result = convert_map_file(
                map_file,
                scale=0.03,
                wad_search_dirs=_default_wad_search_dirs(map_file),
                materials_dirs=_default_materials_dirs(map_file),
                texture_cache_dir=tex_cache,
            )
        except Exception as e:
            raise RuntimeError(f"Server failed to convert .map file: {map_file}") from e

        if not result.triangles:
            raise RuntimeError(f"Server map conversion produced no render triangles: {map_file}")

        if result.spawn_position is not None and len(result.spawn_position) == 3:
            try:
                self.spawn_point = LVector3f(
                    float(result.spawn_position[0]),
                    float(result.spawn_position[1]),
                    float(result.spawn_position[2]),
                )
                self.spawn_point.setZ(self.spawn_point.getZ() + 1.2)
            except Exception:
                pass
        self.spawn_yaw = float(result.spawn_yaw)
        try:
            self.kill_z = float(result.bounds_min[2]) - 5.0
        except Exception:
            pass

        pos_tris: list[list[float]] = []
        for t in result.triangles:
            if not isinstance(t, dict):
                continue
            p = t.get("p")
            if isinstance(p, list) and len(p) == 9:
                try:
                    pos_tris.append([float(x) for x in p])
                except Exception:
                    pass
        if not pos_tris:
            raise RuntimeError(f"Server map conversion produced no position triangles: {map_file}")
        if result.collision_triangles:
            coll: list[list[float]] = []
            for t in result.collision_triangles:
                if isinstance(t, list) and len(t) == 9:
                    try:
                        coll.append([float(x) for x in t])
                    except Exception:
                        pass
            self.collision_triangles = coll if coll else pos_tris
        else:
            self.collision_triangles = pos_tris
        if not self.collision_triangles:
            raise RuntimeError(f"Server map conversion produced no collision triangles: {map_file}")

    def _spawn_point_for_player(self, *, player_id: int) -> LVector3f:
        idx = max(0, int(player_id) - 1)
        if idx == 0:
            return LVector3f(self.spawn_point)
        # Keep host at base spawn; spread other players in small rings to avoid overlap.
        ring = 1 + ((idx - 1) // 6)
        slot = (idx - 1) % 6
        angle = (math.tau * (float(slot) / 6.0)) + (float(ring) * 0.37)
        base_radius = max(float(self.tuning.player_radius) * 3.0, 0.9)
        r = base_radius * float(ring)
        return LVector3f(
            float(self.spawn_point.x) + math.cos(angle) * r,
            float(self.spawn_point.y) + math.sin(angle) * r,
            float(self.spawn_point.z),
        )

    def _make_controller(self, *, spawn_point: LVector3f | None = None) -> PlayerController:
        return PlayerController(
            tuning=self.tuning,
            spawn_point=(LVector3f(spawn_point) if spawn_point is not None else self.spawn_point),
            aabbs=self.aabbs,
            collision=self.collision,
        )

    def _accept_tcp(self) -> None:
        while True:
            try:
                cs, _addr = self._tcp_listener.accept()
            except BlockingIOError:
                return
            cs.setblocking(False)
            self._tcp_clients[cs] = b""

    def _process_tcp(self) -> None:
        dead: list[socket.socket] = []
        for cs, buf in list(self._tcp_clients.items()):
            try:
                data = cs.recv(8192)
            except BlockingIOError:
                continue
            except Exception:
                dead.append(cs)
                continue
            if not data:
                dead.append(cs)
                continue
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                obj = decode_json_line(line)
                if not obj:
                    continue
                t = str(obj.get("t") or "")
                if t == "cfg":
                    st = self._client_state_by_tcp(cs)
                    if st is None:
                        continue
                    if self._config_owner_token is None or st.token != self._config_owner_token:
                        continue
                    tuning_val = obj.get("tuning")
                    if isinstance(tuning_val, dict):
                        self._apply_tuning_snapshot(tuning_val)
                        self._tuning_version += 1
                    continue
                if t == "respawn":
                    st = self._client_state_by_tcp(cs)
                    if st is None:
                        continue
                    st.ctrl.respawn()
                    st.yaw = float(self.spawn_yaw)
                    st.pitch = 0.0
                    st.hp = 100
                    st.respawn_seq = int(st.respawn_seq) + 1
                    continue
                if t != "hello":
                    continue
                name = str(obj.get("name") or "player")[:24]
                pid = self._next_player_id
                self._next_player_id += 1
                token = secrets.token_hex(12)
                player_spawn = self._spawn_point_for_player(player_id=int(pid))
                ctrl = self._make_controller(spawn_point=player_spawn)
                st = _ClientState(
                    player_id=pid,
                    token=token,
                    name=name,
                    tcp_sock=cs,
                    udp_addr=None,
                    ctrl=ctrl,
                    yaw=float(self.spawn_yaw),
                    pitch=0.0,
                    hp=100,
                    respawn_seq=0,
                    last_input=InputCommand(
                        seq=0,
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
                    rewind_history=deque(maxlen=240),
                )
                self._clients_by_token[token] = st
                if self._config_owner_token is None:
                    self._config_owner_token = token
                resp = {
                    "t": "welcome",
                    "v": PROTOCOL_VERSION,
                    "player_id": pid,
                    "token": token,
                    "tick_rate": self.tick_rate_hz,
                    "udp_port": self.udp_port,
                    "spawn": [float(player_spawn.x), float(player_spawn.y), float(player_spawn.z)],
                    "spawn_yaw": float(self.spawn_yaw),
                    "map_json": self.map_json,
                    "can_configure": bool(token == self._config_owner_token),
                    "cfg_v": int(self._tuning_version),
                    "tuning": self._tuning_snapshot(),
                }
                try:
                    cs.sendall(encode_json(resp))
                except Exception:
                    dead.append(cs)
            self._tcp_clients[cs] = buf

        for cs in dead:
            self._drop_tcp_client(cs)

    def _drop_tcp_client(self, cs: socket.socket) -> None:
        self._tcp_clients.pop(cs, None)
        token_to_drop = None
        for token, st in self._clients_by_token.items():
            if st.tcp_sock is cs:
                token_to_drop = token
                break
        if token_to_drop is not None:
            self._clients_by_token.pop(token_to_drop, None)
            if token_to_drop == self._config_owner_token:
                self._config_owner_token = None
        try:
            cs.close()
        except Exception:
            pass

    def _process_udp(self) -> None:
        while True:
            try:
                payload, addr = self._udp_sock.recvfrom(65535)
            except BlockingIOError:
                return
            except Exception:
                return
            parsed = decode_input_packet(payload)
            if not parsed:
                continue
            token, cmd = parsed
            st = self._clients_by_token.get(token)
            if st is None:
                continue
            st.udp_addr = addr
            if int(cmd.seq) >= int(st.last_input.seq):
                st.last_input = cmd

    def _wish_from_axes(self, *, yaw_deg: float, move_forward: int, move_right: int) -> LVector3f:
        h = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h), math.cos(h), 0)
        right = LVector3f(forward.y, -forward.x, 0)
        out = LVector3f(0, 0, 0)
        if move_forward > 0:
            out += forward
        if move_forward < 0:
            out -= forward
        if move_right > 0:
            out += right
        if move_right < 0:
            out -= right
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out

    @staticmethod
    def _view_dir(*, yaw_deg: float, pitch_deg: float) -> LVector3f:
        h = math.radians(float(yaw_deg))
        p = math.radians(float(pitch_deg))
        out = LVector3f(
            -math.sin(h) * math.cos(p),
            math.cos(h) * math.cos(p),
            math.sin(p),
        )
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out

    @staticmethod
    def _ray_sphere_t(*, origin: LVector3f, direction: LVector3f, center: LVector3f, radius: float) -> float | None:
        oc = origin - center
        b = 2.0 * float(oc.dot(direction))
        c = float(oc.dot(oc)) - float(radius * radius)
        disc = b * b - 4.0 * c
        if disc < 0.0:
            return None
        s = math.sqrt(disc)
        t0 = (-b - s) / 2.0
        t1 = (-b + s) / 2.0
        t = None
        if t0 >= 0.0:
            t = t0
        elif t1 >= 0.0:
            t = t1
        return t

    def _history_pos_for_tick(self, target: _ClientState, *, tick: int) -> LVector3f:
        if not target.rewind_history:
            return LVector3f(target.ctrl.pos)
        best = target.rewind_history[-1][1]
        best_dt = abs(int(target.rewind_history[-1][0]) - int(tick))
        for t, p in target.rewind_history:
            d = abs(int(t) - int(tick))
            if d < best_dt:
                best_dt = d
                best = p
        return LVector3f(best)

    def _grapple_or_damage(self, st: _ClientState) -> None:
        if st.hp <= 0:
            return
        origin = LVector3f(st.ctrl.pos.x, st.ctrl.pos.y, st.ctrl.pos.z + float(self.tuning.player_eye_height))
        direction = self._view_dir(yaw_deg=st.yaw, pitch_deg=st.pitch)
        if direction.lengthSquared() <= 1e-12:
            return
        reach = max(8.0, float(self.tuning.grapple_fire_range))

        nearest_player_t = None
        nearest_player: _ClientState | None = None
        hit_radius = float(self.tuning.player_radius) * 1.1
        aim_tick = int(st.last_input.server_tick_hint) if int(st.last_input.server_tick_hint) > 0 else int(self._tick)
        for other in self._clients_by_token.values():
            if other is st:
                continue
            rewound = self._history_pos_for_tick(other, tick=aim_tick)
            center = LVector3f(rewound.x, rewound.y, rewound.z + float(self.tuning.player_half_height) * 0.5)
            t = self._ray_sphere_t(origin=origin, direction=direction, center=center, radius=hit_radius)
            if t is None:
                continue
            if t > reach:
                continue
            if nearest_player_t is None or t < nearest_player_t:
                nearest_player_t = t
                nearest_player = other

        world_t = None
        hit = self.collision.ray_closest(origin, origin + direction * reach)
        if hit.hasHit():
            world_t = float(hit.getHitFraction()) * reach

        if nearest_player is not None and (world_t is None or float(nearest_player_t) <= float(world_t)):
            nearest_player.hp = max(0, int(nearest_player.hp) - 20)
            if nearest_player.hp <= 0:
                nearest_player.ctrl.respawn()
                nearest_player.yaw = float(self.spawn_yaw)
                nearest_player.pitch = 0.0
                nearest_player.hp = 100
                nearest_player.respawn_seq = int(nearest_player.respawn_seq) + 1
            return

        if st.ctrl.is_grapple_attached():
            st.ctrl.detach_grapple()
            return
        if hit.hasHit():
            if hasattr(hit, "getHitPos"):
                anchor = LVector3f(hit.getHitPos())
            else:
                frac = _clamp(float(hit.getHitFraction()), 0.0, 1.0)
                anchor = origin + (origin + direction * reach - origin) * frac
            st.ctrl.attach_grapple(anchor=anchor)

    def _simulate_tick(self) -> None:
        self._tick += 1
        for st in self._clients_by_token.values():
            cmd = st.last_input
            st.yaw -= (float(cmd.look_dx) / float(max(1, int(cmd.look_scale)))) * float(self.tuning.mouse_sensitivity)
            st.pitch = _clamp(
                st.pitch - (float(cmd.look_dy) / float(max(1, int(cmd.look_scale)))) * float(self.tuning.mouse_sensitivity),
                -88.0,
                88.0,
            )

            jump_requested = bool(cmd.jump_pressed)
            if self.tuning.autojump_enabled and cmd.jump_held and st.ctrl.grounded:
                jump_requested = True

            if cmd.grapple_pressed:
                self._grapple_or_damage(st)

            if not bool(self.tuning.grapple_enabled):
                st.ctrl.detach_grapple()
            wish = self._wish_from_axes(
                yaw_deg=st.yaw,
                move_forward=int(cmd.move_forward),
                move_right=int(cmd.move_right),
            )
            st.ctrl.step_with_intent(
                dt=self.fixed_dt,
                intent=MotionIntent(
                    wish_dir=LVector3f(wish),
                    jump_requested=bool(jump_requested),
                    slide_requested=bool(cmd.slide_pressed),
                ),
                yaw_deg=st.yaw,
                pitch_deg=st.pitch,
            )
            if float(st.ctrl.pos.z) < float(self.kill_z):
                st.ctrl.respawn()
                st.yaw = float(self.spawn_yaw)
                st.pitch = 0.0
                st.hp = 100
                st.respawn_seq = int(st.respawn_seq) + 1
            st.rewind_history.append((int(self._tick), LVector3f(st.ctrl.pos)))

    def _snapshot_players(self) -> tuple[list[int], dict[int, dict], dict[int, LVector3f], dict[int, int | None]]:
        ordered_ids: list[int] = []
        rows_by_id: dict[int, dict] = {}
        positions_by_id: dict[int, LVector3f] = {}
        leaves_by_id: dict[int, int | None] = {}
        for st in self._clients_by_token.values():
            pid = int(st.player_id)
            pos = LVector3f(st.ctrl.pos)
            ordered_ids.append(pid)
            positions_by_id[pid] = LVector3f(pos)
            rows_by_id[pid] = {
                "id": int(st.player_id),
                "n": st.name,
                "x": round(float(st.ctrl.pos.x), 6),
                "y": round(float(st.ctrl.pos.y), 6),
                "z": round(float(st.ctrl.pos.z), 6),
                "yaw": round(float(st.yaw), 4),
                "pitch": round(float(st.pitch), 4),
                "vx": round(float(st.ctrl.vel.x), 6),
                "vy": round(float(st.ctrl.vel.y), 6),
                "vz": round(float(st.ctrl.vel.z), 6),
                "ack": int(st.last_input.seq),
                "hp": int(st.hp),
                "rs": int(st.respawn_seq),
            }
            if self._relevance is not None:
                leaves_by_id[pid] = self._relevance.world_pos_to_leaf(pos=pos)
            else:
                leaves_by_id[pid] = None
        ordered_ids.sort()
        return (ordered_ids, rows_by_id, positions_by_id, leaves_by_id)

    def _broadcast_snapshot(self) -> None:
        ordered_ids, rows_by_id, positions_by_id, leaves_by_id = self._snapshot_players()
        if not ordered_ids:
            return

        all_players = [rows_by_id[int(pid)] for pid in ordered_ids if int(pid) in rows_by_id]
        packet_cache: dict[tuple[int, ...], bytes] = {
            tuple(int(pid) for pid in ordered_ids): encode_snapshot_packet(
                tick=self._tick,
                players=all_players,
                cfg_v=int(self._tuning_version),
                tuning=self._tuning_snapshot(),
            )
        }
        for st in self._clients_by_token.values():
            if st.udp_addr is None:
                continue
            key_ids = tuple(int(pid) for pid in ordered_ids)
            if self._relevance is not None and len(ordered_ids) > 1:
                visible_ids = self._relevance.relevant_player_ids(
                    viewer_player_id=int(st.player_id),
                    ordered_player_ids=list(ordered_ids),
                    positions_by_player_id=positions_by_id,
                    leaves_by_player_id=leaves_by_id,
                )
                key_ids = tuple(int(pid) for pid in visible_ids)
            pkt = packet_cache.get(key_ids)
            if pkt is None:
                players = [rows_by_id[int(pid)] for pid in key_ids if int(pid) in rows_by_id]
                pkt = encode_snapshot_packet(
                    tick=self._tick,
                    players=players,
                    cfg_v=int(self._tuning_version),
                    tuning=self._tuning_snapshot(),
                )
                packet_cache[key_ids] = pkt
            try:
                self._udp_sock.sendto(pkt, st.udp_addr)
            except Exception:
                pass

    def run_forever(self, *, stop_event: threading.Event | None = None) -> None:
        print(f"[ivan-server] TCP {self.host}:{self.tcp_port} | UDP {self.host}:{self.udp_port}")
        t_next_tick = time.monotonic()
        t_next_snap = time.monotonic()
        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                self._accept_tcp()
                self._process_tcp()
                self._process_udp()

                now = time.monotonic()
                while now >= t_next_tick:
                    self._simulate_tick()
                    t_next_tick += self.fixed_dt
                if now >= t_next_snap:
                    self._broadcast_snapshot()
                    t_next_snap += self.snapshot_dt

                sleep_for = min(t_next_tick, t_next_snap) - time.monotonic()
                if sleep_for > 0.0:
                    time.sleep(min(0.002, sleep_for))
        finally:
            self.close()


class EmbeddedHostServer:
    def __init__(
        self,
        *,
        host: str,
        tcp_port: int,
        udp_port: int,
        map_json: str | None,
        initial_tuning: dict[str, float | bool] | None = None,
        initial_spawn: tuple[float, float, float] | None = None,
        initial_spawn_yaw: float | None = None,
    ) -> None:
        self._srv = MultiplayerServer(
            host=host,
            tcp_port=tcp_port,
            udp_port=udp_port,
            map_json=map_json,
            initial_tuning=initial_tuning,
            initial_spawn=initial_spawn,
            initial_spawn_yaw=initial_spawn_yaw,
        )
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._srv.run_forever,
            kwargs={"stop_event": self._stop},
            daemon=True,
            name="ivan-embedded-host",
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self, *, timeout_s: float = 2.0) -> None:
        self._stop.set()
        self._thread.join(timeout=max(0.1, float(timeout_s)))
        self._srv.close()


def run_server(
    *,
    host: str,
    tcp_port: int,
    udp_port: int,
    map_json: str | None,
    initial_tuning: dict[str, float | bool] | None = None,
    initial_spawn: tuple[float, float, float] | None = None,
    initial_spawn_yaw: float | None = None,
) -> None:
    srv = MultiplayerServer(
        host=host,
        tcp_port=tcp_port,
        udp_port=udp_port,
        map_json=map_json,
        initial_tuning=initial_tuning,
        initial_spawn=initial_spawn,
        initial_spawn_yaw=initial_spawn_yaw,
    )
    srv.run_forever()
