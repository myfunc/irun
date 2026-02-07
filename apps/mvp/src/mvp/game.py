from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    BitMask32,
    CollisionBox,
    CollisionCapsule,
    CollisionHandlerPusher,
    CollisionHandlerQueue,
    CollisionNode,
    CollisionRay,
    CollisionTraverser,
    DirectionalLight,
    LVector3,
    LVector4,
    Point3,
    TextNode,
    loadPrcFileData,
)


SETTINGS_VERSION = 1


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False
    settings_path: Path = Path("mvp_settings.json")


@dataclass
class FeatureFlags:
    enable_air_control: bool = True
    enable_bunny_hop: bool = True
    enable_friction: bool = True
    enable_sprint: bool = False


@dataclass
class TuningSettings:
    gravity: float = -24.0
    jump_speed: float = 9.0
    move_speed: float = 10.0
    sprint_multiplier: float = 1.4
    ground_accel: float = 50.0
    air_accel: float = 18.0
    air_control: float = 0.45
    friction: float = 10.0
    max_speed: float = 18.0


@dataclass
class GameSettings:
    version: int = SETTINGS_VERSION
    tuning: TuningSettings = field(default_factory=TuningSettings)
    flags: FeatureFlags = field(default_factory=FeatureFlags)

    @staticmethod
    def from_dict(data: dict) -> "GameSettings":
        tuning = TuningSettings(**data.get("tuning", {}))
        flags = FeatureFlags(**data.get("flags", {}))
        version = data.get("version", SETTINGS_VERSION)
        return GameSettings(version=version, tuning=tuning, flags=flags)

    def to_dict(self) -> dict:
        return asdict(self)


class MVPApp(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        loadPrcFileData("", "audio-library-name null")

        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.disableMouse()
        self.settings_path = cfg.settings_path
        self.settings = self._load_settings(self.settings_path)

        self._key_state: dict[str, bool] = {
            "forward": False,
            "back": False,
            "left": False,
            "right": False,
            "jump": False,
            "sprint": False,
        }
        self._velocity = LVector3(0, 0, 0)
        self._wish_jump = False
        self._is_grounded = False
        self._debug_visible = True

        self._setup_scene()
        self._setup_player()
        self._setup_collision()
        self._setup_controls()
        self._setup_debug_hud()

        self.taskMgr.add(self._update_task, "update")

        if cfg.smoke:
            self._frames_left = 8
            self.taskMgr.add(self._smoke_task, "smoke-exit")

    def _load_settings(self, path: Path) -> GameSettings:
        if not path.exists():
            return GameSettings()
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return GameSettings.from_dict(payload)

    def _save_settings(self) -> None:
        payload = self.settings.to_dict()
        with self.settings_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    def _setup_scene(self) -> None:
        self.setBackgroundColor(0.04, 0.04, 0.06)

        floor_model = self.loader.loadModel("models/box")
        floor_model.reparentTo(self.render)
        floor_model.setScale(60, 60, 1)
        floor_model.setPos(0, 0, -1)
        floor_model.setColor(0.18, 0.18, 0.2, 1)

        platform_model = self.loader.loadModel("models/box")
        platform_model.reparentTo(self.render)
        platform_model.setScale(6, 6, 1)
        platform_model.setPos(8, 14, 2)
        platform_model.setColor(0.25, 0.25, 0.3, 1)

        ambient = AmbientLight("ambient")
        ambient.setColor(LVector4(0.2, 0.2, 0.2, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LVector4(0.85, 0.85, 0.85, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.render.setLight(sun_np)

        self._platform_model = platform_model
        self._floor_model = floor_model

    def _setup_player(self) -> None:
        self.player = self.render.attachNewNode("player")
        self.player.setPos(0, 0, 1.0)

        avatar = self.loader.loadModel("models/smiley")
        avatar.reparentTo(self.player)
        avatar.setScale(0.7)
        avatar.setPos(0, 0, 0.7)

        self.camera.setPos(0, -18, 8)
        self.camera.lookAt(self.player)

    def _setup_collision(self) -> None:
        self.cTrav = CollisionTraverser()

        world_mask = BitMask32.bit(1)

        floor_node = CollisionNode("floor")
        floor_node.addSolid(CollisionBox(Point3(0, 0, 0), 60, 60, 1))
        floor_node.setIntoCollideMask(world_mask)
        floor_np = self.render.attachNewNode(floor_node)
        floor_np.setPos(0, 0, -1)

        platform_node = CollisionNode("platform")
        platform_node.addSolid(CollisionBox(Point3(0, 0, 0), 6, 6, 1))
        platform_node.setIntoCollideMask(world_mask)
        platform_np = self.render.attachNewNode(platform_node)
        platform_np.setPos(8, 14, 2)

        player_node = CollisionNode("player")
        player_node.addSolid(
            CollisionCapsule(
                Point3(0, 0, 0.4),
                Point3(0, 0, 1.4),
                0.4,
            )
        )
        player_node.setFromCollideMask(world_mask)
        self.player_collider = self.player.attachNewNode(player_node)

        self._pusher = CollisionHandlerPusher()
        self._pusher.addCollider(self.player_collider, self.player)
        self.cTrav.addCollider(self.player_collider, self._pusher)

        ray_node = CollisionNode("ground-ray")
        ray_node.addSolid(CollisionRay(0, 0, 0.2, 0, 0, -1))
        ray_node.setFromCollideMask(world_mask)
        self._ground_ray = self.player.attachNewNode(ray_node)
        self._ground_handler = CollisionHandlerQueue()
        self.cTrav.addCollider(self._ground_ray, self._ground_handler)

        self._floor_np = floor_np
        self._platform_np = platform_np

    def _setup_controls(self) -> None:
        self.accept("w", self._set_key, ["forward", True])
        self.accept("w-up", self._set_key, ["forward", False])
        self.accept("s", self._set_key, ["back", True])
        self.accept("s-up", self._set_key, ["back", False])
        self.accept("a", self._set_key, ["left", True])
        self.accept("a-up", self._set_key, ["left", False])
        self.accept("d", self._set_key, ["right", True])
        self.accept("d-up", self._set_key, ["right", False])
        self.accept("space", self._set_key, ["jump", True])
        self.accept("space-up", self._set_key, ["jump", False])
        self.accept("shift", self._set_key, ["sprint", True])
        self.accept("shift-up", self._set_key, ["sprint", False])

        self.accept("f1", self._toggle_debug)
        self.accept("f2", self._toggle_flag, ["enable_air_control"])
        self.accept("f3", self._toggle_flag, ["enable_bunny_hop"])
        self.accept("f4", self._toggle_flag, ["enable_friction"])
        self.accept("f5", self._save_settings)
        self.accept("f6", self._reload_settings)

        self.accept("[", self._adjust_tuning, ["gravity", 1.0])
        self.accept("]", self._adjust_tuning, ["gravity", -1.0])
        self.accept(";", self._adjust_tuning, ["jump_speed", -0.5])
        self.accept("'", self._adjust_tuning, ["jump_speed", 0.5])
        self.accept(",", self._adjust_tuning, ["move_speed", -0.5])
        self.accept(".", self._adjust_tuning, ["move_speed", 0.5])
        self.accept("o", self._adjust_tuning, ["friction", -0.5])
        self.accept("p", self._adjust_tuning, ["friction", 0.5])

    def _setup_debug_hud(self) -> None:
        self._debug_text = OnscreenText(
            text="",
            pos=(-1.28, 0.92),
            align=TextNode.ALeft,
            scale=0.045,
            fg=(0.9, 0.9, 0.9, 1),
            mayChange=True,
        )
        self._refresh_debug_text()

    def _toggle_debug(self) -> None:
        self._debug_visible = not self._debug_visible
        self._debug_text.hide() if not self._debug_visible else self._debug_text.show()

    def _toggle_flag(self, flag_name: str) -> None:
        flags = self.settings.flags
        current = getattr(flags, flag_name)
        setattr(flags, flag_name, not current)
        self._refresh_debug_text()

    def _adjust_tuning(self, field_name: str, delta: float) -> None:
        tuning = self.settings.tuning
        current = getattr(tuning, field_name)
        setattr(tuning, field_name, current + delta)
        self._refresh_debug_text()

    def _reload_settings(self) -> None:
        self.settings = self._load_settings(self.settings_path)
        self._refresh_debug_text()

    def _set_key(self, key: str, pressed: bool) -> None:
        self._key_state[key] = pressed
        if key == "jump":
            self._wish_jump = pressed

    def _refresh_debug_text(self) -> None:
        tuning = self.settings.tuning
        flags = self.settings.flags
        self._debug_text.setText(
            "\n".join(
                [
                    "MVP Movement Tuning (F1 hide)",
                    f"Pos: {self.player.getPos()}",
                    f"Velocity: {self._velocity}",
                    f"Gravity: {tuning.gravity:.1f} ([ / ])",
                    f"Jump Speed: {tuning.jump_speed:.1f} (; / ')",
                    f"Move Speed: {tuning.move_speed:.1f} (, / .)",
                    f"Friction: {tuning.friction:.1f} (o / p)",
                    f"Flags: air={flags.enable_air_control} "
                    f"bhop={flags.enable_bunny_hop} friction={flags.enable_friction}",
                    "F2 air control | F3 bunny hop | F4 friction",
                    "F5 save JSON | F6 reload JSON",
                ]
            )
        )

    def _update_task(self, task):  # type: ignore[no-untyped-def]
        dt = globalClock.getDt()
        if dt > 0.2:
            dt = 0.2

        self._apply_movement(dt)
        self.cTrav.traverse(self.render)
        self._update_ground_state()
        self._update_camera()
        self._refresh_debug_text()

        return task.cont

    def _apply_movement(self, dt: float) -> None:
        tuning = self.settings.tuning
        flags = self.settings.flags

        move_dir = LVector3(0, 0, 0)
        if self._key_state["forward"]:
            move_dir.y += 1
        if self._key_state["back"]:
            move_dir.y -= 1
        if self._key_state["right"]:
            move_dir.x += 1
        if self._key_state["left"]:
            move_dir.x -= 1

        if move_dir.lengthSquared() > 0:
            move_dir.normalize()

        desired_speed = tuning.move_speed
        if flags.enable_sprint and self._key_state["sprint"]:
            desired_speed *= tuning.sprint_multiplier

        if self._is_grounded:
            if flags.enable_friction:
                self._apply_friction(dt, tuning.friction)
            self._accelerate(move_dir, desired_speed, tuning.ground_accel, dt)
        else:
            air_control = tuning.air_control if flags.enable_air_control else 0.0
            self._accelerate(move_dir, desired_speed * air_control, tuning.air_accel, dt)

        horizontal = LVector3(self._velocity.x, self._velocity.y, 0)
        if horizontal.length() > tuning.max_speed:
            horizontal.normalize()
            horizontal *= tuning.max_speed
            self._velocity.x = horizontal.x
            self._velocity.y = horizontal.y

        self._velocity.z += tuning.gravity * dt

        if self._is_grounded and self._wish_jump:
            self._velocity.z = tuning.jump_speed
            if not flags.enable_bunny_hop:
                self._wish_jump = False

        self.player.setPos(self.player.getPos() + self._velocity * dt)

    def _apply_friction(self, dt: float, friction: float) -> None:
        speed = (self._velocity.x ** 2 + self._velocity.y ** 2) ** 0.5
        if speed < 0.001:
            return
        drop = speed * friction * dt
        new_speed = max(speed - drop, 0)
        if new_speed != speed:
            scale = new_speed / speed
            self._velocity.x *= scale
            self._velocity.y *= scale

    def _accelerate(self, wish_dir: LVector3, wish_speed: float, accel: float, dt: float) -> None:
        if wish_dir.lengthSquared() == 0:
            return
        current_speed = self._velocity.dot(wish_dir)
        add_speed = wish_speed - current_speed
        if add_speed <= 0:
            return
        accel_speed = accel * dt * wish_speed
        if accel_speed > add_speed:
            accel_speed = add_speed
        self._velocity += wish_dir * accel_speed

    def _update_ground_state(self) -> None:
        self._ground_handler.sortEntries()
        grounded = False
        for entry in self._ground_handler.getEntries():
            if entry.getIntoNodePath() in {self._floor_np, self._platform_np}:
                hit_z = entry.getSurfacePoint(self.render).getZ()
                if self.player.getZ() - hit_z <= 0.6:
                    grounded = True
                break
        if grounded and self._velocity.z < 0:
            self._velocity.z = 0
        self._is_grounded = grounded

    def _update_camera(self) -> None:
        target = self.player.getPos()
        camera_pos = target + LVector3(0, -18, 8)
        self.camera.setPos(camera_pos)
        self.camera.lookAt(target + LVector3(0, 4, 1))

    def _smoke_task(self, task):  # type: ignore[no-untyped-def]
        self._frames_left -= 1
        if self._frames_left <= 0:
            self.userExit()
            return task.done
        return task.cont


def run(*, smoke: bool = False, settings_path: Path | None = None) -> None:
    config = RunConfig(smoke=smoke, settings_path=settings_path or Path("mvp_settings.json"))
    app = MVPApp(config)
    app.run()
