from __future__ import annotations

from dataclasses import dataclass
import math


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


@dataclass(frozen=True)
class CylinderVolume:
    """
    Vertical cylinder used for GTA-style race checkpoints.
    """

    center_xyz: tuple[float, float, float]
    radius: float
    half_z: float

    def contains_point(self, *, x: float, y: float, z: float) -> bool:
        cx, cy, cz = self.center_xyz
        if abs(float(z) - float(cz)) > float(self.half_z):
            return False
        dx = float(x) - float(cx)
        dy = float(y) - float(cy)
        return (dx * dx) + (dy * dy) <= float(self.radius) * float(self.radius)


def aabb_centered(*, cx: float, cy: float, cz: float, half_xy: float, half_z: float) -> AABBVolume:
    return AABBVolume(
        min_xyz=(cx - half_xy, cy - half_xy, cz - half_z),
        max_xyz=(cx + half_xy, cy + half_xy, cz + half_z),
    )


def cylinder_centered(*, cx: float, cy: float, cz: float, radius: float, half_z: float) -> CylinderVolume:
    return CylinderVolume(
        center_xyz=(float(cx), float(cy), float(cz)),
        radius=max(0.05, float(radius)),
        half_z=max(0.05, float(half_z)),
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


def cylinder_from_json(obj: object) -> CylinderVolume | None:
    if not isinstance(obj, dict):
        return None
    center = obj.get("center")
    radius = obj.get("radius")
    half_z = obj.get("half_z")
    if not (isinstance(center, list) and len(center) == 3 and isinstance(radius, (int, float)) and isinstance(half_z, (int, float))):
        return None
    try:
        cx = float(center[0])
        cy = float(center[1])
        cz = float(center[2])
        rr = float(radius)
        hz = float(half_z)
    except Exception:
        return None
    if not math.isfinite(cx) or not math.isfinite(cy) or not math.isfinite(cz) or not math.isfinite(rr) or not math.isfinite(hz):
        return None
    return cylinder_centered(cx=cx, cy=cy, cz=cz, radius=rr, half_z=hz)


def cylinder_to_json(vol: CylinderVolume) -> dict:
    cx, cy, cz = vol.center_xyz
    return {
        "center": [float(cx), float(cy), float(cz)],
        "radius": float(vol.radius),
        "half_z": float(vol.half_z),
    }
