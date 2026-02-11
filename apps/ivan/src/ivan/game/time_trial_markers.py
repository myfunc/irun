from __future__ import annotations

from dataclasses import dataclass
import math

from panda3d.core import LineSegs, LVector3f, NodePath

from ivan.course.volumes import AABBVolume, CylinderVolume


@dataclass
class TimeTrialMarkerRuntime:
    root_np: NodePath | None = None


def _runtime(host) -> TimeTrialMarkerRuntime:
    st = getattr(host, "_time_trial_marker_runtime", None)
    if isinstance(st, TimeTrialMarkerRuntime):
        return st
    st = TimeTrialMarkerRuntime()
    setattr(host, "_time_trial_marker_runtime", st)
    return st


def init_runtime(host) -> None:
    st = _runtime(host)
    root = st.root_np
    world_root = getattr(host, "world_root", None)
    if world_root is None:
        st.root_np = None
        return
    if root is None or root.isEmpty():
        st.root_np = world_root.attachNewNode("time-trial-markers")
        return
    try:
        if root.getParent() != world_root:
            root.reparentTo(world_root)
    except Exception:
        st.root_np = world_root.attachNewNode("time-trial-markers")


def _clear(root: NodePath) -> None:
    for child in list(root.getChildren()):
        try:
            child.removeNode()
        except Exception:
            pass


def _as_cylinder(vol: AABBVolume | CylinderVolume | None) -> tuple[LVector3f, float, float] | None:
    if vol is None:
        return None
    if isinstance(vol, CylinderVolume):
        cx, cy, cz = vol.center_xyz
        return (LVector3f(float(cx), float(cy), float(cz)), max(0.10, float(vol.radius)), max(0.10, float(vol.half_z)))
    if isinstance(vol, AABBVolume):
        minx, miny, minz = vol.min_xyz
        maxx, maxy, maxz = vol.max_xyz
        cx = (float(minx) + float(maxx)) * 0.5
        cy = (float(miny) + float(maxy)) * 0.5
        cz = (float(minz) + float(maxz)) * 0.5
        radius = min(abs(float(maxx) - float(minx)), abs(float(maxy) - float(miny))) * 0.5
        half_z = abs(float(maxz) - float(minz)) * 0.5
        return (LVector3f(cx, cy, cz), max(0.10, radius), max(0.10, half_z))
    return None


def _build_ring(
    parent: NodePath,
    *,
    name: str,
    center: LVector3f,
    radius: float,
    half_z: float,
    color: tuple[float, float, float, float],
) -> None:
    segs = 48
    ribs = 12
    ls = LineSegs(str(name))
    try:
        ls.setThickness(3.0)
    except Exception:
        pass
    ls.setColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))

    for zoff in (-half_z, 0.0, half_z):
        for i in range(segs + 1):
            a = (math.tau * float(i)) / float(segs)
            x = float(center.x) + math.cos(a) * float(radius)
            y = float(center.y) + math.sin(a) * float(radius)
            z = float(center.z) + float(zoff)
            if i == 0:
                ls.moveTo(x, y, z)
            else:
                ls.drawTo(x, y, z)

    for i in range(ribs):
        a = (math.tau * float(i)) / float(ribs)
        x = float(center.x) + math.cos(a) * float(radius)
        y = float(center.y) + math.sin(a) * float(radius)
        ls.moveTo(x, y, float(center.z) - float(half_z))
        ls.drawTo(x, y, float(center.z) + float(half_z))

    np = parent.attachNewNode(ls.create())
    np.setTransparency(True)
    np.setDepthWrite(False)
    np.setBin("fixed", 14)
    np.setLightOff(1)


def set_markers(
    host,
    *,
    start: AABBVolume | CylinderVolume | None,
    finish: AABBVolume | CylinderVolume | None,
) -> None:
    init_runtime(host)
    st = _runtime(host)
    if st.root_np is None or st.root_np.isEmpty():
        return
    _clear(st.root_np)
    start_v = _as_cylinder(start)
    finish_v = _as_cylinder(finish)
    if start_v is not None:
        c, r, hz = start_v
        _build_ring(
            st.root_np,
            name="race-start",
            center=c,
            radius=r,
            half_z=hz,
            color=(0.25, 0.95, 0.35, 0.78),
        )
    if finish_v is not None:
        c, r, hz = finish_v
        _build_ring(
            st.root_np,
            name="race-finish",
            center=c,
            radius=r,
            half_z=hz,
            color=(0.98, 0.48, 0.16, 0.82),
        )


__all__ = ["init_runtime", "set_markers"]
