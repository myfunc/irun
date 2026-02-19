from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import LVector3f, NodePath

from ivan.course.volumes import CylinderVolume
from ivan.game.ring_marker import build_ring


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
        build_ring(
            self.root_np,
            name=name,
            center=center,
            radius=radius,
            half_z=half_z,
            color=color,
            thickness=thickness,
            segs=56,
        )

    @staticmethod
    def _as_params(marker: CylinderVolume) -> tuple[LVector3f, float, float]:
        cx, cy, cz = marker.center_xyz
        return (
            LVector3f(float(cx), float(cy), float(cz)),
            max(0.10, float(marker.radius)),
            max(0.10, float(marker.half_z)),
        )

