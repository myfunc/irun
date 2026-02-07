from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    LVector3,
    LVector4,
    TextNode,
    loadPrcFileData,
)


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False


@dataclass
class FeatureFlags:
    bunny_hop: bool = True
    air_control: bool = True
    show_debug: bool = True


@dataclass
class Tuning:
    gravity: float = 28.0
    jump_speed: float = 9.0
    ground_accel: float = 35.0
    air_accel: float = 16.0
    max_speed: float = 14.0
    friction: float = 8.0
    air_friction: float = 1.5


@dataclass
class Settings:
    tuning: Tuning = field(default_factory=Tuning)
    flags: FeatureFlags = field(default_factory=FeatureFlags)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Settings":
        tuning_payload = payload.get("tuning", {})
        flags_payload = payload.get("flags", {})
        return cls(
            tuning=Tuning(**{**asdict(Tuning()), **tuning_payload}),
            flags=FeatureFlags(**{**asdict(FeatureFlags()), **flags_payload}),
        )


@dataclass
class Arena:
    half_size: float = 20.0


@dataclass
class Platform:
    center: LVector3
    half_extents: LVector3

    @property
    def top(self) -> float:
        return self.center.z + self.half_extents.z


@dataclass
class PlayerState:
    position: LVector3
    velocity: LVector3
    radius: float


SETTINGS_PATH = Path(__file__).resolve().parents[2] / "settings.json"


class MVPApp(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        # Keep audio from being a dependency for early smoke runs / CI.
        loadPrcFileData("", "audio-library-name null")

        if cfg.smoke:
            # Avoid flashing a window in quick verification runs.
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.disableMouse()
        self.settings_path = SETTINGS_PATH
        self.settings = self._load_settings()
        self.arena = Arena()
        self.platforms: list[Platform] = []

        self._input_state = {
            "forward": False,
            "back": False,
            "left": False,
            "right": False,
            "jump": False,
        }
        self._jump_requested = False
        self._on_ground = False

        self._setup_scene()
        self._setup_input()
        self._setup_ui()

        self.taskMgr.add(self._update, "update-loop")

        if cfg.smoke:
            # Run a handful of frames then exit.
            self._frames_left = 8
            self.taskMgr.add(self._smoke_task, "smoke-exit")

    def _load_settings(self) -> Settings:
        if not self.settings_path.exists():
            return Settings()
        try:
            payload = json.loads(self.settings_path.read_text())
        except json.JSONDecodeError:
            return Settings()
        return Settings.from_dict(payload)

    def _save_settings(self) -> None:
        self.settings_path.write_text(json.dumps(self.settings.to_dict(), indent=2, sort_keys=True))

    def _setup_scene(self) -> None:
        # Basic arena: floor + a single platform.
        floor = self.loader.loadModel("models/box")
        floor.reparentTo(self.render)
        floor.setScale(self.arena.half_size, self.arena.half_size, 0.5)
        floor.setPos(0, 0, -0.5)

        platform_model = self.loader.loadModel("models/box")
        platform_model.reparentTo(self.render)
        platform_model.setScale(3.0, 3.0, 0.5)
        platform_model.setPos(6.0, 8.0, 1.0)

        platform = Platform(
            center=LVector3(6.0, 8.0, 1.0),
            half_extents=LVector3(3.0, 3.0, 0.5),
        )
        self.platforms.append(platform)

        # Player avatar (simple cube).
        self.player = PlayerState(
            position=LVector3(0, -5, 1.5),
            velocity=LVector3(0, 0, 0),
            radius=0.5,
        )
        self.player_model = self.loader.loadModel("models/box")
        self.player_model.reparentTo(self.render)
        self.player_model.setScale(self.player.radius)
        self.player_model.setPos(self.player.position)

        # Camera.
        self.camera.setPos(0, -18, 6)
        self.camera.lookAt(self.player_model)

        # Lighting.
        ambient = AmbientLight("ambient")
        ambient.setColor(LVector4(0.25, 0.25, 0.25, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LVector4(0.9, 0.9, 0.9, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.render.setLight(sun_np)

    def _setup_input(self) -> None:
        for key, name in [
            ("w", "forward"),
            ("s", "back"),
            ("a", "left"),
            ("d", "right"),
        ]:
            self.accept(key, self._set_input, [name, True])
            self.accept(f"{key}-up", self._set_input, [name, False])

        self.accept("space", self._queue_jump, [True])
        self.accept("space-up", self._queue_jump, [False])

        self.accept("r", self._reset_player)
        self.accept("f1", self._toggle_flag, ["bunny_hop"])
        self.accept("f2", self._toggle_flag, ["air_control"])
        self.accept("f3", self._toggle_flag, ["show_debug"])
        self.accept("f5", self._save_settings)

        self.accept("bracketleft", self._adjust_tuning, ["gravity", -2.0])
        self.accept("bracketright", self._adjust_tuning, ["gravity", 2.0])
        self.accept("comma", self._adjust_tuning, ["max_speed", -1.0])
        self.accept("period", self._adjust_tuning, ["max_speed", 1.0])
        self.accept("semicolon", self._adjust_tuning, ["ground_accel", -2.0])
        self.accept("apostrophe", self._adjust_tuning, ["ground_accel", 2.0])
        self.accept("slash", self._adjust_tuning, ["jump_speed", -1.0])
        self.accept("shift-slash", self._adjust_tuning, ["jump_speed", 1.0])

    def _setup_ui(self) -> None:
        self._debug_text = OnscreenText(
            text="",
            parent=self.aspect2d,
            pos=(-1.32, 0.9),
            align=TextNode.ALeft,
            scale=0.045,
            fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.6),
        )

    def _set_input(self, name: str, pressed: bool) -> None:
        self._input_state[name] = pressed

    def _queue_jump(self, pressed: bool) -> None:
        self._input_state["jump"] = pressed
        if pressed:
            self._jump_requested = True

    def _reset_player(self) -> None:
        self.player.position = LVector3(0, -5, 1.5)
        self.player.velocity = LVector3(0, 0, 0)

    def _toggle_flag(self, name: str) -> None:
        current = getattr(self.settings.flags, name)
        setattr(self.settings.flags, name, not current)

    def _adjust_tuning(self, name: str, delta: float) -> None:
        current = getattr(self.settings.tuning, name)
        setattr(self.settings.tuning, name, max(0.0, current + delta))

    def _update(self, task):  # type: ignore[no-untyped-def]
        dt = globalClock.getDt()
        dt = min(dt, 0.05)

        prev_position = LVector3(self.player.position)

        self._apply_horizontal_movement(dt)
        self._apply_gravity(dt)
        self._apply_jump()

        self.player.position += self.player.velocity * dt
        self._resolve_collisions(prev_position)
        self._clamp_to_arena()

        self.player_model.setPos(self.player.position)
        self._update_camera()
        self._update_debug_text()

        self._jump_requested = False
        return task.cont

    def _apply_horizontal_movement(self, dt: float) -> None:
        direction = LVector3(0, 0, 0)
        if self._input_state["forward"]:
            direction.y += 1
        if self._input_state["back"]:
            direction.y -= 1
        if self._input_state["left"]:
            direction.x -= 1
        if self._input_state["right"]:
            direction.x += 1

        if direction.length_squared() > 0:
            direction.normalize()

        tuning = self.settings.tuning
        accel = tuning.ground_accel if self._on_ground else tuning.air_accel
        if not self._on_ground and not self.settings.flags.air_control:
            accel = 0.0

        self.player.velocity.x += direction.x * accel * dt
        self.player.velocity.y += direction.y * accel * dt

        max_speed = tuning.max_speed
        speed = self.player.velocity.getXy().length()
        if speed > max_speed:
            scale = max_speed / speed
            self.player.velocity.x *= scale
            self.player.velocity.y *= scale

        if self._on_ground:
            if not self.settings.flags.bunny_hop or direction.length_squared() == 0:
                drop = tuning.friction * dt
                self._apply_friction(drop)
        else:
            drop = tuning.air_friction * dt
            self._apply_friction(drop)

    def _apply_friction(self, drop: float) -> None:
        speed = self.player.velocity.getXy().length()
        if speed <= 0:
            return
        new_speed = max(0.0, speed - drop)
        if new_speed == 0:
            self.player.velocity.x = 0
            self.player.velocity.y = 0
            return
        scale = new_speed / speed
        self.player.velocity.x *= scale
        self.player.velocity.y *= scale

    def _apply_gravity(self, dt: float) -> None:
        self.player.velocity.z -= self.settings.tuning.gravity * dt

    def _apply_jump(self) -> None:
        if self._on_ground and self._jump_requested:
            self.player.velocity.z = self.settings.tuning.jump_speed
            self._on_ground = False

    def _resolve_collisions(self, prev_position: LVector3) -> None:
        radius = self.player.radius
        self._on_ground = False

        if self.player.position.z - radius <= 0:
            self.player.position.z = radius
            self.player.velocity.z = 0
            self._on_ground = True

        for platform in self.platforms:
            if (
                abs(self.player.position.x - platform.center.x)
                <= platform.half_extents.x + radius
                and abs(self.player.position.y - platform.center.y)
                <= platform.half_extents.y + radius
            ):
                if (
                    prev_position.z - radius >= platform.top
                    and self.player.position.z - radius <= platform.top
                ):
                    self.player.position.z = platform.top + radius
                    self.player.velocity.z = 0
                    self._on_ground = True

    def _clamp_to_arena(self) -> None:
        limit = self.arena.half_size - self.player.radius
        self.player.position.x = max(-limit, min(limit, self.player.position.x))
        self.player.position.y = max(-limit, min(limit, self.player.position.y))

    def _update_camera(self) -> None:
        offset = LVector3(0, -18, 8)
        self.camera.setPos(self.player.position + offset)
        self.camera.lookAt(self.player.position)

    def _update_debug_text(self) -> None:
        if not self.settings.flags.show_debug:
            self._debug_text.setText("")
            return

        tuning = self.settings.tuning
        flags = self.settings.flags
        lines = [
            "Controls: WASD move | Space jump | R reset",
            "F1 bunny hop | F2 air control | F3 toggle HUD | F5 save JSON",
            "[ / ] gravity | , / . max speed | ; / ' ground accel | / / ? jump speed",
            "",
            f"Speed: {self.player.velocity.getXy().length():.2f}",
            f"Gravity: {tuning.gravity:.1f}",
            f"Jump speed: {tuning.jump_speed:.1f}",
            f"Ground accel: {tuning.ground_accel:.1f}",
            f"Air accel: {tuning.air_accel:.1f}",
            f"Max speed: {tuning.max_speed:.1f}",
            f"Friction: {tuning.friction:.1f}",
            f"Air friction: {tuning.air_friction:.1f}",
            f"Bunny hop: {'ON' if flags.bunny_hop else 'OFF'}",
            f"Air control: {'ON' if flags.air_control else 'OFF'}",
            f"Settings path: {self.settings_path.name}",
        ]
        self._debug_text.setText("\n".join(lines))

    def _smoke_task(self, task):  # type: ignore[no-untyped-def]
        # Add a tiny motion so we exercise the task loop.
        self.camera.setPos(self.camera.getPos() + LVector3(0, 0.0, 0.0))
        self._frames_left -= 1
        if self._frames_left <= 0:
            self.userExit()
            return task.done
        return task.cont


def run(*, smoke: bool = False) -> None:
    app = MVPApp(RunConfig(smoke=smoke))
    app.run()
