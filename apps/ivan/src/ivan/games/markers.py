from __future__ import annotations

from dataclasses import dataclass
import math

from panda3d.core import LineSegs, LVector3f, NodePath

from ivan.course.volumes import CylinderVolume


@dataclass
class RaceMarkerRenderer:
    root_np: NodePath | None = None

    def attach(self, *, world_root: NodePath | None) -> None:
        if world_root is None:
            self.root_np = None
            return
        if self.root_np is None or self.root_np.isEmpty():
            self.root_np = world_root.attachNewNode("race-game-markers")
            return
        try:
            if self.root_np.getParent() != world_root:
                self.root_np.reparentTo(world_root)
        except Exception:
            self.root_np = world_root.attachNewNode("race-game-markers")

    def clear(self) -> None:
        if self.root_np is None or self.root_np.isEmpty():
            return
        for child in list(self.root_np.getChildren()):
            try:
                child.removeNode()
            except Exception:
                pass

    def render(
        self,
        *,
        mission: CylinderVolume | None,
        start: CylinderVolume | None,
        checkpoints: tuple[CylinderVolume, ...],
        finish: CylinderVolume | None,
        show_mission: bool,
        show_course: bool,
    ) -> None:
        if self.root_np is None or self.root_np.isEmpty():
            return
        self.clear()
        if bool(show_mission):
            self._draw_marker(
                marker=mission,
                name="mission-ring",
                color=(0.12, 0.84, 1.00, 0.82),
                thickness=4.0,
            )
        if not bool(show_course):
            return
        self._draw_marker(
            marker=start,
            name="race-start",
            color=(0.20, 1.00, 0.36, 0.80),
            thickness=3.0,
        )
        for idx, cp in enumerate(checkpoints, start=1):
            self._draw_marker(
                marker=cp,
                name=f"race-cp-{idx:02d}",
                color=(1.00, 0.85, 0.15, 0.82),
                thickness=3.0,
            )
        self._draw_marker(
            marker=finish,
            name="race-finish",
            color=(1.00, 0.45, 0.20, 0.82),
            thickness=3.0,
        )

    def _draw_marker(
        self,
        *,
        marker: CylinderVolume | None,
        name: str,
        color: tuple[float, float, float, float],
        thickness: float,
    ) -> None:
        if marker is None or self.root_np is None:
            return
        center, radius, half_z = self._as_params(marker)
        segs = 56
        ribs = 12
        ls = LineSegs(str(name))
        try:
            ls.setThickness(float(thickness))
        except Exception:
            pass
        ls.setColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))

        for zoff in (-half_z, 0.0, half_z):
            for i in range(segs + 1):
                ang = (math.tau * float(i)) / float(segs)
                x = float(center.x) + math.cos(ang) * float(radius)
                y = float(center.y) + math.sin(ang) * float(radius)
                z = float(center.z) + float(zoff)
                if i == 0:
                    ls.moveTo(x, y, z)
                else:
                    ls.drawTo(x, y, z)

        for i in range(ribs):
            ang = (math.tau * float(i)) / float(ribs)
            x = float(center.x) + math.cos(ang) * float(radius)
            y = float(center.y) + math.sin(ang) * float(radius)
            ls.moveTo(x, y, float(center.z) - float(half_z))
            ls.drawTo(x, y, float(center.z) + float(half_z))

        np = self.root_np.attachNewNode(ls.create())
        np.setTransparency(True)
        np.setDepthWrite(False)
        np.setBin("fixed", 14)
        np.setLightOff(1)

    @staticmethod
    def _as_params(marker: CylinderVolume) -> tuple[LVector3f, float, float]:
        cx, cy, cz = marker.center_xyz
        return (
            LVector3f(float(cx), float(cy), float(cz)),
            max(0.10, float(marker.radius)),
            max(0.10, float(marker.half_z)),
        )

