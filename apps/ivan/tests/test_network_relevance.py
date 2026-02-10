from __future__ import annotations

from pathlib import Path

from panda3d.core import LVector3f

from ivan.net.relevance import GoldSrcPvsRelevance, build_goldsrc_pvs_relevance_from_map
from ivan.world.goldsrc_visibility import GoldSrcBspVis


def _test_vis() -> GoldSrcBspVis:
    # X >= 0 -> leaf 0, X < 0 -> leaf 1.
    # Leaf 0 sees only leaf 0 (bit 0), leaf 1 sees only leaf 1 (bit 1).
    return GoldSrcBspVis(
        source_bsp="test.bsp",
        source_mtime_ns=0,
        root_node=0,
        planes=[(1.0, 0.0, 0.0, 0.0)],
        nodes=[(0, -1, -2)],
        leaves=[(0, 0, 0), (1, 0, 0)],
        leaf_faces=[],
        visdata=bytes([0x01, 0x02]),
        world_first_face=0,
        world_num_faces=0,
    )


def test_world_pos_to_leaf_and_visible_leaf_set() -> None:
    rel = GoldSrcPvsRelevance(vis=_test_vis(), map_scale=1.0, distance_fallback=0.0)
    assert rel.world_pos_to_leaf(pos=LVector3f(2.0, 0.0, 0.0)) == 0
    assert rel.world_pos_to_leaf(pos=LVector3f(-2.0, 0.0, 0.0)) == 1
    assert rel.visible_leaves_for_leaf(leaf=0) == {0}
    assert rel.visible_leaves_for_leaf(leaf=1) == {1}


def test_relevant_player_ids_uses_pvs_and_keeps_local_player() -> None:
    rel = GoldSrcPvsRelevance(vis=_test_vis(), map_scale=1.0, distance_fallback=0.0)
    ordered = [1, 2, 3]
    positions = {
        1: LVector3f(2.0, 0.0, 0.0),   # viewer in leaf 0
        2: LVector3f(-8.0, 0.0, 0.0),  # hidden in leaf 1
        3: LVector3f(6.0, 0.0, 0.0),   # visible in leaf 0
    }
    leaves = {pid: rel.world_pos_to_leaf(pos=pos) for pid, pos in positions.items()}
    out = rel.relevant_player_ids(
        viewer_player_id=1,
        ordered_player_ids=ordered,
        positions_by_player_id=positions,
        leaves_by_player_id=leaves,
    )
    assert out == [1, 3]


def test_relevant_player_ids_short_range_distance_fallback() -> None:
    rel = GoldSrcPvsRelevance(vis=_test_vis(), map_scale=1.0, distance_fallback=5.0)
    ordered = [1, 2]
    positions = {
        1: LVector3f(2.0, 0.0, 0.0),    # leaf 0
        2: LVector3f(-1.0, 0.0, 0.0),   # leaf 1, but only 3 units away
    }
    leaves = {pid: rel.world_pos_to_leaf(pos=pos) for pid, pos in positions.items()}
    out = rel.relevant_player_ids(
        viewer_player_id=1,
        ordered_player_ids=ordered,
        positions_by_player_id=positions,
        leaves_by_player_id=leaves,
    )
    assert out == [1, 2]


def test_build_goldsrc_relevance_requires_goldsrc_lightmap_encoding(monkeypatch) -> None:
    vis = _test_vis()
    monkeypatch.setattr("ivan.net.relevance.load_or_build_visibility_cache", lambda **_kwargs: vis)
    none_rel = build_goldsrc_pvs_relevance_from_map(
        map_json=Path("/tmp/fake/map.json"),
        payload={"lightmaps": {"encoding": "source_rgba"}},
    )
    assert none_rel is None

    rel = build_goldsrc_pvs_relevance_from_map(
        map_json=Path("/tmp/fake/map.json"),
        payload={"lightmaps": {"encoding": "goldsrc_rgb"}, "scale": 0.5},
    )
    assert rel is not None
    assert abs(float(rel.map_scale) - 0.5) < 1e-9
