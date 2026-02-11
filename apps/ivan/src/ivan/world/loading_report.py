from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

LOAD_STAGE_MAP_PARSE_IMPORT = "map_parse_import"
LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE = "material_sky_fog_resolve"
LOAD_STAGE_GEOMETRY_BUILD_ATTACH = "geometry_build_attach"
LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD = "visibility_cache_load_build"
LOAD_STAGE_FIRST_FRAME_READINESS = "first_frame_readiness"

LOAD_STAGE_ORDER: tuple[str, ...] = (
    LOAD_STAGE_MAP_PARSE_IMPORT,
    LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE,
    LOAD_STAGE_GEOMETRY_BUILD_ATTACH,
    LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD,
    LOAD_STAGE_FIRST_FRAME_READINESS,
)

# Initial soft budgets for perf tracking/tuning; these are intentionally conservative
# and can be tightened once more maps are measured in CI and local profiling.
LOAD_STAGE_BUDGET_MS: dict[str, float] = {
    LOAD_STAGE_MAP_PARSE_IMPORT: 700.0,
    LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE: 280.0,
    LOAD_STAGE_GEOMETRY_BUILD_ATTACH: 1600.0,
    LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD: 420.0,
    LOAD_STAGE_FIRST_FRAME_READINESS: 2600.0,
}

LOAD_REPORT_SCHEMA = "ivan.world.load_report.v1"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class LoadReportState:
    run_started_s: float = 0.0
    map_ref: str = ""
    map_profile: str = "auto"
    entry_kind_hint: str = "unknown"
    stage_ms: dict[str, float] = field(default_factory=lambda: {name: 0.0 for name in LOAD_STAGE_ORDER})
    visibility_cache: dict[str, object] = field(default_factory=dict)
    first_frame_emitted: bool = False
    optimizations: dict[str, bool] = field(default_factory=dict)


class LoadReporter:
    def __init__(self, *, time_fn: Callable[[], float] | None = None) -> None:
        self._time_fn = time_fn if callable(time_fn) else time.perf_counter
        self._state = LoadReportState()

    def begin(self, *, map_ref: str | Path | None, map_profile: str | None, entry_kind_hint: str = "unknown") -> None:
        ref = ""
        if map_ref is not None:
            try:
                ref = str(Path(map_ref))
            except Exception:
                ref = str(map_ref)
        self._state = LoadReportState(
            run_started_s=float(self._time_fn()),
            map_ref=ref,
            map_profile=str(map_profile or "auto"),
            entry_kind_hint=str(entry_kind_hint or "unknown"),
        )

    @contextmanager
    def stage(self, stage_name: str) -> Iterator[None]:
        if stage_name not in self._state.stage_ms:
            self._state.stage_ms[stage_name] = 0.0
        t0 = float(self._time_fn())
        try:
            yield
        finally:
            elapsed_ms = max(0.0, (float(self._time_fn()) - t0) * 1000.0)
            self._state.stage_ms[stage_name] = float(self._state.stage_ms.get(stage_name, 0.0)) + elapsed_ms

    def stage_ms(self, stage_name: str) -> float:
        return float(self._state.stage_ms.get(stage_name, 0.0))

    def set_stage_ms_max(self, stage_name: str, *, value_ms: float) -> None:
        cur = float(self._state.stage_ms.get(stage_name, 0.0))
        self._state.stage_ms[stage_name] = max(cur, max(0.0, float(value_ms)))

    def set_visibility_cache(self, **payload: object) -> None:
        clean: dict[str, object] = {}
        for k, v in payload.items():
            if v is None:
                continue
            clean[str(k)] = v
        self._state.visibility_cache = clean

    def set_optimizations(self, **flags: bool) -> None:
        for k, v in flags.items():
            self._state.optimizations[str(k)] = bool(v)

    def needs_first_frame(self) -> bool:
        return not bool(self._state.first_frame_emitted)

    def mark_first_frame_ready(self) -> None:
        if self._state.first_frame_emitted:
            return
        total_ms = max(0.0, (float(self._time_fn()) - float(self._state.run_started_s)) * 1000.0)
        self.set_stage_ms_max(LOAD_STAGE_FIRST_FRAME_READINESS, value_ms=total_ms)
        self._state.first_frame_emitted = True

    def as_payload(self, *, runtime_diag: dict | None = None) -> dict[str, object]:
        stage_ms = {name: float(self._state.stage_ms.get(name, 0.0)) for name in LOAD_STAGE_ORDER}
        total_ms = float(stage_ms.get(LOAD_STAGE_FIRST_FRAME_READINESS, 0.0))
        budgets_ms = {name: float(LOAD_STAGE_BUDGET_MS[name]) for name in LOAD_STAGE_ORDER}
        budget_pass = all(float(stage_ms[name]) <= float(budgets_ms[name]) for name in LOAD_STAGE_ORDER)

        payload: dict[str, object] = {
            "event": "world_load_report",
            "schema": LOAD_REPORT_SCHEMA,
            "timestamp_utc": _now_iso_utc(),
            "map_ref": str(self._state.map_ref),
            "entry_kind_hint": str(self._state.entry_kind_hint),
            "map_profile": str(self._state.map_profile),
            "stage_order": list(LOAD_STAGE_ORDER),
            "stages_ms": stage_ms,
            "total_ms": total_ms,
            "budgets_ms": budgets_ms,
            "budget_pass": bool(budget_pass),
            "visibility_cache": dict(self._state.visibility_cache),
            "optimizations": dict(self._state.optimizations),
        }
        if isinstance(runtime_diag, dict):
            payload["runtime"] = dict(runtime_diag)
        return payload
