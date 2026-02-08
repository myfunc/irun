from __future__ import annotations

import math
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    ButtonHandle,
    Filename,
    KeyboardButton,
    LVector3f,
    PNMImage,
    WindowProperties,
    loadPrcFileData,
)

from ivan.app_config import RunConfig
from ivan.common.error_log import ErrorLog
from ivan.maps.run_metadata import RunMetadata, load_run_metadata
from ivan.modes.base import ModeContext
from ivan.modes.loader import load_mode
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.paths import app_root as ivan_app_root
from ivan.state import load_state, resolve_map_json, update_state
from ivan.ui.debug_ui import DebugUI
from ivan.ui.error_console_ui import ErrorConsoleUI
from ivan.ui.input_debug_ui import InputDebugUI
from ivan.ui.main_menu import ImportRequest, MainMenuController
from ivan.ui.pause_menu_ui import PauseMenuUI
from ivan.world.scene import WorldScene


class RunnerDemo(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        loadPrcFileData("", "audio-library-name null")
        # GoldSrc and some Source assets include many non-power-of-two (NPOT) textures.
        # Panda3D can rescale these to the nearest power-of-two by default, which breaks
        # BSP UV mapping (textures look skewed/flipped). Disable that behavior.
        loadPrcFileData("", "textures-power-2 none")
        loadPrcFileData("", "textures-square none")
        loadPrcFileData("", "textures-auto-power-2 0")
        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.cfg = cfg
        self.tuning = PhysicsTuning()
        self._loaded_state = load_state()
        self._apply_persisted_tuning(self._loaded_state.tuning_overrides)
        self.disableMouse()

        self._yaw = 0.0
        self._pitch = 0.0
        self._pointer_locked = True
        self._pause_menu_open = False
        self._debug_menu_open = False
        self._mode: str = "boot"  # boot | menu | game
        self._last_mouse: tuple[float, float] | None = None
        self._input_debug_until: float = 0.0
        self._noclip_toggle_key: str = "v"
        self._noclip_toggle_prev_down: bool = False
        self._awaiting_noclip_rebind: bool = False

        self.scene: WorldScene | None = None
        self.collision: CollisionWorld | None = None
        self.player: PlayerController | None = None
        self.player_node = self.render.attachNewNode("player-node")
        self.world_root = self.render.attachNewNode("world-root")
        self._game_mode: Any | None = None
        self._game_mode_ctx: ModeContext | None = None
        self._game_mode_events: list[str] = []

        self._menu: MainMenuController | None = None
        self._import_thread: threading.Thread | None = None
        self._importing: bool = False
        self._import_error: str | None = None
        self._pending_map_json: str | None = None
        self._menu_hold_dir: int = 0
        self._menu_hold_since: float = 0.0
        self._menu_hold_next: float = 0.0

        self.error_log = ErrorLog(max_items=30)

        self._setup_window()
        self.ui = DebugUI(aspect2d=self.aspect2d, tuning=self.tuning, on_tuning_change=self._on_tuning_change)
        self.error_console = ErrorConsoleUI(aspect2d=self.aspect2d, error_log=self.error_log)
        self.pause_ui = PauseMenuUI(
            aspect2d=self.aspect2d,
            on_resume=self._close_all_game_menus,
            on_map_selector=self._back_to_menu,
            on_back_to_menu=self._back_to_menu,
            on_quit=self.userExit,
            on_open_keybindings=self._open_keybindings_menu,
            on_rebind_noclip=self._start_rebind_noclip,
        )
        self.pause_ui.set_noclip_binding(self._noclip_toggle_key)
        self.input_debug = InputDebugUI(aspect2d=self.aspect2d)
        self._setup_input()

        # Boot behavior:
        # - --map: run immediately (useful for fast iteration)
        # - smoke: keep existing fast boot path (offscreen)
        # - otherwise: start in the main menu (can still Quick Start a bundled map)
        if self.cfg.map_json or self.cfg.smoke:
            self._start_game(map_json=self.cfg.map_json)
        else:
            self._enter_main_menu()

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
        self.accept("escape", lambda: self._safe_call("input.escape", self._on_escape))
        self.accept("`", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("ascii`", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("grave", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("r", lambda: self._safe_call("input.respawn", lambda: self._do_respawn(from_mode=False)))
        self.accept("space", lambda: self._safe_call("input.jump", self._queue_jump))
        self.accept("mouse1", lambda: self._safe_call("input.grapple", self._grapple_mock))
        self.accept("f2", self.input_debug.toggle)
        self.accept("f3", self.error_console.toggle)
        self.accept("shift-f3", lambda: self._safe_call("errors.clear", self._clear_errors))
        self.accept("arrow_up", lambda: self._menu_nav_press(-1))
        self.accept("arrow_down", lambda: self._menu_nav_press(1))
        self.accept("arrow_up-up", lambda: self._menu_nav_release(-1))
        self.accept("arrow_down-up", lambda: self._menu_nav_release(1))
        self.accept("arrow_left", lambda: self._menu_page(-1))
        self.accept("arrow_right", lambda: self._menu_page(1))
        self.accept("enter", self._menu_select)
        self.accept("w", lambda: self._menu_nav_press(-1))
        self.accept("s", lambda: self._menu_nav_press(1))
        self.accept("w-up", lambda: self._menu_nav_release(-1))
        self.accept("s-up", lambda: self._menu_nav_release(1))
        self.accept("control-f", lambda: self._safe_call("menu.search", self._menu_toggle_search))
        self.accept("meta-f", lambda: self._safe_call("menu.search", self._menu_toggle_search))
        if hasattr(self, "buttonThrowers") and self.buttonThrowers:
            try:
                self.buttonThrowers[0].node().setKeystrokeEvent("keystroke")
            except Exception:
                pass
        self.accept("keystroke", lambda key: self._safe_call("input.keystroke", lambda: self._on_keystroke(key)))

    def _on_tuning_change(self, field: str) -> None:
        if field in ("player_radius", "player_half_height", "crouch_half_height"):
            if self.player is not None:
                self.player.apply_hull_settings()
        self._persist_tuning_field(field)

    def _apply_persisted_tuning(self, overrides: dict[str, float | bool]) -> None:
        fields = set(PhysicsTuning.__annotations__.keys())
        for field, value in overrides.items():
            if field not in fields:
                continue
            setattr(self.tuning, field, value)

    def _persist_tuning_field(self, field: str) -> None:
        if field not in PhysicsTuning.__annotations__:
            return
        value = getattr(self.tuning, field)
        persisted_value: float | bool
        if isinstance(value, bool):
            persisted_value = value
        else:
            persisted_value = float(value)
        update_state(tuning_overrides={field: persisted_value})

    def _set_pointer_lock(self, locked: bool) -> None:
        self._pointer_locked = bool(locked)
        self._last_mouse = None
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        props.setMouseMode(WindowProperties.M_relative if self._pointer_locked else WindowProperties.M_absolute)
        self.win.requestProperties(props)
        if self._pointer_locked:
            self._center_mouse()

    def _close_all_game_menus(self) -> None:
        if self._mode != "game":
            return
        self._pause_menu_open = False
        self._debug_menu_open = False
        self._awaiting_noclip_rebind = False
        self.pause_ui.hide()
        self.ui.hide()
        self._set_pointer_lock(True)

    def _open_pause_menu(self) -> None:
        if self._mode != "game":
            return
        self._pause_menu_open = True
        self._debug_menu_open = False
        self._awaiting_noclip_rebind = False
        self.pause_ui.show_main()
        self.pause_ui.set_keybind_status("")
        self.pause_ui.show()
        self.ui.hide()
        self._set_pointer_lock(False)

    def _toggle_debug_menu(self) -> None:
        if self._mode != "game":
            return
        self._debug_menu_open = not self._debug_menu_open
        if self._debug_menu_open:
            self._pause_menu_open = False
            self.pause_ui.hide()
            self.ui.show()
            self._set_pointer_lock(False)
            return
        self.ui.hide()
        if self._pause_menu_open:
            self.pause_ui.show()
            self._set_pointer_lock(False)
        else:
            self._set_pointer_lock(True)

    def _on_escape(self) -> None:
        if self._mode == "menu":
            if self._importing:
                return
            if self._menu is not None:
                self._safe_call("menu.escape", self._menu.on_escape)
                return
        if self._mode != "game":
            return
        if self._debug_menu_open or self._pause_menu_open:
            self._close_all_game_menus()
            return
        self._open_pause_menu()

    def _open_keybindings_menu(self) -> None:
        if self._mode != "game":
            return
        self.pause_ui.show_keybindings()
        self.pause_ui.set_noclip_binding(self._noclip_toggle_key)
        self.pause_ui.set_keybind_status("")

    def _start_rebind_noclip(self) -> None:
        if self._mode != "game":
            return
        self._awaiting_noclip_rebind = True
        self.pause_ui.set_keybind_status("Press a key to assign noclip toggle.")

    def _on_keystroke(self, key: str) -> None:
        if not self._awaiting_noclip_rebind:
            return
        key_name = self._normalize_bind_key(key)
        if not key_name:
            return
        self._noclip_toggle_key = key_name
        self._awaiting_noclip_rebind = False
        self.pause_ui.set_noclip_binding(self._noclip_toggle_key)
        self.pause_ui.set_keybind_status(f"Noclip key set to {self._noclip_toggle_key.upper()}.")

    @staticmethod
    def _normalize_bind_key(key: str) -> str | None:
        k = (key or "").strip().lower()
        if not k:
            return None
        aliases = {
            "space": "space",
            "spacebar": "space",
            "grave": "`",
            "backquote": "`",
            "backtick": "`",
        }
        if k in aliases:
            return aliases[k]
        if len(k) == 1 and ord(k) < 128:
            return k
        if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
            return k
        return None

    def _enter_main_menu(self) -> None:
        self._mode = "menu"
        self._menu_hold_dir = 0
        self._pause_menu_open = False
        self._debug_menu_open = False
        self._awaiting_noclip_rebind = False
        self._set_pointer_lock(False)

        # Hide in-game HUD while picking.
        self.ui.speed_hud_label.hide()
        self.ui.hide()
        self.pause_ui.hide()

        self._menu = MainMenuController(
            aspect2d=self.aspect2d,
            initial_game_root=self.cfg.hl_root,
            initial_mod=self.cfg.hl_mod if self.cfg.hl_root else None,
            on_start_map_json=self._start_game,
            on_import_bsp=self._start_import_from_request,
            on_quit=self.userExit,
        )

    def _back_to_menu(self) -> None:
        if self._mode != "game":
            return
        if self._importing:
            return
        self._teardown_game_mode()

        # Tear down active world state so returning to menu doesn't leak nodes/state.
        self.scene = None
        self.collision = None
        self.player = None
        try:
            self.world_root.removeNode()
        except Exception:
            pass
        self.world_root = self.render.attachNewNode("world-root")

        self.input_debug.hide()
        self.ui.hide()
        self.pause_ui.hide()

        self._enter_main_menu()

    def _menu_toggle_search(self) -> None:
        if self._mode == "menu" and self._menu is not None and not self._importing:
            self._menu.toggle_search()

    def _menu_nav_press(self, dir01: int) -> None:
        if self._mode != "menu" or self._menu is None or self._importing:
            return
        if self._menu.is_search_active():
            return
        now = float(globalClock.getFrameTime())
        d = -1 if dir01 < 0 else 1
        if self._menu_hold_dir != d:
            self._menu_hold_dir = d
            self._menu_hold_since = now
            self._menu_hold_next = now + 0.28
        self._safe_call("menu.move", lambda: self._menu.move(d))

    def _menu_nav_release(self, dir01: int) -> None:
        d = -1 if dir01 < 0 else 1
        if self._menu_hold_dir == d:
            self._menu_hold_dir = 0

    def _menu_page(self, dir01: int) -> None:
        if self._mode != "menu" or self._menu is None or self._importing:
            return
        if self._menu.is_search_active():
            return
        d = -1 if dir01 < 0 else 1
        shift = False
        try:
            if self.mouseWatcherNode is not None:
                shift = bool(self.mouseWatcherNode.isButtonDown(KeyboardButton.shift()))
        except Exception:
            shift = False
        jump = 20 if shift else 10
        self._safe_call("menu.page", lambda: self._menu.move(d * jump))

    def _menu_select(self) -> None:
        if self._mode != "menu" or self._menu is None or self._importing:
            return
        self._safe_call("menu.enter", self._menu.on_enter)

    def _start_import_from_request(self, req: ImportRequest) -> None:
        update_state(last_game_root=req.game_root, last_mod=req.mod)

        app_root = ivan_app_root()
        out_dir = app_root / "assets" / "imported" / "halflife" / req.mod / req.map_label
        game_root = Path(req.game_root) / req.mod

        script = app_root / "tools" / "importers" / "goldsrc" / "import_goldsrc_bsp.py"
        venv_py = app_root / ".venv" / "bin" / "python"
        python_exe = str(venv_py) if venv_py.exists() else sys.executable
        cmd = [
            python_exe,
            str(script),
            "--bsp",
            req.bsp_path,
            "--game-root",
            str(game_root),
            "--out",
            str(out_dir),
            "--map-id",
            req.map_label,
            "--scale",
            "0.03",
        ]

        self._importing = True
        self._import_error = None
        self._pending_map_json = None
        if self._menu is not None:
            self._menu.set_loading_status(f"Importing {req.map_label}", started_at=globalClock.getFrameTime())

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
        try:
            self._teardown_game_mode()
            if map_json:
                update_state(last_map_json=map_json)

            # Tear down menu.
            if self._menu is not None:
                self._menu.destroy()
                self._menu = None

            self._mode = "game"
            self._pause_menu_open = False
            self._debug_menu_open = False
            self._awaiting_noclip_rebind = False
            self._pointer_locked = True
            self._last_mouse = None
            if not self.cfg.smoke:
                self._set_pointer_lock(True)
            self.ui.speed_hud_label.show()
            self.ui.hide()
            self.pause_ui.hide()
            if not self.cfg.smoke:
                self._center_mouse()
                # Show input debug briefly after loading a map (useful when mouse/keyboard seem dead).
                self._input_debug_until = globalClock.getFrameTime() + 8.0
                self.input_debug.show()

            # Reset world root to allow reloading.
            self.world_root.removeNode()
            self.world_root = self.render.attachNewNode("world-root")

            resolved = resolve_map_json(map_json) if map_json else None
            bundle_root = resolved.parent if resolved is not None else None
            run_meta: RunMetadata = load_run_metadata(bundle_root=bundle_root) if bundle_root is not None else RunMetadata()

            cfg_map_json = str(resolved) if resolved is not None else map_json
            cfg = RunConfig(smoke=self.cfg.smoke, map_json=cfg_map_json, hl_root=self.cfg.hl_root, hl_mod=self.cfg.hl_mod)
            self.scene = WorldScene()
            self.scene.build(cfg=cfg, loader=self.loader, render=self.world_root, camera=self.camera)

            # Optional spawn override stored next to the map (bundle run.json).
            self._apply_spawn_override(spawn=run_meta.spawn_override)
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

            # Install game mode after the world/player exist.
            mode = load_mode(mode=run_meta.mode, config=run_meta.mode_config)
            self._setup_game_mode(mode=mode, bundle_root=bundle_root)
        except Exception as e:
            # Avoid leaving the app in a broken half-loaded state where input feels "dead".
            self._handle_unhandled_error(context="start_game", exc=e)
            self._back_to_menu()

    def _apply_spawn_override(self, *, spawn: dict | None) -> None:
        if self.scene is None or not isinstance(spawn, dict):
            return
        pos = spawn.get("position")
        yaw = spawn.get("yaw")
        if isinstance(pos, list) and len(pos) == 3:
            try:
                self.scene.spawn_point = LVector3f(float(pos[0]), float(pos[1]), float(pos[2]))
            except Exception:
                pass
        if isinstance(yaw, (int, float)):
            self.scene.spawn_yaw = float(yaw)

    def _setup_game_mode(self, *, mode: Any, bundle_root: Path | None) -> None:
        if self.scene is None:
            return
        self._game_mode = mode
        self._game_mode_events = []
        self._game_mode_ctx = ModeContext(
            map_id=str(self.scene.map_id),
            bundle_root=str(bundle_root) if bundle_root is not None else None,
            tuning=self.tuning,
            ui=self.ui,
            host=self,
        )
        try:
            bindings = mode.bindings()
            for evt, cb in getattr(bindings, "events", []) or []:
                self.accept(evt, lambda cb=cb, e=evt: self._safe_call(f"mode.{mode.id}.{e}", cb))
                self._game_mode_events.append(evt)
        except Exception as e:
            self._handle_unhandled_error(context="mode.bindings", exc=e)
        try:
            mode.on_enter(ctx=self._game_mode_ctx)
        except Exception as e:
            self._handle_unhandled_error(context="mode.on_enter", exc=e)

    def _teardown_game_mode(self) -> None:
        if self._game_mode is None:
            return
        for evt in self._game_mode_events:
            try:
                self.ignore(evt)
            except Exception:
                pass
        try:
            self._game_mode.on_exit()
        except Exception as e:
            self._handle_unhandled_error(context="mode.on_exit", exc=e)
        self._game_mode = None
        self._game_mode_ctx = None
        self._game_mode_events = []

    def _clear_errors(self) -> None:
        self.error_log.clear()
        self.error_console.refresh(auto_reveal=False)

    def _safe_call(self, context: str, fn) -> None:
        try:
            fn()
        except Exception as e:
            self._handle_unhandled_error(context=context, exc=e)

    def _handle_unhandled_error(self, *, context: str, exc: BaseException) -> None:
        # Avoid ever crashing because of a UI/update exception.
        try:
            self.error_log.log_exception(context=context, exc=exc)
            self.error_console.refresh(auto_reveal=True)
        except Exception:
            # Last-ditch: never let the logger crash the app.
            try:
                print(f"[FATAL] error logger failed: {traceback.format_exc()}", file=sys.stderr)
            except Exception:
                pass

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

        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        right = LVector3f(forward.y, -forward.x, 0)

        move = LVector3f(0, 0, 0)
        # Support non-US keyboard layouts by checking Cyrillic equivalents of WASD (RU):
        # W/A/S/D -> Ц/Ф/Ы/В. Arrow keys are also supported as a fallback.
        if self._is_key_down("w") or self._is_key_down("ц") or self.mouseWatcherNode.isButtonDown(KeyboardButton.up()):
            move += forward
        if self._is_key_down("s") or self._is_key_down("ы") or self.mouseWatcherNode.isButtonDown(KeyboardButton.down()):
            move -= forward
        if self._is_key_down("d") or self._is_key_down("в") or self.mouseWatcherNode.isButtonDown(KeyboardButton.right()):
            move += right
        if self._is_key_down("a") or self._is_key_down("ф") or self.mouseWatcherNode.isButtonDown(KeyboardButton.left()):
            move -= right

        if move.lengthSquared() > 0:
            move.normalize()
        return move

    def _is_key_down(self, key_name: str) -> bool:
        if self.mouseWatcherNode is None:
            return False
        k = (key_name or "").lower().strip()
        if not k:
            return False
        if k in {"space", "spacebar"}:
            return bool(self.mouseWatcherNode.isButtonDown(KeyboardButton.space()))
        if len(k) == 1 and ord(k) < 128:
            # ASCII key (layout-dependent) + raw key (layout-independent).
            if self.mouseWatcherNode.isButtonDown(KeyboardButton.ascii_key(k)):
                return True
            return bool(self.mouseWatcherNode.isButtonDown(ButtonHandle(f"raw-{k}")))
        if k in {"tab", "enter", "escape", "shift", "control", "alt"}:
            return bool(self.mouseWatcherNode.isButtonDown(ButtonHandle(k)))
        return bool(self.mouseWatcherNode.isButtonDown(ButtonHandle(k)))

    def _queue_jump(self) -> None:
        if self.player is not None and self._mode == "game" and not self._pause_menu_open and not self._debug_menu_open:
            self.player.queue_jump()

    def _grapple_mock(self) -> None:
        if self.player is not None and self._mode == "game" and not self._pause_menu_open and not self._debug_menu_open:
            self.player.apply_grapple_impulse(yaw_deg=self._yaw)

    def request_respawn(self) -> None:
        self._do_respawn(from_mode=True)

    def player_pos(self) -> LVector3f:
        if self.player is None:
            return LVector3f(0, 0, 0)
        return LVector3f(self.player.pos)

    def now(self) -> float:
        return float(globalClock.getFrameTime())

    def player_yaw_deg(self) -> float:
        return float(self._yaw)

    def _do_respawn(self, *, from_mode: bool) -> None:
        if self.player is None or self.scene is None:
            return
        if not from_mode and self._game_mode is not None:
            try:
                handled = bool(self._game_mode.on_reset_requested())
            except Exception as e:
                self._handle_unhandled_error(context="mode.on_reset_requested", exc=e)
                handled = False
            if handled:
                return
        # Keep respawn synced to the current scene spawn (may be overridden by run.json).
        self.player.spawn_point = LVector3f(self.scene.spawn_point)
        self.player.respawn()
        self._yaw = float(self.scene.spawn_yaw)
        self._pitch = 0.0
        self.player_node.setPos(self.player.pos)

    def _toggle_noclip(self) -> None:
        self.tuning.noclip_enabled = not bool(self.tuning.noclip_enabled)

    def _step_noclip(self, *, dt: float, wish_dir: LVector3f, crouching: bool) -> None:
        if self.player is None:
            return
        up = 1.0 if self._is_key_down("space") else 0.0
        down = 1.0 if crouching else 0.0
        move = LVector3f(wish_dir.x, wish_dir.y, up - down)
        if move.lengthSquared() > 1e-12:
            move.normalize()
        speed = max(0.0, float(self.tuning.noclip_speed))
        self.player.vel = move * speed
        self.player.pos += self.player.vel * dt
        self.player.grounded = False

    def _update(self, task: Task) -> int:
        try:
            if self._mode == "menu":
                if self._menu is not None:
                    self._menu.tick(globalClock.getFrameTime())
                self._update_menu_hold(now=float(globalClock.getFrameTime()))
                if self._import_error and self._menu is not None:
                    # Importer failures are not unhandled exceptions, but are still useful in the error feed.
                    self.error_log.log_message(context="import", message=self._import_error)
                    self.error_console.refresh(auto_reveal=True)
                    self._menu.set_status(f"Import failed: {self._import_error}")
                    self._import_error = None
                if self._pending_map_json:
                    self._start_game(map_json=self._pending_map_json)
                    self._pending_map_json = None
                return Task.cont
            if self._mode != "game" or self.player is None:
                return Task.cont

            dt = min(globalClock.getDt(), 1.0 / 30.0)
            now = float(globalClock.getFrameTime())

            if self.scene is not None:
                self.scene.tick(now=now)

            menu_open = self._pause_menu_open or self._debug_menu_open

            # Precompute wish so debug overlay can show it even if movement seems dead.
            wish = LVector3f(0, 0, 0) if menu_open else self._wish_direction()
            noclip_toggle_down = False if menu_open else self._is_key_down(self._noclip_toggle_key)
            if not menu_open and noclip_toggle_down and not self._noclip_toggle_prev_down:
                self._toggle_noclip()
            self._noclip_toggle_prev_down = noclip_toggle_down

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

            if not menu_open:
                self._update_look()
            crouching = False if menu_open else self._is_crouching()

            if not menu_open and self.tuning.autojump_enabled and self._is_key_down("space"):
                self.player.queue_jump()

            if self.tuning.noclip_enabled:
                self._step_noclip(dt=dt, wish_dir=wish, crouching=crouching)
            else:
                self.player.step(dt=dt, wish_dir=wish, yaw_deg=self._yaw, crouching=crouching)

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
                f"wall: {self.player.has_wall_for_jump()} | surf: {self.player.has_surf_surface()}"
            )

            if self._game_mode is not None:
                try:
                    self._game_mode.tick(now=now, player_pos=self.player.pos)
                except Exception as e:
                    self._handle_unhandled_error(context="mode.tick", exc=e)

            return Task.cont
        except Exception as e:
            self._handle_unhandled_error(context="update.loop", exc=e)
            return Task.cont

    def _update_menu_hold(self, *, now: float) -> None:
        if self._menu_hold_dir == 0 or self._menu is None or self._importing:
            return
        if self._menu.is_search_active():
            return
        if now < self._menu_hold_next:
            return

        t = max(0.0, now - self._menu_hold_since)
        # Accelerate by shortening interval and increasing step size.
        if t < 0.8:
            interval = 0.11
            step = 1
        elif t < 1.6:
            interval = 0.08
            step = 2
        elif t < 3.0:
            interval = 0.05
            step = 4
        else:
            interval = 0.03
            step = 8

        d = self._menu_hold_dir * step
        self._safe_call("menu.hold", lambda: self._menu.move(d))
        self._menu_hold_next = now + interval

    def _is_crouching(self) -> bool:
        return self._is_key_down("c")

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
            # Best-effort: don't fail smoke runs if filesystem is read-only.
            return

        try:
            # Ensure at least one fresh frame is rendered before capturing.
            self.graphicsEngine.renderFrame()
            img: PNMImage | None = None
            try:
                img = self.win.getScreenshot()
            except Exception:
                # Older Panda3D builds can require an output buffer.
                tmp = PNMImage()
                ok = self.win.getScreenshot(tmp)
                img = tmp if ok else None
            if img is None:
                return
            img.write(Filename.fromOsSpecific(str(out)))
        except Exception:
            # Best-effort screenshot. Smoke mode is meant to never hard-fail.
            return


def run(
    *,
    smoke: bool = False,
    smoke_screenshot: str | None = None,
    map_json: str | None = None,
    hl_root: str | None = None,
    hl_mod: str = "valve",
) -> None:
    app = RunnerDemo(
        RunConfig(smoke=smoke, smoke_screenshot=smoke_screenshot, map_json=map_json, hl_root=hl_root, hl_mod=hl_mod)
    )
    app.run()
