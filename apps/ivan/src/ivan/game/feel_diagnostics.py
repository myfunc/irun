from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path

from panda3d.core import LVector3f


@dataclass
class FeelTickSample:
    t: float
    state: str
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    ax: float
    ay: float
    az: float
    speed: float
    contact_count: int
    floor_nx: float
    floor_ny: float
    floor_nz: float
    wall_nx: float
    wall_ny: float
    wall_nz: float
    jump_buffer_left: float
    coyote_left: float
    last_input_age: float
    inp_mf: int
    inp_mr: int
    inp_jp: bool
    inp_jh: bool
    inp_sp: bool


class RollingFeelDiagnostics:
    """Rolling HUD metrics + dumpable 2-5s movement log."""

    def __init__(self, *, tick_rate_hz: int, seconds: float = 5.0) -> None:
        self._frame_ms = deque(maxlen=1024)
        self._samples = deque(maxlen=max(1, int(float(tick_rate_hz) * max(2.0, min(5.0, float(seconds))))))

    def record_frame_dt(self, *, dt_s: float) -> None:
        self._frame_ms.append(max(0.0, float(dt_s)) * 1000.0)

    def frame_p95_ms(self) -> float:
        if not self._frame_ms:
            return 0.0
        vals = sorted(float(v) for v in self._frame_ms)
        idx = max(0, min(len(vals) - 1, int(round(0.95 * (len(vals) - 1)))))
        return float(vals[idx])

    def frame_ms_history(self) -> list[float]:
        """Return a snapshot of recent frametimes (ms) for graph overlay."""
        return list(self._frame_ms)

    def frame_spike_threshold_ms(self) -> float:
        """Baseline for spike detection: 2x median or 33ms (2 frames at 60Hz), whichever is higher."""
        if not self._frame_ms:
            return 33.0
        vals = sorted(float(v) for v in self._frame_ms)
        median = float(vals[len(vals) // 2])
        return max(33.0, median * 2.0)

    def record_tick(
        self,
        *,
        t: float,
        state: str,
        pos: LVector3f,
        vel: LVector3f,
        accel: LVector3f,
        contact_count: int,
        floor_normal: LVector3f,
        wall_normal: LVector3f,
        jump_buffer_left: float,
        coyote_left: float,
        last_input_age: float,
        inp_mf: int,
        inp_mr: int,
        inp_jp: bool,
        inp_jh: bool,
        inp_sp: bool,
    ) -> None:
        speed = float((LVector3f(vel)).length())
        self._samples.append(
            FeelTickSample(
                t=float(t),
                state=str(state),
                x=float(pos.x),
                y=float(pos.y),
                z=float(pos.z),
                vx=float(vel.x),
                vy=float(vel.y),
                vz=float(vel.z),
                ax=float(accel.x),
                ay=float(accel.y),
                az=float(accel.z),
                speed=speed,
                contact_count=int(contact_count),
                floor_nx=float(floor_normal.x),
                floor_ny=float(floor_normal.y),
                floor_nz=float(floor_normal.z),
                wall_nx=float(wall_normal.x),
                wall_ny=float(wall_normal.y),
                wall_nz=float(wall_normal.z),
                jump_buffer_left=float(jump_buffer_left),
                coyote_left=float(coyote_left),
                last_input_age=float(last_input_age),
                inp_mf=int(inp_mf),
                inp_mr=int(inp_mr),
                inp_jp=bool(inp_jp),
                inp_jh=bool(inp_jh),
                inp_sp=bool(inp_sp),
            )
        )

    def dump_json(self, *, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sample_count": int(len(self._samples)),
            "frame_p95_ms": float(self.frame_p95_ms()),
            "samples": [asdict(s) for s in self._samples],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
