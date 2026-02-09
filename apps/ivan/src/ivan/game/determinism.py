from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from panda3d.core import LVector3f


def deterministic_state_hash(
    *,
    pos: LVector3f,
    vel: LVector3f,
    yaw_deg: float,
    pitch_deg: float,
    grounded: bool,
    state: str,
    contact_count: int,
    jump_buffer_left: float,
    coyote_left: float,
) -> str:
    """Quantized per-tick state hash for replay/harness determinism checks."""

    q = (
        int(round(float(pos.x) * 1000.0)),
        int(round(float(pos.y) * 1000.0)),
        int(round(float(pos.z) * 1000.0)),
        int(round(float(vel.x) * 1000.0)),
        int(round(float(vel.y) * 1000.0)),
        int(round(float(vel.z) * 1000.0)),
        int(round(float(yaw_deg) * 100.0)),
        int(round(float(pitch_deg) * 100.0)),
        int(bool(grounded)),
        str(state),
        int(contact_count),
        int(round(float(jump_buffer_left) * 1000.0)),
        int(round(float(coyote_left) * 1000.0)),
    )
    h = hashlib.blake2b(digest_size=8)
    h.update(repr(q).encode("utf-8", errors="strict"))
    return h.hexdigest()


@dataclass(frozen=True)
class DeterminismSample:
    t: float
    tick_hash: str
    trace_hash: str


class DeterminismTrace:
    """Rolling determinism trace with per-tick hash + cumulative trace hash."""

    def __init__(self, *, tick_rate_hz: int, seconds: float = 5.0) -> None:
        maxlen = max(1, int(float(tick_rate_hz) * max(2.0, min(10.0, float(seconds)))))
        self._samples: deque[DeterminismSample] = deque(maxlen=maxlen)
        self._trace_hash = "0" * 16

    def reset(self) -> None:
        self._samples.clear()
        self._trace_hash = "0" * 16

    def record(
        self,
        *,
        t: float,
        tick_hash: str,
    ) -> str:
        prev = str(self._trace_hash)
        h = hashlib.blake2b(digest_size=8)
        h.update(prev.encode("utf-8", errors="strict"))
        h.update(str(tick_hash).encode("utf-8", errors="strict"))
        self._trace_hash = h.hexdigest()
        self._samples.append(
            DeterminismSample(
                t=float(t),
                tick_hash=str(tick_hash),
                trace_hash=str(self._trace_hash),
            )
        )
        return str(self._trace_hash)

    def latest_trace_hash(self) -> str:
        return str(self._trace_hash)

    def sample_count(self) -> int:
        return int(len(self._samples))

    def dump_json(self, *, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sample_count": int(len(self._samples)),
            "latest_trace_hash": str(self._trace_hash),
            "samples": [asdict(s) for s in self._samples],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
