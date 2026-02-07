from __future__ import annotations

from dataclasses import dataclass

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    LVector3,
    LVector4,
    loadPrcFileData,
)


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False


class MVPApp(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        # Keep audio from being a dependency for early smoke runs / CI.
        loadPrcFileData("", "audio-library-name null")

        if cfg.smoke:
            # Avoid flashing a window in quick verification runs.
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.disableMouse()
        self._setup_scene()

        if cfg.smoke:
            # Run a handful of frames then exit.
            self._frames_left = 8
            self.taskMgr.add(self._smoke_task, "smoke-exit")

    def _setup_scene(self) -> None:
        # Built-in Panda3D sample environment model.
        env = self.loader.loadModel("models/environment")
        env.reparentTo(self.render)
        env.setScale(0.25)
        env.setPos(-8, 42, 0)

        # Simple primitive in front of the camera.
        smiley = self.loader.loadModel("models/smiley")
        smiley.reparentTo(self.render)
        smiley.setScale(0.8)
        smiley.setPos(0, 10, 1.2)

        # Camera.
        self.camera.setPos(0, -18, 6)
        self.camera.lookAt(0, 10, 1.0)

        # Lighting.
        ambient = AmbientLight("ambient")
        ambient.setColor(LVector4(0.25, 0.25, 0.25, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LVector4(0.9, 0.9, 0.9, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.render.setLight(sun_np)

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

