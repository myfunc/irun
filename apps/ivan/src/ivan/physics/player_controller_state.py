from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.state import MotionWriteSource


class PlayerControllerStateMixin:
    def motion_state_name(self) -> str:
        if self._knockback_active:
            return "knockback"
        if self._hitstop_active:
            return "hitstop"
        if self.is_sliding():
            return "slide"
        if self.is_wallrunning():
            return "wallrun"
        return "ground" if bool(self.grounded) else "air"

    def last_velocity_write_source(self) -> str:
        return str(self._last_vel_write_source)

    def last_velocity_write_reason(self) -> str:
        return str(self._last_vel_write_reason)

    def set_external_velocity(self, *, vel: LVector3f, reason: str = "external") -> None:
        self._set_velocity(
            LVector3f(vel),
            source=MotionWriteSource.EXTERNAL,
            reason=str(reason),
        )

    def add_external_impulse(self, *, impulse: LVector3f, reason: str = "external_impulse") -> None:
        self._add_velocity(
            LVector3f(impulse),
            source=MotionWriteSource.IMPULSE,
            reason=str(reason),
        )

    def set_hitstop_active(self, active: bool) -> None:
        self._hitstop_active = bool(active)

    def set_knockback_active(self, active: bool) -> None:
        self._knockback_active = bool(active)

    def is_wallrunning(self) -> bool:
        return bool(self._wallrun_active)

    def wallrun_camera_roll_deg(self, *, yaw_deg: float) -> float:
        if not bool(self.tuning.wallrun_enabled):
            return 0.0
        if self.grounded:
            return 0.0
        if self._wallrun_reacquire_block_timer > 0.0:
            return 0.0
        if self._wall_normal.lengthSquared() <= 0.01:
            return 0.0
        # Keep visual feedback present while wall contact is recent enough to be perceived,
        # then drop quickly after contact is truly stale.
        if self._wall_contact_timer > 0.14:
            return 0.0
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if forward.lengthSquared() <= 1e-12:
            return 0.0
        right = LVector3f(forward.y, -forward.x, 0.0)
        side = float(right.dot(self._wall_normal))
        if abs(side) <= 1e-12:
            return 0.0
        # Slight side roll away from the wall to indicate active wallrun.
        return math.copysign(6.0, side)

    def vault_camera_pitch_deg(self) -> float:
        if self._vault_camera_timer <= 0.0:
            return 0.0
        duration = self._vault_camera_duration()
        # Smooth dip-and-recover curve (0 -> peak -> 0) to avoid one-frame snap.
        progress = max(0.0, min(1.0, 1.0 - float(self._vault_camera_timer) / duration))
        envelope = math.sin(math.pi * progress)
        return -1.9 * envelope

    @staticmethod
    def _vault_camera_duration() -> float:
        return 0.24

    def vault_debug_status(self) -> str:
        if self._vault_debug_timer <= 0.0:
            return "idle"
        return str(self._vault_debug)

    def _set_vault_debug(self, text: str, *, hold: float = 0.85) -> None:
        self._vault_debug = str(text)
        self._vault_debug_timer = max(0.0, float(hold))
