from __future__ import annotations

import math
import subprocess
import sys
import threading
from pathlib import Path

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
from ivan.paths import app_root as ivan_app_root
from ivan.ui.debug_ui import DebugUI
from ivan.ui.input_debug_ui import InputDebugUI
from ivan.ui.map_select_ui import MapEntry, MapSelectUI
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
        self._mode: str = "boot"  # boot | menu | game
        self._last_mouse: tuple[float, float] | None = None
        self._input_debug_until: float = 0.0

        self.scene: WorldScene | None = None
        self.collision: CollisionWorld | None = None
        self.player: PlayerController | None = None
        self.player_node = self.render.attachNewNode("player-node")
        self.world_root = self.render.attachNewNode("world-root")

        self._map_menu: MapSelectUI | None = None
        self._import_thread: threading.Thread | None = None
        self._importing: bool = False
        self._import_error: str | None = None
        self._pending_map_json: str | None = None

        self._setup_window()
        self.ui = DebugUI(aspect2d=self.aspect2d, tuning=self.tuning, on_tuning_change=self._on_tuning_change)
        self.input_debug = InputDebugUI(aspect2d=self.aspect2d)
        self._setup_input()

        if self.cfg.hl_root and not self.cfg.map_json and not self.cfg.smoke:
            self._enter_map_picker()
        else:
            self._start_game(map_json=self.cfg.map_json)

        self.taskMgr.add(self._update, "runner-update")

        if cfg.smoke:
            self._smoke_frames = 10
            self.taskMgr.add(self._smoke_exit, "smoke-exit")

    def _setup_window(self) -> None:
        if self.cfg.smoke:
            return
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        props.setMouseMode(WindowProperties.M_relative if self._pointer_locked else WindowProperties.M_absolute)
        props.setTitle("IRUN IVAN Demo")
        props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        self.win.requestProperties(props)
        self.camLens.setFov(96)
        # Reduce near-plane clipping when hugging walls in first-person.
        self.camLens.setNearFar(0.03, 5000.0)
        if self._pointer_locked:
            self._center_mouse()

    def _setup_input(self) -> None:
        self.accept("escape", self._on_escape)
        self.accept("r", self._respawn)
        self.accept("space", self._queue_jump)
        self.accept("mouse1", self._grapple_mock)
        self.accept("f2", self.input_debug.toggle)
        self.accept("arrow_up", self._menu_up)
        self.accept("arrow_down", self._menu_down)
        self.accept("enter", self._menu_select)
        self.accept("w", self._menu_up)
        self.accept("s", self._menu_down)

    def _on_tuning_change(self, field: str) -> None:
        if field in ("player_radius", "player_half_height", "crouch_half_height"):
            if self.player is not None:
                self.player.apply_hull_settings()

    def _toggle_pointer_lock(self) -> None:
        self._pointer_locked = not self._pointer_locked
        self._last_mouse = None
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        props.setMouseMode(WindowProperties.M_relative if self._pointer_locked else WindowProperties.M_absolute)
        self.win.requestProperties(props)
        if self._mode == "game":
            if self._pointer_locked:
                self.ui.hide()
            else:
                self.ui.show()
        if self._pointer_locked:
            self._center_mouse()

    def _on_escape(self) -> None:
        if self._mode == "menu":
            self.userExit()
            return
        self._toggle_pointer_lock()

    def _enter_map_picker(self) -> None:
        self._mode = "menu"
        self._pointer_locked = False
        self._last_mouse = None
        props = WindowProperties()
        props.setCursorHidden(False)
        props.setMouseMode(WindowProperties.M_absolute)
        self.win.requestProperties(props)

        # Hide in-game HUD while picking.
        self.ui.speed_hud_label.hide()
        self.ui.hide()

        entries = self._list_hl_maps()
        title = f"Select map to import/run ({self.cfg.hl_mod})"
        self._map_menu = MapSelectUI(aspect2d=self.aspect2d, title=title)
        self._map_menu.set_entries(entries)

        if not entries:
            self._map_menu.set_status("No .bsp maps found.")
            return

        # Make Crossfire easy to find.
        for i, e in enumerate(entries):
            if e.label.lower() == "crossfire":
                self._map_menu.move(i)
                break

    def _list_hl_maps(self) -> list[MapEntry]:
        if not self.cfg.hl_root:
            return []
        maps_dir = Path(self.cfg.hl_root) / self.cfg.hl_mod / "maps"
        if not maps_dir.exists():
            return []
        out: list[MapEntry] = []
        for p in sorted(maps_dir.glob("*.bsp")):
            out.append(MapEntry(label=p.stem, bsp_path=str(p)))
        return out

    def _menu_up(self) -> None:
        if self._mode == "menu" and self._map_menu is not None and not self._importing:
            self._map_menu.move(-1)

    def _menu_down(self) -> None:
        if self._mode == "menu" and self._map_menu is not None and not self._importing:
            self._map_menu.move(1)

    def _menu_select(self) -> None:
        if self._mode != "menu" or self._map_menu is None or self._importing:
            return
        entry = self._map_menu.selected()
        if entry is None:
            return
        self._start_import_goldsrc_map(entry)

    def _start_import_goldsrc_map(self, entry: MapEntry) -> None:
        assert self.cfg.hl_root is not None
        app_root = ivan_app_root()
        out_dir = app_root / "assets" / "imported" / "halflife" / self.cfg.hl_mod / entry.label
        game_root = Path(self.cfg.hl_root) / self.cfg.hl_mod

        script = app_root / "tools" / "importers" / "goldsrc" / "import_goldsrc_bsp.py"
        venv_py = app_root / ".venv" / "bin" / "python"
        python_exe = str(venv_py) if venv_py.exists() else sys.executable
        cmd = [
            python_exe,
            str(script),
            "--bsp",
            entry.bsp_path,
            "--game-root",
            str(game_root),
            "--out",
            str(out_dir),
            "--map-id",
            entry.label,
            "--scale",
            "0.03",
        ]

        self._importing = True
        self._import_error = None
        self._pending_map_json = None
        self._map_menu.set_status(f"Importing {entry.label} ...")

        def worker() -> None:
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    err = (proc.stderr or proc.stdout or "").strip()
                    # Prefer the last non-empty line (usually the exception), but keep a short tail for context.
                    if err:
                        lines = [l for l in err.splitlines() if l.strip()]
                        tail = "\n".join(lines[-6:]) if lines else err
                        self._import_error = tail[-800:]
                    else:
                        self._import_error = f"Importer failed with code {proc.returncode}"
                    return
                self._pending_map_json = str(out_dir / "map.json")
            except Exception as e:
                self._import_error = str(e)
            finally:
                self._importing = False

        self._import_thread = threading.Thread(target=worker, daemon=True)
        self._import_thread.start()

    def _start_game(self, map_json: str | None) -> None:
        # Tear down menu.
        if self._map_menu is not None:
            self._map_menu.destroy()
            self._map_menu = None

        self._mode = "game"
        self._pointer_locked = True
        self._last_mouse = None
        if not self.cfg.smoke:
            props = WindowProperties()
            props.setCursorHidden(True)
            props.setMouseMode(WindowProperties.M_relative)
            self.win.requestProperties(props)
        self.ui.speed_hud_label.show()
        self.ui.hide()
        if not self.cfg.smoke:
            self._center_mouse()
            # Show input debug briefly after loading a map (useful when mouse/keyboard seem dead).
            self._input_debug_until = globalClock.getFrameTime() + 8.0
            self.input_debug.show()

        # Reset world root to allow reloading.
        self.world_root.removeNode()
        self.world_root = self.render.attachNewNode("world-root")

        cfg = RunConfig(smoke=self.cfg.smoke, map_json=map_json, hl_root=self.cfg.hl_root, hl_mod=self.cfg.hl_mod)
        self.scene = WorldScene()
        self.scene.build(cfg=cfg, loader=self.loader, render=self.world_root, camera=self.camera)
        self._yaw = float(self.scene.spawn_yaw)

        self.collision = CollisionWorld(
            aabbs=self.scene.aabbs,
            triangles=self.scene.triangles,
            triangle_collision_mode=self.scene.triangle_collision_mode,
            player_radius=float(self.tuning.player_radius),
            player_half_height=float(self.tuning.player_half_height),
            render=self.world_root,
        )

        self.player = PlayerController(
            tuning=self.tuning,
            spawn_point=self.scene.spawn_point,
            aabbs=self.scene.aabbs,
            collision=self.collision,
        )
        self.player_node.setPos(self.player.pos)

    def _center_mouse(self) -> None:
        if self.cfg.smoke:
            return
        x = self.win.getXSize() // 2
        y = self.win.getYSize() // 2
        self.win.movePointer(0, x, y)

    def _update_look(self) -> None:
        if self.cfg.smoke or not self._pointer_locked:
            return

        # Primary path: normalized mouse coords (works well with relative mouse mode).
        if self.mouseWatcherNode is not None and self.mouseWatcherNode.hasMouse():
            mx = float(self.mouseWatcherNode.getMouseX())
            my = float(self.mouseWatcherNode.getMouseY())
            if self._last_mouse is None:
                self._last_mouse = (mx, my)
                return
            lmx, lmy = self._last_mouse
            self._last_mouse = (mx, my)

            dx_norm = mx - lmx
            # Keep non-inverted vertical look (mouse up -> look up).
            dy_norm = lmy - my
            dx = dx_norm * (self.win.getXSize() * 0.5)
            dy = dy_norm * (self.win.getYSize() * 0.5)

            self._yaw -= dx * float(self.tuning.mouse_sensitivity)
            self._pitch = max(-88.0, min(88.0, self._pitch - dy * float(self.tuning.mouse_sensitivity)))
            return

        # Fallback: pointer delta vs screen center (useful if hasMouse() stays false on some macOS setups).
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        pointer = self.win.getPointer(0)
        dx = float(pointer.getX() - cx)
        dy = float(pointer.getY() - cy)

        if dx == 0.0 and dy == 0.0:
            return
        self._yaw -= dx * float(self.tuning.mouse_sensitivity)
        self._pitch = max(-88.0, min(88.0, self._pitch - dy * float(self.tuning.mouse_sensitivity)))
        self._center_mouse()

    def _wish_direction(self) -> LVector3f:
        if self.mouseWatcherNode is None:
            return LVector3f(0, 0, 0)

        def down(*names: str) -> bool:
            for name in names:
                n = name.lower()
                if len(n) == 1 and ord(n) < 128:
                    # ASCII key (layout-dependent) + raw key (layout-independent).
                    if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key(n)):
                        return True
                    if self.mouseWatcherNode.isButtonDown(ButtonHandle(f"raw-{n}")):
                        return True
                    continue
                if self.mouseWatcherNode.isButtonDown(ButtonHandle(n)):
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
        if self.player is not None:
            self.player.queue_jump()

    def _grapple_mock(self) -> None:
        if self.player is not None:
            self.player.apply_grapple_impulse(yaw_deg=self._yaw)

    def _respawn(self) -> None:
        if self.player is None or self.scene is None:
            return
        self.player.respawn()
        self._yaw = float(self.scene.spawn_yaw)
        self._pitch = 0.0
        self.player_node.setPos(self.player.pos)

    def _update(self, task: Task) -> int:
        if self._mode == "menu":
            if self._import_error and self._map_menu is not None:
                self._map_menu.set_status(f"Import failed: {self._import_error}")
                self._import_error = None
            if self._pending_map_json:
                self._start_game(map_json=self._pending_map_json)
                self._pending_map_json = None
            return Task.cont
        if self._mode != "game" or self.player is None:
            return Task.cont

        dt = min(globalClock.getDt(), 1.0 / 30.0)

        # Precompute wish so debug overlay can show it even if movement seems dead.
        wish = self._wish_direction()

        if self.mouseWatcherNode is not None:
            has_mouse = self.mouseWatcherNode.hasMouse()
            mx = float(self.mouseWatcherNode.getMouseX()) if has_mouse else 0.0
            my = float(self.mouseWatcherNode.getMouseY()) if has_mouse else 0.0
            raw_w = self.mouseWatcherNode.isButtonDown(ButtonHandle("raw-w"))
            raw_a = self.mouseWatcherNode.isButtonDown(ButtonHandle("raw-a"))
            raw_s = self.mouseWatcherNode.isButtonDown(ButtonHandle("raw-s"))
            raw_d = self.mouseWatcherNode.isButtonDown(ButtonHandle("raw-d"))
            asc_w = self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("w"))
            asc_a = self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("a"))
            asc_s = self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("s"))
            asc_d = self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key("d"))
            pos = self.player.pos if self.player is not None else LVector3f(0, 0, 0)
            vel = self.player.vel if self.player is not None else LVector3f(0, 0, 0)
            grounded = bool(self.player.grounded) if self.player is not None else False
            self.input_debug.set_text(
                "input debug (F2)\n"
                f"mode={self._mode} lock={self._pointer_locked} dt={dt:.3f} hasMouse={has_mouse} mouse=({mx:+.2f},{my:+.2f})\n"
                f"raw WASD={int(raw_w)}{int(raw_a)}{int(raw_s)}{int(raw_d)} ascii WASD={int(asc_w)}{int(asc_a)}{int(asc_s)}{int(asc_d)}\n"
                f"wish=({wish.x:+.2f},{wish.y:+.2f}) pos=({pos.x:+.2f},{pos.y:+.2f},{pos.z:+.2f}) vel=({vel.x:+.2f},{vel.y:+.2f},{vel.z:+.2f}) grounded={int(grounded)}"
            )
        if self._input_debug_until and globalClock.getFrameTime() >= self._input_debug_until:
            self._input_debug_until = 0.0
            self.input_debug.hide()

        self._update_look()

        self.player.step(dt=dt, wish_dir=wish, yaw_deg=self._yaw, crouching=self._is_crouching())

        if self.scene is not None and self.player.pos.z < float(self.scene.kill_z):
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


def run(*, smoke: bool = False, map_json: str | None = None, hl_root: str | None = None, hl_mod: str = "valve") -> None:
    app = RunnerDemo(RunConfig(smoke=smoke, map_json=map_json, hl_root=hl_root, hl_mod=hl_mod))
    app.run()
