from __future__ import annotations

import json
from dataclasses import dataclass

PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class InputCommand:
    seq: int
    server_tick_hint: int
    look_dx: int
    look_dy: int
    look_scale: int
    move_forward: int
    move_right: int
    jump_pressed: bool
    jump_held: bool
    crouch_held: bool
    grapple_pressed: bool


def encode_json(obj: dict) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def decode_json_line(line: bytes) -> dict | None:
    try:
        s = line.decode("utf-8", errors="ignore").strip()
        if not s:
            return None
        v = json.loads(s)
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def decode_input_packet(payload: bytes) -> tuple[str, InputCommand] | None:
    try:
        obj = json.loads(payload.decode("utf-8", errors="ignore"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("t") != "in":
        return None
    token = obj.get("token")
    if not isinstance(token, str) or not token:
        return None
    cmd = InputCommand(
        seq=int(obj.get("seq") or 0),
        server_tick_hint=max(0, int(obj.get("st") or 0)),
        look_dx=int(obj.get("dx") or 0),
        look_dy=int(obj.get("dy") or 0),
        look_scale=max(1, int(obj.get("ls") or 1)),
        move_forward=max(-1, min(1, int(obj.get("mf") or 0))),
        move_right=max(-1, min(1, int(obj.get("mr") or 0))),
        jump_pressed=bool(obj.get("jp")),
        jump_held=bool(obj.get("jh")),
        crouch_held=bool(obj.get("ch")),
        grapple_pressed=bool(obj.get("gp")),
    )
    return (token, cmd)


def encode_snapshot_packet(
    *,
    tick: int,
    players: list[dict],
    cfg_v: int | None = None,
    tuning: dict[str, float | bool] | None = None,
) -> bytes:
    obj = {
        "t": "snap",
        "v": PROTOCOL_VERSION,
        "tick": int(tick),
        "players": players,
    }
    if cfg_v is not None:
        obj["cfg_v"] = int(cfg_v)
    if isinstance(tuning, dict):
        obj["tuning"] = tuning
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
