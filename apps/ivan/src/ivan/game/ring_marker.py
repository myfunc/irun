"""Shared ring marker rendering (LineSegs-based GTA-style circular rings)."""

from __future__ import annotations

import math

from panda3d.core import LineSegs, LVector3f, NodePath


def build_ring(
    parent: NodePath,
    *,
    name: str,
    center: LVector3f,
    radius: float,
    half_z: float,
    color: tuple[float, float, float, float],
    thickness: float = 3.0,
    segs: int = 48,
    ribs: int = 12,
    bin: int = 14,
) -> None:
    """
    Build a translucent ring marker (3 horizontal circles + vertical ribs) and attach to parent.

    Caller defines color, thickness, and visibility bin to preserve existing visuals.
    """
    ls = LineSegs(str(name))
    try:
        ls.setThickness(float(thickness))
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
    np.setBin("fixed", bin)
    np.setLightOff(1)


__all__ = ["build_ring"]
