"""
Consistency tests for world->BSP coordinate mapping across relevance and visibility paths.

Ensures startup (spawn/geometry) and runtime (PVS culling, server relevance) use the same
canonical contract: scale-only, no Y-flip.
"""

from __future__ import annotations

from panda3d.core import LVector3f

# Import ivan.game first to resolve circular ivan.net dependency before relevance.
import ivan.game  # noqa: F401
from ivan.net.relevance import GoldSrcPvsRelevance
from ivan.world.goldsrc_visibility import GoldSrcBspVis
from ivan.world.scene_layers.visibility import world_to_bsp_pos


def _minimal_vis() -> GoldSrcBspVis:
    return GoldSrcBspVis(
        source_bsp="minimal.bsp",
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


class _MinimalScene:
    """Minimal scene contract for world_to_bsp_pos."""

    _map_scale: float = 1.0


def test_relevance_and_visibility_use_same_world_to_bsp_mapping() -> None:
    """
    Relevance (_world_to_bsp) and visibility (world_to_bsp_pos) must produce identical
    BSP coordinates for the same world position and scale.
    """
    scale = 2.5
    pos = LVector3f(10.0, -6.0, 4.0)

    rel = GoldSrcPvsRelevance(vis=_minimal_vis(), map_scale=scale, distance_fallback=0.0)
    bsp_relevance = rel._world_to_bsp(pos=pos)

    scene = _MinimalScene()
    scene._map_scale = scale
    bsp_visibility = world_to_bsp_pos(scene, pos=pos)

    assert bsp_relevance == bsp_visibility
    assert bsp_relevance == (4.0, -2.4, 1.6)

