from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AABBVolume:
    """
    Simple axis-aligned volume used for course triggers.
    Coordinates are in world space.
    """

    min_xyz: tuple[float, float, float]
    max_xyz: tuple[float, float, float]

    def contains_point(self, *, x: float, y: float, z: float) -> bool:
        (minx, miny, minz) = self.min_xyz
        (maxx, maxy, maxz) = self.max_xyz
        return (minx <= x <= maxx) and (miny <= y <= maxy) and (minz <= z <= maxz)


def aabb_centered(*, cx: float, cy: float, cz: float, half_xy: float, half_z: float) -> AABBVolume:
    return AABBVolume(
        min_xyz=(cx - half_xy, cy - half_xy, cz - half_z),
        max_xyz=(cx + half_xy, cy + half_xy, cz + half_z),
    )


def aabb_from_json(obj: object) -> AABBVolume | None:
    if not isinstance(obj, dict):
        return None
    mn = obj.get("min")
    mx = obj.get("max")
    if not (isinstance(mn, list) and isinstance(mx, list) and len(mn) == 3 and len(mx) == 3):
        return None
    try:
        min_xyz = (float(mn[0]), float(mn[1]), float(mn[2]))
        max_xyz = (float(mx[0]), float(mx[1]), float(mx[2]))
    except Exception:
        return None
    return AABBVolume(min_xyz=min_xyz, max_xyz=max_xyz)


def aabb_to_json(vol: AABBVolume) -> dict:
    (minx, miny, minz) = vol.min_xyz
    (maxx, maxy, maxz) = vol.max_xyz
    return {"min": [minx, miny, minz], "max": [maxx, maxy, maxz]}

