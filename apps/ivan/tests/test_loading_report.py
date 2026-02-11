from __future__ import annotations

from pathlib import Path

from ivan.world.goldsrc_visibility import GoldSrcBspVis, _VIS_CACHE_MEM, load_or_build_visibility_cache
from ivan.world.loading_report import (
    LOAD_STAGE_FIRST_FRAME_READINESS,
    LOAD_STAGE_GEOMETRY_BUILD_ATTACH,
    LOAD_STAGE_MAP_PARSE_IMPORT,
    LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE,
    LOAD_STAGE_ORDER,
    LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD,
    LoadReporter,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def tick(self, dt: float) -> None:
        self.now += float(dt)

    def __call__(self) -> float:
        return float(self.now)


def test_load_report_emits_stable_stage_names_and_first_frame_total() -> None:
    clock = _Clock()
    rep = LoadReporter(time_fn=clock)
    rep.begin(map_ref="apps/ivan/assets/maps/demo/demo.map", map_profile="dev-fast")

    with rep.stage(LOAD_STAGE_MAP_PARSE_IMPORT):
        clock.tick(0.040)
    with rep.stage(LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
        clock.tick(0.015)
    with rep.stage(LOAD_STAGE_GEOMETRY_BUILD_ATTACH):
        clock.tick(0.110)
    with rep.stage(LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD):
        clock.tick(0.020)

    # Extra setup cost before first playable frame should be captured in first_frame_readiness.
    clock.tick(0.030)
    rep.mark_first_frame_ready()
    payload = rep.as_payload(runtime_diag={"entry_kind": "direct-map"})

    assert payload["stage_order"] == list(LOAD_STAGE_ORDER)
    stages = payload["stages_ms"]
    assert isinstance(stages, dict)
    assert float(stages[LOAD_STAGE_MAP_PARSE_IMPORT]) > 0.0
    assert float(stages[LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE]) > 0.0
    assert float(stages[LOAD_STAGE_GEOMETRY_BUILD_ATTACH]) > 0.0
    assert float(stages[LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD]) > 0.0
    assert float(stages[LOAD_STAGE_FIRST_FRAME_READINESS]) >= 210.0
    assert float(payload["total_ms"]) == float(stages[LOAD_STAGE_FIRST_FRAME_READINESS])


def test_visibility_cache_reports_memory_hit_on_repeated_load(tmp_path: Path) -> None:
    _VIS_CACHE_MEM.clear()
    cache_path = tmp_path / "visibility.goldsrc.json"
    vis = GoldSrcBspVis(
        source_bsp="",
        source_mtime_ns=0,
        root_node=0,
        planes=[(0.0, 0.0, 1.0, 0.0)],
        nodes=[(0, -1, -1)],
        leaves=[(-1, 0, 0)],
        leaf_faces=[],
        visdata=b"\xff",
        world_first_face=0,
        world_num_faces=0,
    )
    cache_path.write_text(vis.to_json(), encoding="utf-8")

    d0: dict[str, object] = {}
    out0 = load_or_build_visibility_cache(cache_path=cache_path, source_bsp_path=None, diagnostics=d0)
    assert out0 is not None
    assert d0.get("result") == "disk-hit"

    d1: dict[str, object] = {}
    out1 = load_or_build_visibility_cache(cache_path=cache_path, source_bsp_path=None, diagnostics=d1)
    assert out1 is not None
    assert d1.get("result") == "memory-hit"
