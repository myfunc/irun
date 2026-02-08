from __future__ import annotations

import json
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task
from panda3d.core import Filename, LVector3f, PNMImage, WindowProperties, loadPrcFileData

from baker.app_config import BakerRunConfig
from baker.controls.fly_camera import FlyCameraController
from baker.monorepo_paths import ensure_ivan_importable
from baker.render.tonemapping import TonemapPass
from baker.runtime_log import RuntimeLog
from baker.ui.hud import ViewerHUD
from baker.ui.layout import EditorLayout

# Imported from Ivan for WYSIWYG rendering and bundle loading.
ensure_ivan_importable()
from ivan.maps.bundle_io import resolve_bundle_handle
from ivan.world.scene import WorldScene


class BakerViewer(ShowBase):
    def __init__(self, cfg: BakerRunConfig) -> None:
        # Keep renderer behavior aligned with Ivan.
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "textures-power-2 none")
        loadPrcFileData("", "textures-square none")
        loadPrcFileData("", "textures-auto-power-2 0")
        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.log = RuntimeLog()
        self.log.log("Baker start")

        self.cfg = cfg
        self.disableMouse()

        self._setup_window()
        self.log.log("Window setup complete")

        handle = resolve_bundle_handle(cfg.map_json)
        if handle is None:
            raise SystemExit(f"Could not resolve --map: {cfg.map_json}")
        self.log.log(f"Resolved map: {cfg.map_json} -> {handle.map_json}")

        # WorldScene expects a config-like object with `map_json` and optional lighting/visibility settings.
        scene_cfg = type(
            "BakerSceneCfg",
            (),
            {
                "map_json": str(handle.map_json),
                "lighting": {"preset": "original"},
                "visibility": {"enabled": True, "mode": "auto", "build_cache": True},
            },
        )()

        self.scene = WorldScene()
        self.world_root = self.render.attachNewNode("world-root")
        self.scene.build(cfg=scene_cfg, loader=self.loader, render=self.world_root, camera=self.camera)
        self.log.log("Scene build complete")

        # Minimal editor-like chrome: left/right panels (placeholders for catalog/inspector).
        self.layout = EditorLayout(aspect2d=self.aspect2d)

        self.hud = ViewerHUD(aspect2d=self.aspect2d)
        self.hud.set_map_label(str(getattr(self.scene, "map_id", "")) or "(unknown)")
        self.hud.set_log_tail("")

        # Initialize camera pose near the spawn.
        try:
            self.camera.setPos(self.scene.spawn_point)
            self.camera.setHpr(self.scene.spawn_yaw, 0.0, 0.0)
        except Exception:
            pass
        if cfg.smoke:
            self._apply_smoke_camera_pose(map_json_path=Path(handle.map_json))

        self.tonemap = TonemapPass(base=self)
        self.tonemap.attach()
        self.hud.set_tonemap_label("gamma-only")

        self.fly = FlyCameraController(
            base=self,
            camera_np=self.camera,
            initial_yaw_deg=float(getattr(self.scene, "spawn_yaw", 0.0) or 0.0),
            initial_pitch_deg=0.0,
            move_speed=10.0,
            fast_multiplier=4.0,
            mouse_sensitivity=0.12,
            on_pointer_lock_changed=self._on_pointer_lock_changed,
            on_input_debug=self._on_input_debug,
        )
        self.hud.set_pointer_lock_label("locked" if self.fly.is_pointer_locked() else "unlocked")

        self.accept("1", self._set_tonemap, [1])
        self.accept("2", self._set_tonemap, [2])
        self.accept("3", self._set_tonemap, [3])
        self.accept("f", self._focus_scene)
        self.accept("f2", self._toggle_log_tail)
        self._log_tail_enabled = False

        self.taskMgr.add(self._tick_scene_task, "baker.scene_tick")
        self.taskMgr.add(self._input_probe_task, "baker.input_probe")

        # Try to enable keystroke events so we can see what Panda3D is actually receiving.
        self._setup_keystroke_debug()

        self._smoke_frames = 6
        if cfg.smoke:
            self.taskMgr.add(self._smoke_exit, "baker.smoke_exit")

    def _setup_window(self) -> None:
        if self.win is None:
            return
        if not hasattr(self.win, "requestProperties"):
            # Offscreen (smoke) runs can create a GraphicsBuffer instead of a window.
            return
        props = WindowProperties()
        props.setTitle("IRUN Baker (mapperoni)")
        # Match Ivan: open at display size by default (user can resize afterwards).
        try:
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        except Exception:
            pass
        self.win.requestProperties(props)
        # Wider FOV than the Panda3D default; closer to typical FPS/editor navigation.
        try:
            self.camLens.setFov(110)
            self.camLens.setNearFar(0.03, 5000.0)
        except Exception:
            pass

    def _set_tonemap(self, mode: int) -> None:
        self.tonemap.set_mode(int(mode))
        if mode == 1:
            self.hud.set_tonemap_label("gamma-only")
        elif mode == 2:
            self.hud.set_tonemap_label("Reinhard")
        elif mode == 3:
            self.hud.set_tonemap_label("ACES approx")

    def _on_pointer_lock_changed(self, locked: bool) -> None:
        self.hud.set_pointer_lock_label("locked" if locked else "unlocked")

    def _on_input_debug(self, text: str) -> None:
        self.hud.set_input_debug(text)
        if text:
            self.log.log(f"HUD: {text}")

    def _toggle_log_tail(self) -> None:
        self._log_tail_enabled = not bool(self._log_tail_enabled)
        if not self._log_tail_enabled:
            self.hud.set_log_tail("")

    def _setup_keystroke_debug(self) -> None:
        try:
            if hasattr(self, "buttonThrowers") and self.buttonThrowers:
                self.buttonThrowers[0].node().setKeystrokeEvent("keystroke")
            self.accept("keystroke", self._on_keystroke)
            self.log.log("Keystroke debug enabled (event=keystroke)")
        except Exception:
            self.log.log("Keystroke debug setup failed")
            self.log.log_exc("keystroke.setup")

    def _on_keystroke(self, key: str) -> None:
        # Log a small sample so we can tell what the platform is sending (e.g. non-ASCII).
        try:
            self.log.log(f"keystroke={repr(key)}")
        except Exception:
            pass

    def _input_probe_task(self, task: Task) -> int:
        # Periodic probe: tells us whether Panda3D thinks we have a keyboard/mouse watcher.
        try:
            if getattr(task, "_next_probe", None) is None:
                task._next_probe = 0.0
            now = float(globalClock.getFrameTime())
            if now < float(task._next_probe):
                return Task.cont
            task._next_probe = now + 0.5

            mw = getattr(self, "mouseWatcherNode", None)
            if mw is None:
                self.log.log("probe: mouseWatcherNode=None")
                return Task.cont

            has_mouse = bool(mw.hasMouse())
            x = float(mw.getMouseX()) if has_mouse else 0.0
            y = float(mw.getMouseY()) if has_mouse else 0.0
            self.log.log(f"probe: hasMouse={has_mouse} mouse=({x:.3f},{y:.3f})")
            return Task.cont
        except Exception:
            self.log.log_exc("probe")
            return Task.cont

    def _focus_scene(self) -> None:
        # Quick escape hatch if we spawn inside geometry: move above spawn and look at it.
        try:
            sp = LVector3f(self.scene.spawn_point)
            self.camera.setPos(sp + LVector3f(0.0, -18.0, 10.0))
            self.camera.lookAt(sp)
        except Exception:
            return

    def _apply_smoke_camera_pose(self, *, map_json_path: Path) -> None:
        """Move the camera away from the normal spawn so smoke screenshots show more context."""

        try:
            payload = json.loads(map_json_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

        bounds = payload.get("bounds") if isinstance(payload, dict) else None
        bmin = bounds.get("min") if isinstance(bounds, dict) else None
        bmax = bounds.get("max") if isinstance(bounds, dict) else None

        if isinstance(bmin, list) and isinstance(bmax, list) and len(bmin) == 3 and len(bmax) == 3:
            try:
                mn = LVector3f(float(bmin[0]), float(bmin[1]), float(bmin[2]))
                mx = LVector3f(float(bmax[0]), float(bmax[1]), float(bmax[2]))
                center = (mn + mx) * 0.5
                ext = (mx - mn)
                dist = max(float(ext.x), float(ext.y)) * 0.6 + 10.0
                pos = center + LVector3f(0.0, -dist, max(5.0, float(ext.z) * 0.18 + 5.0))
                self.camera.setPos(pos)
                self.camera.lookAt(center)
                return
            except Exception:
                pass

        # Fallback: offset from spawn.
        try:
            sp = LVector3f(self.scene.spawn_point)
            pos = sp + LVector3f(0.0, -35.0, 12.0)
            self.camera.setPos(pos)
            self.camera.lookAt(sp)
        except Exception:
            return

    def _tick_scene_task(self, task: Task) -> int:
        try:
            now = float(globalClock.getFrameTime())
            self.scene.tick(now=now)
            return Task.cont
        except Exception:
            self.log.log_exc("scene.tick")
            return Task.cont

    def _smoke_exit(self, task: Task) -> int:
        self._smoke_frames -= 1
        if self._smoke_frames <= 0:
            self._write_smoke_screenshot()
            self.userExit()
            return Task.done
        return Task.cont

    def _write_smoke_screenshot(self) -> None:
        if not self.cfg.smoke or not self.cfg.smoke_screenshot:
            return
        if self.win is None:
            return
        out = Path(self.cfg.smoke_screenshot).expanduser()
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        try:
            self.graphicsEngine.renderFrame()
            img: PNMImage | None = None
            try:
                img = self.win.getScreenshot()
            except Exception:
                tmp = PNMImage()
                ok = self.win.getScreenshot(tmp)
                img = tmp if ok else None
            if img is None:
                return
            img.write(Filename.fromOsSpecific(str(out)))
        except Exception:
            return


def run(cfg: BakerRunConfig) -> None:
    app = BakerViewer(cfg)
    app.run()
