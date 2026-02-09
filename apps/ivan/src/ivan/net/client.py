from __future__ import annotations

import json
import socket
from dataclasses import dataclass

from ivan.net.protocol import PROTOCOL_VERSION, encode_json


@dataclass(frozen=True)
class ClientWelcome:
    player_id: int
    token: str
    tick_rate: int
    udp_port: int
    map_json: str | None = None


class MultiplayerClient:
    def __init__(self, *, host: str, tcp_port: int, name: str) -> None:
        self.host = str(host)
        self.tcp_port = int(tcp_port)
        self.name = str(name)

        self.server_udp_addr: tuple[str, int] | None = None
        self.player_id: int = 0
        self.token: str = ""
        self.tick_rate: int = 60
        self.server_map_json: str | None = None
        self.can_configure: bool = False
        self.server_tuning_version: int = 0
        self.server_tuning: dict[str, float | bool] | None = None

        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.settimeout(5.0)
        self._tcp.connect((self.host, self.tcp_port))
        self._tcp.sendall(encode_json({"t": "hello", "v": PROTOCOL_VERSION, "name": self.name}))
        line = b""
        while not line.endswith(b"\n"):
            chunk = self._tcp.recv(4096)
            if not chunk:
                raise RuntimeError("Server closed during handshake")
            line += chunk
            if len(line) > 1_000_000:
                raise RuntimeError("Handshake payload too large")
        obj = json.loads(line.decode("utf-8", errors="ignore").strip())
        if not isinstance(obj, dict) or obj.get("t") != "welcome":
            raise RuntimeError("Invalid welcome packet")

        self.player_id = int(obj.get("player_id") or 0)
        self.token = str(obj.get("token") or "")
        self.tick_rate = int(obj.get("tick_rate") or 60)
        map_json_val = obj.get("map_json")
        if isinstance(map_json_val, str):
            self.server_map_json = map_json_val.strip() or None
        self.can_configure = bool(obj.get("can_configure"))
        self.server_tuning_version = int(obj.get("cfg_v") or 0)
        tuning_val = obj.get("tuning")
        if isinstance(tuning_val, dict):
            out: dict[str, float | bool] = {}
            for k, v in tuning_val.items():
                if not isinstance(k, str):
                    continue
                if isinstance(v, bool):
                    out[k] = bool(v)
                elif isinstance(v, (int, float)):
                    out[k] = float(v)
            self.server_tuning = out
        udp_port = int(obj.get("udp_port") or 0)
        if not self.token or self.player_id <= 0 or udp_port <= 0:
            raise RuntimeError("Incomplete welcome packet")
        self.server_udp_addr = (self.host, udp_port)

        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp.setblocking(False)
        self._latest_snapshot: dict | None = None

    def close(self) -> None:
        try:
            self._tcp.close()
        except Exception:
            pass
        try:
            self._udp.close()
        except Exception:
            pass

    def send_input(self, *, seq: int, server_tick_hint: int, cmd: dict) -> None:
        if not self.server_udp_addr:
            return
        pkt = {
            "t": "in",
            "v": PROTOCOL_VERSION,
            "token": self.token,
            "seq": int(seq),
            "st": max(0, int(server_tick_hint)),
            "dx": int(cmd.get("dx") or 0),
            "dy": int(cmd.get("dy") or 0),
            "ls": max(1, int(cmd.get("ls") or 1)),
            "mf": max(-1, min(1, int(cmd.get("mf") or 0))),
            "mr": max(-1, min(1, int(cmd.get("mr") or 0))),
            "jp": bool(cmd.get("jp")),
            "jh": bool(cmd.get("jh")),
            "dp": bool(cmd.get("dp")),
            "ch": bool(cmd.get("ch")),
            "gp": bool(cmd.get("gp")),
        }
        payload = json.dumps(pkt, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        try:
            self._udp.sendto(payload, self.server_udp_addr)
        except Exception:
            pass

    def poll(self) -> dict | None:
        while True:
            try:
                payload, _addr = self._udp.recvfrom(65535)
            except BlockingIOError:
                break
            except Exception:
                break
            try:
                obj = json.loads(payload.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if not isinstance(obj, dict) or obj.get("t") != "snap":
                continue
            self._latest_snapshot = obj
        return self._latest_snapshot

    def send_tuning(self, tuning: dict[str, float | bool]) -> None:
        payload: dict[str, float | bool] = {}
        for k, v in tuning.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, bool):
                payload[k] = bool(v)
            elif isinstance(v, (int, float)):
                payload[k] = float(v)
        try:
            self._tcp.sendall(encode_json({"t": "cfg", "tuning": payload}))
        except Exception:
            pass

    def send_respawn(self) -> None:
        try:
            self._tcp.sendall(encode_json({"t": "respawn"}))
        except Exception:
            pass
