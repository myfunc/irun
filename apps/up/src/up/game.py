from __future__ import annotations

from dataclasses import dataclass

from ursina import (
    Ursina,
    Entity,
    Vec3,
    camera,
    color,
    held_keys,
    invoke,
    time,
)
from ursina import application


@dataclass
class Tuning:
    move_speed: float = 6.0
    jump_speed: float = 7.5
    gravity: float = 22.0


class Player(Entity):
    def __init__(self, tuning: Tuning) -> None:
        super().__init__(
            model="cube",
            color=color.azure,
            scale=Vec3(0.9, 1.8, 0.9),
            position=Vec3(0, 2, 0),
            collider="box",
        )
        self.tuning = tuning
        self._vel = Vec3(0, 0, 0)
        self._ground_y = 0.5  # top of ground plane (see ground thickness)

    def _is_grounded(self) -> bool:
        return self.y <= (self._ground_y + self.scale_y / 2 + 1e-3)

    def update(self) -> None:
        dt = time.dt

        # Movement (placeholder): camera-relative movement comes later.
        move = Vec3(
            held_keys["d"] - held_keys["a"],
            0,
            held_keys["w"] - held_keys["s"],
        )
        if move.length() > 0:
            move = move.normalized()

        self.x += move.x * self.tuning.move_speed * dt
        self.z += move.z * self.tuning.move_speed * dt

        # Gravity + jump.
        self._vel.y -= self.tuning.gravity * dt

        if self._is_grounded():
            self._vel.y = max(self._vel.y, 0)
            if held_keys["space"]:
                self._vel.y = self.tuning.jump_speed

        self.y += self._vel.y * dt

        # Simple ground collision.
        min_y = self._ground_y + self.scale_y / 2
        if self.y < min_y:
            self.y = min_y
            self._vel.y = 0


class CameraRig(Entity):
    def __init__(self, player: Player) -> None:
        super().__init__()
        self.player = player

    def update(self) -> None:
        target = self.player.position + Vec3(0, 3.5, -10)
        # Ursina's Vec3 doesn't expose lerp() consistently across versions.
        t = min(1.0, time.dt * 6.0)
        camera.position = camera.position + (target - camera.position) * t
        camera.look_at(self.player.position + Vec3(0, 1.2, 0))


def run(*, smoke: bool = False) -> None:
    app = Ursina(title="IRUN (Prototype)")

    # Minimal graybox scene.
    Entity(
        model="cube",
        color=color.gray,
        scale=Vec3(30, 1, 30),
        position=Vec3(0, 0, 0),
        collider="box",
    )
    Entity(
        model="cube",
        color=color.orange,
        scale=Vec3(4, 1, 4),
        position=Vec3(6, 1, 0),
        collider="box",
    )

    tuning = Tuning()
    player = Player(tuning)
    CameraRig(player)

    if smoke:
        # Used for quick verification in CI/dev: start the loop and exit shortly after.
        invoke(application.quit, delay=0.25)

    app.run()
