from __future__ import annotations

import math

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    ButtonHandle,
    KeyboardButton,
    LVector3f,
    WindowProperties,
    loadPrcFileData,
)

from ivan.app_config import RunConfig
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.ui.debug_ui import DebugUI
from ivan.world.scene import WorldScene


class RunnerDemo(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        loadPrcFileData("", "audio-library-name null")
        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.cfg = cfg
        self.tuning = PhysicsTuning()
        self.disableMouse()

        self._yaw = 0.0
        self._pitch = 0.0
        self._pointer_locked = True

        self.scene = WorldScene()
        self.scene.build(loader=self.loader, render=self.render, camera=self.camera)
        self._yaw = float(self.scene.spawn_yaw)

        self.player_node = self.render.attachNewNode("player-node")

        self.collision = CollisionWorld(
            aabbs=self.scene.aabbs,
            triangles=self.scene.triangles,
            triangle_collision_mode=self.scene.triangle_collision_mode,
            player_radius=float(self.tuning.player_radius),
            player_half_height=float(self.tuning.player_half_height),
            render=self.render,
        )

        self.player = PlayerController(
            tuning=self.tuning,
            spawn_point=self.scene.spawn_point,
            aabbs=self.scene.aabbs,
            collision=self.collision,
        )

        self.player_node.setPos(self.player.pos)

        self._setup_window()
        self._setup_input()
        self.ui = DebugUI(aspect2d=self.aspect2d, tuning=self.tuning, on_tuning_change=self._on_tuning_change)

        self.taskMgr.add(self._update, "runner-update")

        if cfg.smoke:
            self._smoke_frames = 10
            self.taskMgr.add(self._smoke_exit, "smoke-exit")

    def _setup_window(self) -> None:
        if self.cfg.smoke:
            return
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setTitle("IRUN IVAN Demo")
        props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        self.win.requestProperties(props)
        self.camLens.setFov(96)
        # Reduce near-plane clipping when hugging walls in first-person.
        self.camLens.setNearFar(0.03, 5000.0)
        self._center_mouse()

    def _setup_input(self) -> None:
        self.accept("escape", self._toggle_pointer_lock)
        self.accept("r", self._respawn)
        self.accept("space", self._queue_jump)
        self.accept("mouse1", self._grapple_mock)

    def _on_tuning_change(self, field: str) -> None:
        if field in ("player_radius", "player_half_height", "crouch_half_height"):
            self.player.apply_hull_settings()

    def _toggle_pointer_lock(self) -> None:
        self._pointer_locked = not self._pointer_locked
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        self.win.requestProperties(props)
        if self._pointer_locked:
            self.ui.hide()
        else:
            self.ui.show()
        if self._pointer_locked:
            self._center_mouse()

    def _center_mouse(self) -> None:
        if self.cfg.smoke:
            return
        x = self.win.getXSize() // 2
        y = self.win.getYSize() // 2
        self.win.movePointer(0, x, y)

    def _update_look(self) -> None:
        if self.cfg.smoke or not self._pointer_locked:
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        pointer = self.win.getPointer(0)
        dx = pointer.getX() - cx
        dy = pointer.getY() - cy

        self._yaw -= dx * float(self.tuning.mouse_sensitivity)
        self._pitch = max(-88.0, min(88.0, self._pitch - dy * float(self.tuning.mouse_sensitivity)))
        self._center_mouse()

    def _wish_direction(self) -> LVector3f:
        if self.mouseWatcherNode is None:
            return LVector3f(0, 0, 0)

        def down(*names: str) -> bool:
            for name in names:
                if len(name) == 1 and ord(name) < 128:
                    handle = KeyboardButton.ascii_key(name)
                else:
                    handle = ButtonHandle(name)
                if self.mouseWatcherNode.isButtonDown(handle):
                    return True
            return False

        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        right = LVector3f(forward.y, -forward.x, 0)

        move = LVector3f(0, 0, 0)
        # Support non-US keyboard layouts by checking Cyrillic equivalents of WASD (RU):
        # W/A/S/D -> Ц/Ф/Ы/В. Arrow keys are also supported as a fallback.
        if down("w", "ц") or self.mouseWatcherNode.isButtonDown(KeyboardButton.up()):
            move += forward
        if down("s", "ы") or self.mouseWatcherNode.isButtonDown(KeyboardButton.down()):
            move -= forward
        if down("d", "в") or self.mouseWatcherNode.isButtonDown(KeyboardButton.right()):
            move += right
        if down("a", "ф") or self.mouseWatcherNode.isButtonDown(KeyboardButton.left()):
            move -= right

        if move.lengthSquared() > 0:
            move.normalize()
        return move

    def _queue_jump(self) -> None:
        self.player.queue_jump()

    def _grapple_mock(self) -> None:
        self.player.apply_grapple_impulse(yaw_deg=self._yaw)

    def _respawn(self) -> None:
        self.player.respawn()
        self._yaw = 0.0
        self._pitch = 0.0
        self.player_node.setPos(self.player.pos)

    def _update(self, task: Task) -> int:
        dt = min(globalClock.getDt(), 1.0 / 30.0)

        self._update_look()

        wish = self._wish_direction()
        self.player.step(dt=dt, wish_dir=wish, yaw_deg=self._yaw, crouching=self._is_crouching())

        if self.player.pos.z < -18:
            self._respawn()

        self.player_node.setPos(self.player.pos)
        eye_height = float(self.tuning.player_eye_height)
        if self.player.crouched and bool(self.tuning.crouch_enabled):
            eye_height = min(eye_height, float(self.tuning.crouch_eye_height))
        self.camera.setPos(
            self.player.pos.x,
            self.player.pos.y,
            self.player.pos.z + eye_height,
        )
        self.camera.setHpr(self._yaw, self._pitch, 0)

        hspeed = math.sqrt(self.player.vel.x * self.player.vel.x + self.player.vel.y * self.player.vel.y)
        self.ui.set_speed(hspeed)
        self.ui.set_status(
            f"speed: {hspeed:.2f} | z-vel: {self.player.vel.z:.2f} | grounded: {self.player.grounded} | "
            f"wall: {self.player.has_wall_for_jump()}"
        )

        return Task.cont

    def _is_crouching(self) -> bool:
        if self.mouseWatcherNode is None:
            return False
        return self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("c"))

    def _smoke_exit(self, task: Task) -> int:
        self._smoke_frames -= 1
        if self._smoke_frames <= 0:
            self.userExit()
            return Task.done
        return Task.cont


def run(*, smoke: bool = False) -> None:
    app = RunnerDemo(RunConfig(smoke=smoke))
    app.run()
