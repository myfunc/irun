from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import LVector3f

from ivan.course.volumes import AABBVolume, aabb_centered


@dataclass(frozen=True)
class CourseSpec:
    start: AABBVolume | None = None
    finish: AABBVolume | None = None

    def is_complete(self) -> bool:
        return self.start is not None and self.finish is not None


class TimeTrial:
    """
    Local time-trial: start timer when entering start volume, stop when entering finish volume.
    Uses edge-triggering (enter events) to avoid re-firing while standing in the volume.
    """

    def __init__(self, *, map_id: str, course: CourseSpec, pb_seconds: float | None) -> None:
        self.map_id = map_id
        self.course = course
        self.pb_seconds = pb_seconds

        self._running = False
        self._finished = False
        self._started_at: float | None = None
        self.last_seconds: float | None = None

        self._inside_start = False
        self._inside_finish = False

    def is_running(self) -> bool:
        return self._running

    def is_finished(self) -> bool:
        return self._finished

    def current_seconds(self, *, now: float) -> float | None:
        if self._running and self._started_at is not None:
            return max(0.0, float(now) - float(self._started_at))
        return None

    def cancel_run(self) -> None:
        self._running = False
        self._finished = False
        self._started_at = None
        self._inside_start = False
        self._inside_finish = False

    def tick(self, *, now: float, pos: LVector3f) -> str | None:
        """
        Returns an event string for lightweight HUD feedback:
        - "start" when the timer starts
        - "finish" when the timer finishes
        """

        start = self.course.start
        finish = self.course.finish
        if start is None or finish is None:
            self._inside_start = False
            self._inside_finish = False
            return None

        inside_start = bool(start.contains_point(x=float(pos.x), y=float(pos.y), z=float(pos.z)))
        inside_finish = bool(finish.contains_point(x=float(pos.x), y=float(pos.y), z=float(pos.z)))

        event: str | None = None

        # Start: rising edge on start volume.
        if inside_start and not self._inside_start:
            self._running = True
            self._finished = False
            self._started_at = float(now)
            self.last_seconds = None
            event = "start"

        # Finish: rising edge on finish volume while running.
        if self._running and inside_finish and not self._inside_finish:
            if self._started_at is not None:
                self.last_seconds = max(0.0, float(now) - float(self._started_at))
            self._running = False
            self._finished = True
            event = "finish"

        self._inside_start = inside_start
        self._inside_finish = inside_finish
        return event


def make_marker_aabb(*, pos: LVector3f, half_xy: float, half_z: float) -> AABBVolume:
    return aabb_centered(cx=float(pos.x), cy=float(pos.y), cz=float(pos.z), half_xy=float(half_xy), half_z=float(half_z))

