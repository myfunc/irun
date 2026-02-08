from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ivan.paths import app_root


DEMO_FORMAT_VERSION = 1
DEMO_EXT = ".ivan_demo.json"


@dataclass(frozen=True)
class DemoFrame:
    look_dx: int
    look_dy: int
    move_forward: int
    move_right: int
    jump_pressed: bool
    jump_held: bool
    crouch_held: bool
    grapple_pressed: bool
    noclip_toggle_pressed: bool


@dataclass(frozen=True)
class DemoMetadata:
    demo_name: str
    created_at_unix: float
    tick_rate: int
    look_scale: int
    map_id: str
    map_json: str | None
    tuning: dict[str, float | bool]


@dataclass
class DemoRecording:
    metadata: DemoMetadata
    frames: list[DemoFrame] = field(default_factory=list)


def demo_dir() -> Path:
    d = app_root() / "replays"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_name(text: str) -> str:
    out = []
    for ch in (text or "demo").strip().lower():
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        elif ch in (" ", "."):
            out.append("-")
    s = "".join(out).strip("-")
    return s or "demo"


def new_recording(
    *,
    tick_rate: int,
    look_scale: int,
    map_id: str,
    map_json: str | None,
    tuning: dict[str, float | bool],
) -> DemoRecording:
    now = float(time.time())
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
    base = _sanitize_name(map_id or "map")
    name = f"{stamp}_{base}"
    return DemoRecording(
        metadata=DemoMetadata(
            demo_name=name,
            created_at_unix=now,
            tick_rate=int(tick_rate),
            look_scale=max(1, int(look_scale)),
            map_id=str(map_id),
            map_json=str(map_json) if isinstance(map_json, str) and map_json.strip() else None,
            tuning=dict(tuning),
        )
    )


def append_frame(rec: DemoRecording, frame: DemoFrame) -> None:
    rec.frames.append(frame)


def save_recording(rec: DemoRecording) -> Path:
    out = demo_dir() / f"{rec.metadata.demo_name}{DEMO_EXT}"
    payload = {
        "format_version": DEMO_FORMAT_VERSION,
        "metadata": {
            "demo_name": rec.metadata.demo_name,
            "created_at_unix": rec.metadata.created_at_unix,
            "tick_rate": rec.metadata.tick_rate,
            "look_scale": rec.metadata.look_scale,
            "map_id": rec.metadata.map_id,
            "map_json": rec.metadata.map_json,
            "tuning": rec.metadata.tuning,
        },
        "frames": [
            {
                "dx": int(f.look_dx),
                "dy": int(f.look_dy),
                "mf": int(f.move_forward),
                "mr": int(f.move_right),
                "jp": bool(f.jump_pressed),
                "jh": bool(f.jump_held),
                "ch": bool(f.crouch_held),
                "gp": bool(f.grapple_pressed),
                "nt": bool(f.noclip_toggle_pressed),
            }
            for f in rec.frames
        ],
    }
    out.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return out


def load_replay(path: Path) -> DemoRecording:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid replay payload")
    ver = raw.get("format_version")
    if int(ver) != DEMO_FORMAT_VERSION:
        raise ValueError(f"Unsupported replay format_version={ver}")

    meta = raw.get("metadata")
    if not isinstance(meta, dict):
        raise ValueError("Missing replay metadata")

    md = DemoMetadata(
        demo_name=str(meta.get("demo_name") or path.stem),
        created_at_unix=float(meta.get("created_at_unix") or 0.0),
        tick_rate=int(meta.get("tick_rate") or 60),
        # Backward compatibility: older demos lacked look_scale and are treated as per-pixel integer deltas.
        look_scale=max(1, int(meta.get("look_scale") or 1)),
        map_id=str(meta.get("map_id") or "unknown"),
        map_json=(str(meta.get("map_json")) if isinstance(meta.get("map_json"), str) and str(meta.get("map_json")).strip() else None),
        tuning=dict(meta.get("tuning") or {}),
    )

    frames_in = raw.get("frames")
    if not isinstance(frames_in, list):
        raise ValueError("Missing replay frames")

    frames: list[DemoFrame] = []
    for row in frames_in:
        if not isinstance(row, dict):
            continue
        frames.append(
            DemoFrame(
                look_dx=int(row.get("dx") or 0),
                look_dy=int(row.get("dy") or 0),
                move_forward=max(-1, min(1, int(row.get("mf") or 0))),
                move_right=max(-1, min(1, int(row.get("mr") or 0))),
                jump_pressed=bool(row.get("jp")),
                jump_held=bool(row.get("jh")),
                crouch_held=bool(row.get("ch")),
                grapple_pressed=bool(row.get("gp")),
                noclip_toggle_pressed=bool(row.get("nt")),
            )
        )
    return DemoRecording(metadata=md, frames=frames)


def list_replays() -> list[Path]:
    d = demo_dir()
    out = sorted(d.glob(f"*{DEMO_EXT}"))
    out.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    return out
