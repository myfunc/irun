from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from panda3d.core import LVector3f

from ivan.world.goldsrc_visibility import (
    GoldSrcBspVis,
    decode_pvs_row,
    iter_visible_leaf_indices,
    load_or_build_visibility_cache,
)


@dataclass
class GoldSrcPvsRelevance:
    """
    Server-side relevance filter based on GoldSrc PVS leaf visibility.

    Distances are still used as a short-range fallback so close players are not hidden by
    PVS edge cases (for example, transient invalid leaves near seams).
    """

    vis: GoldSrcBspVis
    map_scale: float = 1.0
    distance_fallback: float = 8.0
    _visible_leaf_cache: dict[int, set[int]] = field(default_factory=dict, init=False, repr=False)

    def _world_to_bsp(self, *, pos: LVector3f) -> tuple[float, float, float]:
        scale = float(self.map_scale) if float(self.map_scale) > 0.0 else 1.0
        return (
            float(pos.x) / scale,
            -float(pos.y) / scale,
            float(pos.z) / scale,
        )

    def world_pos_to_leaf(self, *, pos: LVector3f) -> int | None:
        try:
            x, y, z = self._world_to_bsp(pos=pos)
            leaf = int(self.vis.point_leaf(x=float(x), y=float(y), z=float(z)))
        except Exception:
            return None
        if leaf < 0 or leaf >= int(self.vis.leaf_count):
            return None
        return int(leaf)

    def visible_leaves_for_leaf(self, *, leaf: int) -> set[int]:
        leaf_i = int(leaf)
        cached = self._visible_leaf_cache.get(leaf_i)
        if cached is not None:
            return set(cached)
        if leaf_i < 0 or leaf_i >= int(self.vis.leaf_count):
            return set()
        try:
            vis_offset = int(self.vis.leaves[leaf_i][0])
        except Exception:
            vis_offset = -1
        row = decode_pvs_row(
            visdata=self.vis.visdata,
            offset=int(vis_offset),
            leaf_count=int(self.vis.leaf_count),
        )
        out = set(int(i) for i in iter_visible_leaf_indices(row=row))
        out.add(leaf_i)
        if len(self._visible_leaf_cache) >= 512:
            self._visible_leaf_cache.clear()
        self._visible_leaf_cache[leaf_i] = set(out)
        return out

    def should_replicate(
        self,
        *,
        viewer_pos: LVector3f,
        target_pos: LVector3f,
        viewer_leaf: int | None,
        target_leaf: int | None,
    ) -> bool:
        dist_sq = float((LVector3f(target_pos) - LVector3f(viewer_pos)).lengthSquared())
        fallback = max(0.0, float(self.distance_fallback))
        if dist_sq <= (fallback * fallback):
            return True
        if viewer_leaf is None or target_leaf is None:
            return True
        visible = self.visible_leaves_for_leaf(leaf=int(viewer_leaf))
        return int(target_leaf) in visible

    def relevant_player_ids(
        self,
        *,
        viewer_player_id: int,
        ordered_player_ids: list[int],
        positions_by_player_id: dict[int, LVector3f],
        leaves_by_player_id: dict[int, int | None],
    ) -> list[int]:
        viewer_id = int(viewer_player_id)
        viewer_pos = positions_by_player_id.get(viewer_id)
        viewer_leaf = leaves_by_player_id.get(viewer_id)
        if viewer_pos is None:
            return list(int(pid) for pid in ordered_player_ids)

        out: list[int] = []
        for pid in ordered_player_ids:
            pid_i = int(pid)
            if pid_i == viewer_id:
                out.append(pid_i)
                continue
            target_pos = positions_by_player_id.get(pid_i)
            if target_pos is None:
                continue
            target_leaf = leaves_by_player_id.get(pid_i)
            if self.should_replicate(
                viewer_pos=LVector3f(viewer_pos),
                target_pos=LVector3f(target_pos),
                viewer_leaf=viewer_leaf,
                target_leaf=target_leaf,
            ):
                out.append(pid_i)
        if viewer_id not in out:
            out.insert(0, viewer_id)
        return out


def build_goldsrc_pvs_relevance_from_map(
    *,
    map_json: Path,
    payload: dict,
    distance_fallback: float = 8.0,
) -> GoldSrcPvsRelevance | None:
    """
    Build a GoldSrc relevance filter from map payload data.

    Note: we intentionally do not build visibility cache on the server path to avoid
    host startup stalls. AOI is enabled only when the cache already exists.
    """

    if not isinstance(payload, dict):
        return None
    lm = payload.get("lightmaps")
    lm_encoding = lm.get("encoding") if isinstance(lm, dict) else None
    if not (isinstance(lm_encoding, str) and lm_encoding.strip() == "goldsrc_rgb"):
        return None

    cache_path = Path(map_json).parent / "visibility.goldsrc.json"
    vis = load_or_build_visibility_cache(cache_path=cache_path, source_bsp_path=None)
    if vis is None:
        return None

    map_scale = 1.0
    try:
        scale = float(payload.get("scale") or 1.0)
        if scale > 0.0:
            map_scale = float(scale)
    except Exception:
        map_scale = 1.0

    return GoldSrcPvsRelevance(
        vis=vis,
        map_scale=float(map_scale),
        distance_fallback=max(0.0, float(distance_fallback)),
    )
