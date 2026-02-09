from __future__ import annotations

import math
import errno
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task
from panda3d.core import (
    ButtonHandle,
    Filename,
    GeomNode,
    KeyboardButton,
    LVector3f,
    PNMImage,
    Texture,
    WindowProperties,
    loadPrcFileData,
)

from ivan.app_config import RunConfig
from ivan.common.error_log import ErrorLog
from ivan.console.control_server import ConsoleControlServer
from ivan.console.core import CommandContext
from ivan.console.ivan_bindings import build_client_console
from ivan.console.line_bus import ThreadSafeLineBus
from ivan.maps.bundle_io import resolve_bundle_handle
from ivan.maps.run_metadata import RunMetadata, load_run_metadata
from ivan.modes.base import ModeContext
from ivan.modes.loader import load_mode
from ivan.net import EmbeddedHostServer, MultiplayerClient
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.replays import (
    DemoFrame,
    DemoRecording,
    append_frame,
    compare_latest_replays,
    export_latest_replay_telemetry,
    list_replays,
    load_replay,
    new_recording,
    save_recording,
)
from ivan.state import IvanState, load_state, update_state
from ivan.ui.debug_ui import DebugUI
from ivan.ui.console_ui import ConsoleUI
from ivan.ui.error_console_ui import ErrorConsoleUI
from ivan.ui.input_debug_ui import InputDebugUI
from ivan.ui.main_menu import ImportRequest, MainMenuController
from ivan.ui.pause_menu_ui import PauseMenuUI
from ivan.ui.replay_browser_ui import ReplayBrowserUI, ReplayListItem
from ivan.ui.replay_input_ui import ReplayInputUI
from ivan.world.scene import WorldScene
from irun_ui_kit.renderer import UIRenderer
from irun_ui_kit.theme import Theme

from . import grapple_rope as _grapple_rope
from . import input_system as _input
from . import menu_flow as _menu
from . import netcode as _net
from . import tuning_profiles as _profiles
from .feel_metrics import FeelMetrics
from .feel_feedback import apply_adjustments as _apply_feedback_adjustments
from .feel_feedback import suggest_adjustments as _suggest_feel_adjustments
from .hooks import EventHooks
from .input_system import _InputCommand
from .netcode import _NetPerfStats, _PredictedInput, _PredictedState, _RemotePlayerVisual


class RunnerDemo(ShowBase):
    def __init__(self, cfg: RunConfig) -> None:
        loadPrcFileData("", "audio-library-name null")
        # GoldSrc and some Source assets include many non-power-of-two (NPOT) textures.
        # Panda3D can rescale these to the nearest power-of-two by default, which breaks
        # BSP UV mapping (textures look skewed/flipped). Disable that behavior.
        loadPrcFileData("", "textures-power-2 none")
        loadPrcFileData("", "textures-square none")
        loadPrcFileData("", "textures-auto-power-2 0")
        # Allow the user to resize the window by dragging its edges.
        loadPrcFileData("", "win-fixed-size 0")
        if cfg.smoke:
            loadPrcFileData("", "window-type offscreen")

        super().__init__()

        self.cfg = cfg
        # Centralized UI theme + font/background defaults for all non-HUD UI.
        self.ui_renderer = UIRenderer(base=self, theme=Theme())
        self.ui_renderer.set_background()
        self.ui_theme = self.ui_renderer.theme
        self.tuning = PhysicsTuning()
        self._loaded_state = load_state()
        self._suspend_tuning_persist: bool = False
        self._default_profiles = self._build_default_profiles()
        self._profiles: dict[str, dict[str, float | bool]] = {}
        self._default_profile_names = set(self._default_profiles.keys())
        self._active_profile_name: str = "surf_bhop_c2"
        self._load_profiles_from_state(self._loaded_state)
        self.disableMouse()

        self._hooks = EventHooks(base=self, safe_call=self._safe_call)

        self._yaw = 0.0
        self._pitch = 0.0
        self._pointer_locked = True
        self._pause_menu_open = False
        self._debug_menu_open = False
        self._replay_browser_open = False
        self._console_open = False
        self._mode: str = "boot"  # boot | menu | game
        self._last_mouse: tuple[float, float] | None = None
        self._input_debug_until: float = 0.0
        self._noclip_toggle_key: str = "v"
        self._awaiting_noclip_rebind: bool = False
        self._demo_save_key: str = "f"
        self._sim_tick_rate_hz: int = 60
        self._sim_fixed_dt: float = 1.0 / float(self._sim_tick_rate_hz)
        self._look_input_scale: int = 256
        self._playback_look_scale: int = self._look_input_scale
        self._sim_accumulator: float = 0.0
        self._mouse_dx_accum: float = 0.0
        self._mouse_dy_accum: float = 0.0
        self._prev_jump_down: bool = False
        self._prev_grapple_down: bool = False
        self._prev_noclip_toggle_down: bool = False
        self._prev_demo_save_down: bool = False
        self._active_recording: DemoRecording | None = None
        self._loaded_replay_path: Path | None = None
        self._playback_frames: list[DemoFrame] | None = None
        self._playback_index: int = 0
        self._playback_active: bool = False
        self._net_client: MultiplayerClient | None = None
        self._net_connected: bool = False
        self._net_player_id: int = 0
        self._remote_players: dict[int, _RemotePlayerVisual] = {}
        self._net_seq_counter: int = 0
        self._net_pending_inputs: list[_PredictedInput] = []
        self._net_predicted_states: list[_PredictedState] = []
        self._net_last_server_tick: int = 0
        self._net_last_acked_seq: int = 0
        self._net_local_respawn_seq: int = 0
        self._net_last_snapshot_local_time: float = 0.0
        self._net_interp_delay_ticks: float = 6.0
        # GoldSrc/Source-style dead reckoning when snapshots stall (short clamp to avoid runaway).
        self._net_remote_extrapolate_max_ticks: float = 8.0
        self._net_can_configure: bool = False
        self._net_authoritative_tuning: dict[str, float | bool] = {}
        self._net_authoritative_tuning_version: int = 0
        self._net_snapshot_intervals: list[float] = []
        self._net_server_tick_offset_ready: bool = False
        self._net_server_tick_offset_ticks: float = 0.0
        self._net_server_tick_offset_smooth: float = 0.12
        self._net_reconcile_pos_offset = LVector3f(0, 0, 0)
        self._net_reconcile_yaw_offset: float = 0.0
        self._net_reconcile_pitch_offset: float = 0.0
        self._net_reconcile_decay_hz: float = 22.0
        self._net_local_cam_shell_enabled: bool = True
        self._net_local_cam_smooth_hz: float = 28.0
        self._net_local_cam_ready: bool = False
        self._net_local_cam_pos = LVector3f(0, 0, 0)
        self._net_local_cam_yaw: float = 0.0
        self._net_local_cam_pitch: float = 0.0
        self._net_cfg_apply_pending_version: int = 0
        self._net_cfg_apply_sent_at: float = 0.0
        self._net_perf = _NetPerfStats()
        self._net_perf_last_publish: float = 0.0
        self._net_perf_text: str = ""
        self._feel_metrics = FeelMetrics()
        self._feel_perf_text: str = "feel | collecting..."
        self._embedded_server: EmbeddedHostServer | None = None
        self._open_to_network: bool = False
        # If no explicit CLI connect target is provided, keep last used host/port for fast iteration.
        st_host = str(self._loaded_state.last_net_host).strip() if self._loaded_state.last_net_host else None
        st_port = int(self._loaded_state.last_net_port) if isinstance(self._loaded_state.last_net_port, int) else None
        self._runtime_connect_host: str | None = (str(self.cfg.net_host).strip() if self.cfg.net_host else st_host)
        self._runtime_connect_port: int = int(self.cfg.net_port) if self.cfg.net_host else int(st_port or self.cfg.net_port)
        self._local_hp: int = 100
        self._sim_prev_player_pos = LVector3f(0, 0, 0)
        self._sim_curr_player_pos = LVector3f(0, 0, 0)
        self._sim_prev_cam_pos = LVector3f(0, 0, 0)
        self._sim_curr_cam_pos = LVector3f(0, 0, 0)
        self._sim_prev_yaw: float = 0.0
        self._sim_curr_yaw: float = 0.0
        self._sim_prev_pitch: float = 0.0
        self._sim_curr_pitch: float = 0.0
        self._sim_state_ready: bool = False
        self._grapple_rope_node = GeomNode("grapple-rope")
        self._grapple_rope_np = self.render.attachNewNode(self._grapple_rope_node)
        self._grapple_rope_np.setTwoSided(True)
        self._grapple_rope_np.setTransparency(True)
        self._grapple_rope_np.setBin("fixed", 12)
        self._grapple_rope_np.setDepthWrite(True)
        self._grapple_rope_np.setTexture(self._build_grapple_rope_texture())
        self._grapple_rope_np.hide()

        self.scene: WorldScene | None = None
        self.collision: CollisionWorld | None = None
        self.player: PlayerController | None = None
        self.player_node = self.render.attachNewNode("player-node")
        self.world_root = self.render.attachNewNode("world-root")
        self._game_mode: Any | None = None
        self._game_mode_ctx: ModeContext | None = None
        self._game_mode_events: list[str] = []
        self._current_map_json: str | None = None

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
        self.ui = DebugUI(
            aspect2d=self.aspect2d,
            theme=self.ui_theme,
            tuning=self.tuning,
            on_tuning_change=self._on_tuning_change,
            on_profile_select=self._apply_profile,
            on_profile_save=self._save_active_profile,
        )
        self.ui.set_profiles(self._profile_names(), self._active_profile_name)
        self.error_console = ErrorConsoleUI(aspect2d=self.aspect2d, theme=self.ui_theme, error_log=self.error_log)
        self.pause_ui = PauseMenuUI(
            aspect2d=self.aspect2d,
            theme=self.ui_theme,
            on_resume=self._close_all_game_menus,
            on_map_selector=self._back_to_menu,
            on_back_to_menu=self._back_to_menu,
            on_quit=self.userExit,
            on_open_replays=self._open_replay_browser,
            on_open_feel_session=self._open_feel_session_menu,
            on_open_keybindings=self._open_keybindings_menu,
            on_rebind_noclip=self._start_rebind_noclip,
            on_toggle_open_network=self._on_toggle_open_network,
            on_connect_server=self._on_connect_server_from_menu,
            on_disconnect_server=self._on_disconnect_server_from_menu,
            on_feel_export_latest=self._feel_export_latest,
            on_feel_compare_latest=self._feel_compare_latest,
            on_feel_apply_feedback=self._feel_apply_feedback,
        )
        self.pause_ui.set_noclip_binding(self._noclip_toggle_key)
        self.pause_ui.set_open_to_network(self._open_to_network)
        self.pause_ui.set_connect_target(
            host=self._runtime_connect_host or "127.0.0.1",
            port=int(self._runtime_connect_port),
        )
        self.replay_browser_ui = ReplayBrowserUI(
            aspect2d=self.aspect2d,
            theme=self.ui_theme,
            on_select=self._load_replay_from_path,
            on_close=self._close_replay_browser,
        )
        self.replay_input_ui = ReplayInputUI(aspect2d=self.aspect2d, theme=self.ui_theme)
        self.replay_input_ui.hide()
        self.console_ui = ConsoleUI(aspect2d=self.aspect2d, theme=self.ui_theme, on_submit=self._console_submit_line)
        self.input_debug = InputDebugUI(aspect2d=self.aspect2d, theme=self.ui_theme)
        self._setup_input()

        # Minimal console runtime (no in-game UI yet). Primarily driven via MCP/control socket.
        self.console = build_client_console(self)
        self._console_bus = ThreadSafeLineBus(max_lines=500)
        self.console.register_listener(self._console_bus.listener)
        # Default chosen to be near the multiplayer default (7777) but not collide.
        self._console_control_port = int(os.environ.get("IRUN_IVAN_CONSOLE_PORT", "7779"))
        self.console_control = ConsoleControlServer(console=self.console, port=int(self._console_control_port))
        try:
            self.console_control.start()
        except Exception:
            # Best-effort: if the port is in use, keep running without the control bridge.
            self.console_control = None

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
        state = self._loaded_state
        fullscreen = bool(state.fullscreen)
        win_w = int(state.window_width) if state.window_width else 1280
        win_h = int(state.window_height) if state.window_height else 720

        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        # M_confined keeps the OS cursor inside the window in windowed mode.
        # Actual FPS input is handled via per-frame center-snap in poll_mouse_look_delta.
        props.setMouseMode(WindowProperties.M_confined if self._pointer_locked else WindowProperties.M_absolute)
        props.setTitle("IRUN IVAN Demo")
        if fullscreen:
            props.setFullscreen(True)
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            props.setFullscreen(False)
            props.setSize(win_w, win_h)
        self.win.requestProperties(props)
        self.camLens.setFov(96)
        # Reduce near-plane clipping when hugging walls in first-person.
        self.camLens.setNearFar(0.03, 5000.0)
        if self._pointer_locked:
            self._center_mouse()

    def _apply_video_settings(self, *, fullscreen: bool, width: int, height: int) -> None:
        """Apply display settings at runtime and persist them to user state."""
        if self.cfg.smoke:
            return
        props = WindowProperties()
        if fullscreen:
            props.setFullscreen(True)
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            props.setFullscreen(False)
            props.setSize(int(width), int(height))
        self.win.requestProperties(props)
        update_state(fullscreen=fullscreen, window_width=int(width), window_height=int(height))

    def _on_scroll_wheel(self, direction: int) -> None:
        """Route mouse wheel: menu scroll in menu mode, debug scroll in game mode."""
        if self._mode == "menu" and self._menu is not None and not self._importing:
            self._safe_call("menu.wheel", lambda: self._menu.move(-direction))
            return
        if self._mode == "game" and self._debug_menu_open:
            self.ui.scroll_wheel(direction)

    def _setup_input(self) -> None:
        self.accept("escape", lambda: self._safe_call("input.escape", self._on_escape))
        self.accept("`", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("ascii`", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("grave", lambda: self._safe_call("input.debug_menu", self._toggle_debug_menu))
        self.accept("f4", lambda: self._safe_call("input.console", self._toggle_console))
        self.accept("r", lambda: self._safe_call("input.respawn", self._on_respawn_pressed))
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
        self.accept("delete", self._menu_delete)
        self.accept("backspace", self._menu_delete)
        self.accept("w", lambda: self._menu_nav_press(-1))
        self.accept("s", lambda: self._menu_nav_press(1))
        self.accept("w-up", lambda: self._menu_nav_release(-1))
        self.accept("s-up", lambda: self._menu_nav_release(1))
        self.accept("control-f", lambda: self._safe_call("menu.search", self._menu_toggle_search))
        self.accept("meta-f", lambda: self._safe_call("menu.search", self._menu_toggle_search))
        self.accept("wheel_up", lambda: self._safe_call("input.wheel_up", lambda: self._on_scroll_wheel(+1)))
        self.accept("wheel_down", lambda: self._safe_call("input.wheel_down", lambda: self._on_scroll_wheel(-1)))
        if hasattr(self, "buttonThrowers") and self.buttonThrowers:
            try:
                self.buttonThrowers[0].node().setKeystrokeEvent("keystroke")
            except Exception:
                pass
        self.accept("keystroke", lambda key: self._safe_call("input.keystroke", lambda: self._on_keystroke(key)))

    def _on_tuning_change(self, field: str) -> None:
        _profiles.on_tuning_change(self, field)

    def _persist_tuning_field(self, field: str) -> None:
        if field not in PhysicsTuning.__annotations__:
            return
        _profiles.persist_profiles_state(self)

    def _current_tuning_snapshot(self) -> dict[str, float | bool]:
        return _profiles.current_tuning_snapshot(self)

    def _apply_authoritative_tuning(self, *, tuning: dict[str, float | bool], version: int) -> None:
        _profiles.apply_authoritative_tuning(self, tuning=tuning, version=version)

    def _send_tuning_to_server(self) -> None:
        _profiles.send_tuning_to_server(self)

    def _append_predicted_state(self, *, seq: int) -> None:
        _net.append_predicted_state(self, seq=seq)

    def _state_for_ack(self, ack: int) -> _PredictedState | None:
        return _net.state_for_ack(self, ack)

    def _reconcile_local_from_server(
        self,
        *,
        x: float,
        y: float,
        z: float,
        vx: float,
        vy: float,
        vz: float,
        yaw: float,
        pitch: float,
        ack: int,
    ) -> None:
        _net.reconcile_local_from_server(
            self,
            x=x,
            y=y,
            z=z,
            vx=vx,
            vy=vy,
            vz=vz,
            yaw=yaw,
            pitch=pitch,
            ack=ack,
        )

    @staticmethod
    def _to_persisted_value(value: object) -> float | bool:
        return _profiles.to_persisted_value(value)

    @staticmethod
    def _build_default_profiles() -> dict[str, dict[str, float | bool]]:
        return _profiles.build_default_profiles()

    def _profile_names(self) -> list[str]:
        return _profiles.profile_names(self)

    def _load_profiles_from_state(self, state: IvanState) -> None:
        _profiles.load_profiles_from_state(self, state)

    def _apply_profile_snapshot(self, values: dict[str, float | bool], *, persist: bool) -> None:
        _profiles.apply_profile_snapshot(self, values, persist=persist)

    def _apply_profile(self, profile_name: str) -> None:
        _profiles.apply_profile(self, profile_name)

    def _save_active_profile(self) -> None:
        _profiles.save_active_profile(self)

    def _make_profile_copy_name(self, base_name: str) -> str:
        return _profiles.make_profile_copy_name(self, base_name)

    def _persist_profiles_state(self) -> None:
        _profiles.persist_profiles_state(self)

    def _on_debug_wheel(self, direction: int) -> None:
        if self._mode != "game" or not self._debug_menu_open:
            return
        self.ui.scroll_wheel(direction)

    def _set_pointer_lock(self, locked: bool) -> None:
        self._pointer_locked = bool(locked)
        self._last_mouse = None
        props = WindowProperties()
        props.setCursorHidden(self._pointer_locked)
        # M_confined keeps the OS cursor inside the window in windowed mode.
        # Actual FPS input is handled via per-frame center-snap in poll_mouse_look_delta.
        props.setMouseMode(WindowProperties.M_confined if self._pointer_locked else WindowProperties.M_absolute)
        self.win.requestProperties(props)
        if self._pointer_locked:
            self._center_mouse()

    def _close_all_game_menus(self) -> None:
        if self._mode != "game":
            return
        self._pause_menu_open = False
        self._debug_menu_open = False
        self._replay_browser_open = False
        self._console_open = False
        self._awaiting_noclip_rebind = False
        self.pause_ui.hide()
        self.replay_browser_ui.hide()
        self.ui.hide()
        try:
            self.console_ui.hide()
        except Exception:
            pass
        self._set_pointer_lock(True)

    def _open_pause_menu(self) -> None:
        if self._mode != "game":
            return
        if self._playback_active:
            self.ui.set_status("Replay lock: press R to exit replay.")
            return
        self._pause_menu_open = True
        self._debug_menu_open = False
        self._replay_browser_open = False
        self._console_open = False
        self._awaiting_noclip_rebind = False
        try:
            self.console_ui.hide()
        except Exception:
            pass
        self.pause_ui.show_main()
        self.pause_ui.set_keybind_status("")
        self.pause_ui.set_open_to_network(self._open_to_network)
        self.pause_ui.set_connect_target(
            host=self._runtime_connect_host or "127.0.0.1",
            port=int(self._runtime_connect_port),
        )
        if self._net_connected and self._net_client is not None:
            try:
                self.pause_ui.set_multiplayer_status(
                    f"Connected to {self._net_client.host}:{self._net_client.tcp_port}"
                )
            except Exception:
                self.pause_ui.set_multiplayer_status("Connected.")
        else:
            self.pause_ui.set_multiplayer_status("Not connected.")
        self.pause_ui.show()
        self.replay_browser_ui.hide()
        self.ui.hide()
        self._set_pointer_lock(False)

    def _toggle_debug_menu(self) -> None:
        if self._mode != "game":
            return
        if self._playback_active:
            self.ui.set_status("Replay lock: press R to exit replay.")
            return
        if self._replay_browser_open:
            self._close_replay_browser()
            return
        self._debug_menu_open = not self._debug_menu_open
        if self._debug_menu_open:
            self._pause_menu_open = False
            self._replay_browser_open = False
            self._console_open = False
            self.pause_ui.hide()
            self.replay_browser_ui.hide()
            try:
                self.console_ui.hide()
            except Exception:
                pass
            self.ui.show()
            self._set_pointer_lock(False)
            return
        self.ui.hide()
        if self._pause_menu_open or self._replay_browser_open:
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
        if self._playback_active:
            self.ui.set_status("Replay lock: press R to exit replay.")
            return
        if self._replay_browser_open:
            self._close_replay_browser()
            return
        if self._console_open:
            self._close_console()
            return
        if self._debug_menu_open or self._pause_menu_open:
            self._close_all_game_menus()
            return
        self._open_pause_menu()

    def _toggle_console(self) -> None:
        if self._mode != "game":
            return
        if self._playback_active:
            self.ui.set_status("Replay lock: press R to exit replay.")
            return
        if self._console_open:
            self._close_console()
        else:
            self._open_console()

    def _open_console(self) -> None:
        if self._mode != "game":
            return
        # Keep console mutually exclusive with other in-game menus.
        if self._pause_menu_open or self._debug_menu_open or self._replay_browser_open:
            self._close_all_game_menus()
        self._console_open = True
        self.console_ui.show()
        self._set_pointer_lock(False)

    def _close_console(self) -> None:
        self._console_open = False
        try:
            self.console_ui.hide()
        except Exception:
            pass
        if not (self._pause_menu_open or self._debug_menu_open or self._replay_browser_open):
            self._set_pointer_lock(True)

    def _console_submit_line(self, line: str) -> list[str]:
        return list(self.console.execute_line(ctx=CommandContext(role="client", origin="ui"), line=str(line)))

    def _open_keybindings_menu(self) -> None:
        if self._mode != "game":
            return
        self.pause_ui.show_keybindings()
        self.pause_ui.set_noclip_binding(self._noclip_toggle_key)
        self.pause_ui.set_keybind_status("")

    def _open_feel_session_menu(self) -> None:
        if self._mode != "game":
            return
        self.pause_ui.show_feel_session()
        self.pause_ui.set_feel_status("Use Route tag + feedback, then Export/Compare/Apply.")

    def _feel_export_latest(self, route_tag: str) -> None:
        tag = str(route_tag or "").strip()
        try:
            exported = export_latest_replay_telemetry()
        except Exception as e:
            msg = f"Feel export failed: {e}"
            self.pause_ui.set_feel_status(msg)
            self.ui.set_status(msg)
            return
        msg = f"Exported latest replay telemetry: {exported.summary_path.name} ({tag or 'route: none'})"
        self.pause_ui.set_feel_status(msg)
        self.ui.set_status(msg)

    def _feel_compare_latest(self, route_tag: str) -> None:
        tag = str(route_tag or "").strip()
        try:
            comp = compare_latest_replays(route_tag=tag or None)
        except Exception as e:
            msg = f"Feel compare failed: {e}"
            self.pause_ui.set_feel_status(msg)
            self.ui.set_status(msg)
            return
        msg = (
            f"Compare complete: +{comp.improved_count} / -{comp.regressed_count} / ={comp.equal_count} "
            f"({comp.comparison_path.name})"
        )
        self.pause_ui.set_feel_status(msg)
        self.ui.set_status(msg)

    def _feel_apply_feedback(self, route_tag: str, feedback_text: str) -> None:
        text = str(feedback_text or "").strip()
        tag = str(route_tag or "").strip()
        if not text:
            msg = "Feel feedback is empty."
            self.pause_ui.set_feel_status(msg)
            self.ui.set_status(msg)
            return
        latest_summary: dict[str, Any] | None = None
        try:
            exported = export_latest_replay_telemetry()
            import json as _json

            latest_summary = _json.loads(exported.summary_path.read_text(encoding="utf-8"))
        except Exception:
            latest_summary = None
        adjustments = _suggest_feel_adjustments(
            feedback_text=text,
            tuning=self.tuning,
            latest_summary=latest_summary,
        )
        if not adjustments:
            msg = "No tuning adjustments suggested for this feedback."
            self.pause_ui.set_feel_status(msg)
            self.ui.set_status(msg)
            return
        _apply_feedback_adjustments(tuning=self.tuning, adjustments=adjustments)
        for adj in adjustments:
            self._on_tuning_change(str(adj.field))
        preview = ", ".join(f"{a.field} {float(a.before):.3f}->{float(a.after):.3f}" for a in adjustments[:4])
        if len(adjustments) > 4:
            preview += f", +{len(adjustments) - 4} more"
        msg = f"Applied {len(adjustments)} feel adjustment(s) [{tag or 'route: none'}]: {preview}"
        self.pause_ui.set_feel_status(msg)
        self.ui.set_status(msg)

    def _open_replay_browser(self) -> None:
        if self._mode != "game":
            return
        if self._playback_active:
            self.ui.set_status("Replay lock: press R to exit replay.")
            return
        self._console_open = False
        try:
            self.console_ui.hide()
        except Exception:
            pass
        items: list[ReplayListItem] = []
        for p in list_replays():
            label = p.stem
            items.append(ReplayListItem(label=label, path=p))
        status = f"{len(items)} replay(s) found."
        self.pause_ui.hide()
        self.replay_browser_ui.show(items=items, status=status)
        self._pause_menu_open = False
        self._replay_browser_open = True
        self._set_pointer_lock(False)

    def _close_replay_browser(self) -> None:
        if self._mode != "game":
            return
        self.replay_browser_ui.hide()
        self._replay_browser_open = False
        self._open_pause_menu()

    def _load_replay_from_path(self, path: Path) -> None:
        try:
            rec = load_replay(path)
        except Exception as e:
            self.error_log.log_message(context="replay.load", message=str(e))
            self.error_console.refresh(auto_reveal=True)
            return

        self._loaded_replay_path = Path(path)
        if rec.metadata.tuning:
            self._apply_profile_snapshot(dict(rec.metadata.tuning), persist=False)
        self._playback_frames = list(rec.frames)
        self._playback_index = 0
        self._playback_active = True
        self._playback_look_scale = max(1, int(rec.metadata.look_scale))
        self._active_recording = None
        self.replay_browser_ui.hide()
        self._replay_browser_open = False
        self.pause_ui.hide()
        self._pause_menu_open = False
        self._set_pointer_lock(True)
        self.replay_input_ui.show()

        if self.scene is not None and rec.metadata.map_id != self.scene.map_id:
            # If map differs and replay points to a known map path, reload the scene first.
            if rec.metadata.map_json:
                self._start_game(map_json=rec.metadata.map_json, lighting=None)
                return
        self._do_respawn(from_mode=True)

    def _stop_replay_playback(self, *, reason: str) -> None:
        was_active = bool(self._playback_active)
        self._playback_active = False
        self._playback_frames = None
        self._playback_index = 0
        self._playback_look_scale = self._look_input_scale
        self._mouse_dx_accum = 0.0
        self._mouse_dy_accum = 0.0
        self._last_mouse = None
        self.replay_input_ui.hide()
        if was_active and reason:
            self.ui.set_status(str(reason))

    def _start_new_demo_recording(self) -> None:
        if self.scene is None:
            return
        snapshot = {
            field: self._to_persisted_value(getattr(self.tuning, field))
            for field in PhysicsTuning.__annotations__.keys()
        }
        self._active_recording = new_recording(
            tick_rate=self._sim_tick_rate_hz,
            look_scale=self._look_input_scale,
            map_id=str(self.scene.map_id),
            map_json=self._current_map_json,
            tuning=snapshot,
        )
        self.ui.set_status(f"Recording demo: {self._active_recording.metadata.demo_name}")

    def _save_current_demo(self) -> None:
        if self._active_recording is None:
            self.ui.set_status("No active demo recording.")
            return
        if not self._active_recording.frames:
            self.ui.set_status("Demo not saved (empty recording).")
            return
        out = save_recording(self._active_recording)
        self.ui.set_status(f"Demo saved: {out.name} ({len(self._active_recording.frames)} ticks)")

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
        return _input.normalize_bind_key(key)

    def _enter_main_menu(self) -> None:
        _menu.enter_main_menu(self)

    def _back_to_menu(self) -> None:
        _menu.back_to_menu(self)

    def _menu_toggle_search(self) -> None:
        _menu.menu_toggle_search(self)

    def _menu_nav_press(self, dir01: int) -> None:
        _menu.menu_nav_press(self, dir01)

    def _menu_nav_release(self, dir01: int) -> None:
        _menu.menu_nav_release(self, dir01)

    def _menu_page(self, dir01: int) -> None:
        _menu.menu_page(self, dir01)

    def _menu_select(self) -> None:
        _menu.menu_select(self)

    def _menu_delete(self) -> None:
        _menu.menu_delete(self)

    def _start_import_from_request(self, req: ImportRequest) -> None:
        _menu.start_import_from_request(self, req)

    def _start_game(self, map_json: str | None, lighting: dict | None = None) -> None:
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
            self.ui.set_speed_hud_visible(True)
            self.ui.set_crosshair_visible(True)
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

            handle = resolve_bundle_handle(map_json) if map_json else None
            bundle_ref = handle.bundle_ref if handle is not None else None
            run_meta: RunMetadata = (
                load_run_metadata(bundle_ref=bundle_ref) if bundle_ref is not None else RunMetadata()
            )

            cfg_map_json = str(handle.map_json) if handle is not None else map_json
            lighting_cfg = lighting if isinstance(lighting, dict) else run_meta.lighting
            cfg = RunConfig(
                smoke=self.cfg.smoke,
                map_json=cfg_map_json,
                hl_root=self.cfg.hl_root,
                hl_mod=self.cfg.hl_mod,
                lighting=lighting_cfg if isinstance(lighting_cfg, dict) else None,
                visibility=run_meta.visibility if isinstance(run_meta.visibility, dict) else None,
            )
            self.scene = WorldScene()
            self.scene.build(cfg=cfg, loader=self.loader, render=self.world_root, camera=self.camera)
            # Visibility culling defaults OFF (can be enabled via the debug menu).
            self.scene.set_visibility_enabled(bool(self.tuning.vis_culling_enabled))
            self._current_map_json = cfg_map_json
            self._clear_remote_players()

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
            self._local_hp = 100
            self._sim_state_ready = False
            self._push_sim_snapshot()
            self._render_interpolated_state(alpha=1.0)
            self._sim_accumulator = 0.0
            self._mouse_dx_accum = 0.0
            self._mouse_dy_accum = 0.0
            if not self._playback_active:
                self._playback_look_scale = self._look_input_scale
            self._prev_jump_down = False
            self._prev_grapple_down = False
            self._prev_noclip_toggle_down = False
            self._prev_demo_save_down = False
            if not self._playback_active:
                self._start_new_demo_recording()
            if self._runtime_connect_host or self._open_to_network:
                if self._open_to_network and not self._runtime_connect_host:
                    # Local host mode: restart to ensure server runs on the selected map.
                    self._stop_embedded_server()
                self._connect_multiplayer_if_requested()
            else:
                self._disconnect_multiplayer()
                self._stop_embedded_server()

            # Install game mode after the world/player exist.
            mode = load_mode(mode=run_meta.mode, config=run_meta.mode_config)
            self._setup_game_mode(mode=mode, bundle_root=bundle_ref)
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
                self._hooks.bind(
                    group="mode",
                    event=str(evt),
                    context=f"mode.{mode.id}.{evt}",
                    fn=cb,
                )
                self._game_mode_events.append(str(evt))
        except Exception as e:
            self._handle_unhandled_error(context="mode.bindings", exc=e)
        try:
            mode.on_enter(ctx=self._game_mode_ctx)
        except Exception as e:
            self._handle_unhandled_error(context="mode.on_enter", exc=e)

    def _teardown_game_mode(self) -> None:
        if self._game_mode is None:
            return
        self._hooks.unbind_group("mode")
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

    def _poll_mouse_look_delta(self) -> None:
        _input.poll_mouse_look_delta(self)

    def _consume_mouse_look_delta(self) -> tuple[int, int]:
        return _input.consume_mouse_look_delta(self)

    def _apply_look_delta(self, *, dx: int, dy: int, look_scale: int, allow_look: bool) -> None:
        if not allow_look:
            return
        scale = max(1.0, float(look_scale))
        self._yaw -= (float(dx) / scale) * float(self.tuning.mouse_sensitivity)
        self._pitch = max(-88.0, min(88.0, self._pitch - (float(dy) / scale) * float(self.tuning.mouse_sensitivity)))

    @staticmethod
    def _lerp_vec(a: LVector3f, b: LVector3f, t: float) -> LVector3f:
        tt = max(0.0, min(1.0, float(t)))
        return LVector3f(
            float(a.x) + (float(b.x) - float(a.x)) * tt,
            float(a.y) + (float(b.y) - float(a.y)) * tt,
            float(a.z) + (float(b.z) - float(a.z)) * tt,
        )

    @staticmethod
    def _lerp_angle_deg(a: float, b: float, t: float) -> float:
        tt = max(0.0, min(1.0, float(t)))
        d = ((float(b) - float(a) + 180.0) % 360.0) - 180.0
        return float(a) + d * tt

    @staticmethod
    def _angle_delta_deg(from_deg: float, to_deg: float) -> float:
        return ((float(to_deg) - float(from_deg) + 180.0) % 360.0) - 180.0

    def _capture_sim_state(self) -> tuple[LVector3f, LVector3f, float, float]:
        player_pos = LVector3f(0, 0, 0)
        cam_pos = LVector3f(0, 0, 0)
        if self.player is not None:
            player_pos = LVector3f(self.player.pos)
            eye_height = float(self.tuning.player_eye_height)
            if self.player.crouched and bool(self.tuning.crouch_enabled):
                eye_height = min(eye_height, float(self.tuning.crouch_eye_height))
            cam_pos = LVector3f(player_pos.x, player_pos.y, player_pos.z + eye_height)
        return (player_pos, cam_pos, float(self._yaw), float(self._pitch))

    def _push_sim_snapshot(self) -> None:
        p, c, y, pi = self._capture_sim_state()
        if not self._sim_state_ready:
            self._sim_prev_player_pos = LVector3f(p)
            self._sim_curr_player_pos = LVector3f(p)
            self._sim_prev_cam_pos = LVector3f(c)
            self._sim_curr_cam_pos = LVector3f(c)
            self._sim_prev_yaw = float(y)
            self._sim_curr_yaw = float(y)
            self._sim_prev_pitch = float(pi)
            self._sim_curr_pitch = float(pi)
            self._sim_state_ready = True
            return
        self._sim_prev_player_pos = LVector3f(self._sim_curr_player_pos)
        self._sim_prev_cam_pos = LVector3f(self._sim_curr_cam_pos)
        self._sim_prev_yaw = float(self._sim_curr_yaw)
        self._sim_prev_pitch = float(self._sim_curr_pitch)
        self._sim_curr_player_pos = LVector3f(p)
        self._sim_curr_cam_pos = LVector3f(c)
        self._sim_curr_yaw = float(y)
        self._sim_curr_pitch = float(pi)

    def _render_interpolated_state(self, *, alpha: float, frame_dt: float = 0.0) -> None:
        if not self._sim_state_ready:
            return
        a = max(0.0, min(1.0, float(alpha)))
        p = self._lerp_vec(self._sim_prev_player_pos, self._sim_curr_player_pos, a)
        c = self._lerp_vec(self._sim_prev_cam_pos, self._sim_curr_cam_pos, a)
        y = self._lerp_angle_deg(self._sim_prev_yaw, self._sim_curr_yaw, a)
        pi = self._lerp_angle_deg(self._sim_prev_pitch, self._sim_curr_pitch, a)
        if self._net_connected:
            p += self._net_reconcile_pos_offset
        self.player_node.setPos(p)
        if self._net_connected and self._net_local_cam_shell_enabled:
            if not self._net_local_cam_ready:
                self._net_local_cam_pos = LVector3f(c)
                self._net_local_cam_yaw = float(y)
                self._net_local_cam_pitch = float(pi)
                self._net_local_cam_ready = True
            else:
                dt = max(0.0, float(frame_dt))
                blend = 1.0 - math.exp(-max(0.0, float(self._net_local_cam_smooth_hz)) * dt) if dt > 0.0 else 1.0
                self._net_local_cam_pos = self._lerp_vec(self._net_local_cam_pos, c, blend)
                self._net_local_cam_yaw = self._lerp_angle_deg(self._net_local_cam_yaw, y, blend)
                self._net_local_cam_pitch = self._lerp_angle_deg(self._net_local_cam_pitch, pi, blend)
            self.camera.setPos(self._net_local_cam_pos)
            self.camera.setHpr(self._net_local_cam_yaw, self._net_local_cam_pitch, 0)
            self._feel_metrics.record_camera_sample(
                pos=self._net_local_cam_pos,
                yaw=float(self._net_local_cam_yaw),
                pitch=float(self._net_local_cam_pitch),
                dt=max(1e-6, float(frame_dt)),
            )
            return
        self.camera.setPos(c)
        self.camera.setHpr(y, pi, 0)
        self._feel_metrics.record_camera_sample(
            pos=c,
            yaw=float(y),
            pitch=float(pi),
            dt=max(1e-6, float(frame_dt)),
        )

    def _connect_multiplayer_if_requested(self) -> None:
        self._disconnect_multiplayer()
        if not self._runtime_connect_host and not self._open_to_network:
            return
        target_host = self._runtime_connect_host if self._runtime_connect_host else "127.0.0.1"
        target_port = int(self._runtime_connect_port)
        had_embedded_server = self._embedded_server is not None
        start_embedded = self._open_to_network and not self._runtime_connect_host
        if start_embedded:
            embedded_ready = self._start_embedded_server()
            if not embedded_ready:
                self.pause_ui.set_keybind_status(
                    f"Host port {target_port} is busy; trying existing local server."
                )
        try:
            self._net_client = MultiplayerClient(
                host=str(target_host),
                tcp_port=int(target_port),
                name=str(self.cfg.net_name),
            )
            server_map_json = str(self._net_client.server_map_json or "").strip() or None
            if server_map_json and server_map_json != self._current_map_json:
                try:
                    self._net_client.close()
                except Exception:
                    pass
                self._net_client = None
                self._net_connected = False
                self._net_player_id = 0
                self.pause_ui.set_multiplayer_status("Loading server map...")
                self.ui.set_status("Loading server map from host...")
                self._start_game(map_json=server_map_json)
                return
            self._net_connected = True
            self._net_can_configure = bool(self._net_client.can_configure)
            self._net_player_id = int(self._net_client.player_id)
            self._local_hp = 100
            self._net_seq_counter = 0
            self._net_pending_inputs.clear()
            self._net_predicted_states.clear()
            self._net_last_server_tick = 0
            self._net_last_acked_seq = 0
            self._net_local_respawn_seq = 0
            self._net_last_snapshot_local_time = time.monotonic()
            self._net_authoritative_tuning_version = int(self._net_client.server_tuning_version)
            if isinstance(self._net_client.server_tuning, dict):
                self._apply_authoritative_tuning(
                    tuning=dict(self._net_client.server_tuning),
                    version=int(self._net_client.server_tuning_version),
                )
            self._net_snapshot_intervals.clear()
            self._net_server_tick_offset_ready = False
            self._net_server_tick_offset_ticks = 0.0
            self._net_reconcile_pos_offset = LVector3f(0, 0, 0)
            self._net_reconcile_yaw_offset = 0.0
            self._net_reconcile_pitch_offset = 0.0
            self._net_local_cam_ready = False
            self._net_cfg_apply_pending_version = 0
            self._net_cfg_apply_sent_at = 0.0
            self._net_perf.reset()
            self._net_perf_last_publish = 0.0
            self._net_perf_text = ""
            if self._runtime_connect_host:
                update_state(last_net_host=str(self._runtime_connect_host), last_net_port=int(self._runtime_connect_port))
            self.ui.set_status(f"Connected to server {target_host}:{target_port} as #{self._net_player_id}")
            role = "host config owner" if self._net_can_configure else "client (read-only config)"
            self.pause_ui.set_multiplayer_status(f"Connected to {target_host}:{target_port} | {role}")
        except Exception as e:
            self._disconnect_multiplayer()
            self.error_log.log_message(context="net.connect", message=str(e))
            self.error_console.refresh(auto_reveal=True)
            self.pause_ui.set_multiplayer_status(f"Connect failed: {e}")
            started_embedded_server = not had_embedded_server and self._embedded_server is not None
            if start_embedded and started_embedded_server:
                self._stop_embedded_server()

    def _disconnect_multiplayer(self) -> None:
        _net.disconnect_multiplayer(self)

    def _start_embedded_server(self) -> bool:
        # Import from the package at call time so tests can monkeypatch
        # `ivan.game.EmbeddedHostServer` and `ivan.game.time.sleep`.
        from . import EmbeddedHostServer as _EmbeddedHostServer
        from . import time as _time

        if self._embedded_server is not None:
            return True
        host = "0.0.0.0" if self._open_to_network else "127.0.0.1"
        try:
            self._embedded_server = _EmbeddedHostServer(
                host=host,
                tcp_port=int(self._runtime_connect_port),
                udp_port=int(self._runtime_connect_port) + 1,
                map_json=self._current_map_json,
                initial_tuning=self._current_tuning_snapshot(),
            )
            self._embedded_server.start()
        except OSError as e:
            self._embedded_server = None
            if e.errno in (errno.EADDRINUSE, 48):
                return False
            raise
        # Give server a brief warmup window before local connect.
        _time.sleep(0.12)
        return True

    def _stop_embedded_server(self) -> None:
        srv = self._embedded_server
        self._embedded_server = None
        if srv is None:
            return
        try:
            srv.stop(timeout_s=2.0)
        except Exception:
            pass

    def _restart_embedded_server(self) -> None:
        if self._runtime_connect_host:
            return
        self._stop_embedded_server()
        if self._net_client is not None:
            try:
                self._net_client.close()
            except Exception:
                pass
            self._net_client = None
        self._net_connected = False
        self._net_player_id = 0
        self._clear_remote_players()
        self._connect_multiplayer_if_requested()

    def _on_toggle_open_network(self, enabled: bool) -> None:
        _net.on_toggle_open_network(self, enabled)

    def _on_connect_server_from_menu(self, host: str, port_text: str) -> None:
        _net.on_connect_server_from_menu(self, host, port_text)

    def _on_disconnect_server_from_menu(self) -> None:
        _net.on_disconnect_server_from_menu(self)

    def _clear_remote_players(self) -> None:
        _net.clear_remote_players(self)

    def _ensure_remote_player_visual(self, *, player_id: int, name: str) -> _RemotePlayerVisual:
        return _net.ensure_remote_player_visual(self, player_id=player_id, name=name)

    def _poll_network_snapshot(self) -> None:
        _net.poll_network_snapshot(self)

    def _render_remote_players(self, *, alpha: float) -> None:
        _net.render_remote_players(self, alpha=alpha)

    def _wish_direction_from_axes(self, *, move_forward: int, move_right: int) -> LVector3f:
        h_rad = math.radians(self._yaw)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        right = LVector3f(forward.y, -forward.x, 0)

        move = LVector3f(0, 0, 0)
        if move_forward > 0:
            move += forward
        if move_forward < 0:
            move -= forward
        if move_right > 0:
            move += right
        if move_right < 0:
            move -= right

        if move.lengthSquared() > 0:
            move.normalize()
        return move

    def _is_key_down(self, key_name: str) -> bool:
        return _input.is_key_down(self, key_name)

    def _move_axes_from_keyboard(self) -> tuple[int, int]:
        return _input.move_axes_from_keyboard(self)

    def _sample_live_input_command(self, *, menu_open: bool) -> _InputCommand:
        return _input.sample_live_input_command(self, menu_open=menu_open)

    def _sample_replay_input_command(self) -> _InputCommand:
        if not self._playback_frames or self._playback_index >= len(self._playback_frames):
            self._stop_replay_playback(reason="Replay finished.")
            return _InputCommand()
        frame = self._playback_frames[self._playback_index]
        self._playback_index += 1
        return _InputCommand.from_demo_frame(frame, look_scale=self._playback_look_scale)

    def _simulate_input_tick(
        self,
        *,
        cmd: _InputCommand,
        menu_open: bool,
        network_send: bool = True,
        record_demo: bool = True,
        capture_snapshot: bool = True,
    ) -> None:
        if self.player is None or self.scene is None:
            return
        pre_grounded = bool(self.player.grounded)
        pre_vel = LVector3f(self.player.vel)
        if self._playback_active:
            self.replay_input_ui.set_input(
                move_forward=int(cmd.move_forward),
                move_right=int(cmd.move_right),
                jump_pressed=bool(cmd.jump_pressed),
                jump_held=bool(cmd.jump_held),
                crouch_held=bool(cmd.crouch_held),
                look_dx=int(cmd.look_dx),
                look_dy=int(cmd.look_dy),
                key_w_held=bool(cmd.key_w_held),
                key_a_held=bool(cmd.key_a_held),
                key_s_held=bool(cmd.key_s_held),
                key_d_held=bool(cmd.key_d_held),
                arrow_up_held=bool(cmd.arrow_up_held),
                arrow_down_held=bool(cmd.arrow_down_held),
                arrow_left_held=bool(cmd.arrow_left_held),
                arrow_right_held=bool(cmd.arrow_right_held),
                mouse_left_held=bool(cmd.mouse_left_held),
                mouse_right_held=bool(cmd.mouse_right_held),
                raw_wasd_available=bool(cmd.raw_wasd_available),
                raw_arrows_available=bool(cmd.raw_arrows_available),
                raw_mouse_buttons_available=bool(cmd.raw_mouse_buttons_available),
            )

        self._apply_look_delta(
            dx=cmd.look_dx,
            dy=cmd.look_dy,
            look_scale=cmd.look_scale,
            allow_look=(not menu_open),
        )

        if cmd.noclip_toggle_pressed:
            self._toggle_noclip()
        if cmd.grapple_pressed:
            self._on_grapple_primary_down()
        if cmd.jump_pressed:
            self.player.queue_jump()

        wish = self._wish_direction_from_axes(move_forward=cmd.move_forward, move_right=cmd.move_right)
        crouching = bool(cmd.crouch_held)

        if self.tuning.autojump_enabled and cmd.jump_held and self.player.grounded:
            # Autojump is for chained grounded hops; don't feed airborne wall-jump retries.
            self.player.queue_jump()

        if self.tuning.noclip_enabled:
            self._step_noclip(dt=self._sim_fixed_dt, wish_dir=wish, jump_held=bool(cmd.jump_held), crouching=crouching)
        else:
            if not bool(self.tuning.grapple_enabled):
                self.player.detach_grapple()
            self.player.step(dt=self._sim_fixed_dt, wish_dir=wish, yaw_deg=self._yaw, crouching=crouching)

        if self.scene is not None and self.player.pos.z < float(self.scene.kill_z):
            self._do_respawn(from_mode=True)

        self._feel_metrics.record_tick(
            now=float(globalClock.getFrameTime()),
            dt=float(self._sim_fixed_dt),
            jump_pressed=bool(cmd.jump_pressed),
            pre_grounded=pre_grounded,
            post_grounded=bool(self.player.grounded),
            pre_vel=pre_vel,
            post_vel=LVector3f(self.player.vel),
        )

        if capture_snapshot:
            self._push_sim_snapshot()

        if record_demo and self._active_recording is not None and not self._playback_active:
            append_frame(
                self._active_recording,
                cmd.to_demo_frame_with_telemetry(telemetry=self._capture_demo_telemetry(cmd=cmd)),
            )
        if network_send and self._net_connected and self._net_client is not None and not self._playback_active:
            self._net_seq_counter += 1
            seq = int(self._net_seq_counter)
            self._net_pending_inputs.append(_PredictedInput(seq=seq, cmd=cmd))
            self._append_predicted_state(seq=seq)
            self._net_client.send_input(
                seq=seq,
                server_tick_hint=int(self._net_last_server_tick),
                cmd={
                    "dx": int(cmd.look_dx),
                    "dy": int(cmd.look_dy),
                    "ls": int(cmd.look_scale),
                    "mf": int(cmd.move_forward),
                    "mr": int(cmd.move_right),
                    "jp": bool(cmd.jump_pressed),
                    "jh": bool(cmd.jump_held),
                    "ch": bool(cmd.crouch_held),
                    "gp": bool(cmd.grapple_pressed),
                },
            )

    def _queue_jump(self) -> None:
        if (
            self.player is not None
            and self._mode == "game"
            and not self._pause_menu_open
            and not self._debug_menu_open
            and not self._console_open
        ):
            self.player.queue_jump()

    def _on_grapple_primary_down(self) -> None:
        if (
            self.player is None
            or self._mode != "game"
            or self._pause_menu_open
            or self._debug_menu_open
            or self._console_open
        ):
            return
        if not bool(self.tuning.grapple_enabled):
            return
        if self.player.is_grapple_attached():
            self.player.detach_grapple()
            return
        self._fire_grapple()

    def _view_direction(self) -> LVector3f:
        h = math.radians(float(self._yaw))
        p = math.radians(float(self._pitch))
        out = LVector3f(
            -math.sin(h) * math.cos(p),
            math.cos(h) * math.cos(p),
            math.sin(p),
        )
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out

    def _capture_demo_telemetry(self, *, cmd: _InputCommand) -> dict[str, float | int | bool]:
        """
        Capture per-tick telemetry for feel tuning.

        Replay still re-simulates from input commands only; telemetry is diagnostic.
        """

        if self.player is None:
            return {
                "t": float(globalClock.getFrameTime()),
                "yaw": float(self._yaw),
                "pitch": float(self._pitch),
                "inp_jp": bool(cmd.jump_pressed),
                "inp_jh": bool(cmd.jump_held),
                "inp_ch": bool(cmd.crouch_held),
                "inp_gp": bool(cmd.grapple_pressed),
                "inp_nt": bool(cmd.noclip_toggle_pressed),
                "inp_mf": int(cmd.move_forward),
                "inp_mr": int(cmd.move_right),
                "inp_kw": bool(cmd.key_w_held),
                "inp_ka": bool(cmd.key_a_held),
                "inp_ks": bool(cmd.key_s_held),
                "inp_kd": bool(cmd.key_d_held),
                "inp_au": bool(cmd.arrow_up_held),
                "inp_ad": bool(cmd.arrow_down_held),
                "inp_al": bool(cmd.arrow_left_held),
                "inp_ar": bool(cmd.arrow_right_held),
                "inp_m1": bool(cmd.mouse_left_held),
                "inp_m2": bool(cmd.mouse_right_held),
            }

        pos = self.player.pos
        vel = self.player.vel
        hspeed = math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y))
        speed = math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y) + float(vel.z) * float(vel.z))
        eye_height = float(self.tuning.player_eye_height)
        if bool(self.player.crouched) and bool(self.tuning.crouch_enabled):
            eye_height = min(eye_height, float(self.tuning.crouch_eye_height))
        return {
            "t": float(globalClock.getFrameTime()),
            "x": float(pos.x),
            "y": float(pos.y),
            "z": float(pos.z),
            "eye_z": float(pos.z + eye_height),
            "vx": float(vel.x),
            "vy": float(vel.y),
            "vz": float(vel.z),
            "hs": float(hspeed),
            "sp": float(speed),
            "yaw": float(self._yaw),
            "pitch": float(self._pitch),
            "grounded": bool(self.player.grounded),
            "crouched": bool(self.player.crouched),
            "grapple": bool(self.player.is_grapple_attached()),
            "noclip": bool(self.tuning.noclip_enabled),
            "inp_jp": bool(cmd.jump_pressed),
            "inp_jh": bool(cmd.jump_held),
            "inp_ch": bool(cmd.crouch_held),
            "inp_gp": bool(cmd.grapple_pressed),
            "inp_nt": bool(cmd.noclip_toggle_pressed),
            "inp_mf": int(cmd.move_forward),
            "inp_mr": int(cmd.move_right),
            "inp_kw": bool(cmd.key_w_held),
            "inp_ka": bool(cmd.key_a_held),
            "inp_ks": bool(cmd.key_s_held),
            "inp_kd": bool(cmd.key_d_held),
            "inp_au": bool(cmd.arrow_up_held),
            "inp_ad": bool(cmd.arrow_down_held),
            "inp_al": bool(cmd.arrow_left_held),
            "inp_ar": bool(cmd.arrow_right_held),
            "inp_m1": bool(cmd.mouse_left_held),
            "inp_m2": bool(cmd.mouse_right_held),
        }

    def _fire_grapple(self) -> None:
        if self.player is None or self.collision is None:
            return
        origin = LVector3f(self.camera.getPos(self.render))
        direction = self._view_direction()
        if direction.lengthSquared() <= 1e-12:
            return
        reach = max(8.0, float(self.tuning.grapple_fire_range))
        end = origin + direction * reach
        hit = self.collision.ray_closest(origin, end)
        if not hit.hasHit():
            return
        if hasattr(hit, "getHitPos"):
            anchor = LVector3f(hit.getHitPos())
        else:
            frac = max(0.0, min(1.0, float(hit.getHitFraction())))
            anchor = origin + (end - origin) * frac
        self.player.attach_grapple(anchor=anchor)

    @staticmethod
    def _build_grapple_rope_texture() -> Texture:
        return _grapple_rope.build_grapple_rope_texture()

    def _update_grapple_rope_visual(self) -> None:
        _grapple_rope.update_grapple_rope_visual(self)

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
        self._local_hp = 100
        self._net_reconcile_pos_offset = LVector3f(0, 0, 0)
        self._net_reconcile_yaw_offset = 0.0
        self._net_reconcile_pitch_offset = 0.0
        self._net_local_cam_ready = False
        self._sim_state_ready = False
        self._push_sim_snapshot()
        self._render_interpolated_state(alpha=1.0)
        # Recording starts from each spawn/respawn window.
        if not self._playback_active:
            self._start_new_demo_recording()

    def _on_respawn_pressed(self) -> None:
        if bool(getattr(self, "_playback_active", False)):
            self._stop_replay_playback(reason="Exited replay.")
            self._do_respawn(from_mode=True)
            return
        if self._net_connected and self._net_client is not None:
            self._net_client.send_respawn()
            self._net_pending_inputs.clear()
            self._net_predicted_states.clear()
            self._net_last_acked_seq = max(int(self._net_last_acked_seq), int(self._net_seq_counter))
            self._do_respawn(from_mode=True)
            self.ui.set_status("Respawn requested (waiting for server confirm).")
            return
        self._do_respawn(from_mode=False)

    def _toggle_noclip(self) -> None:
        self.tuning.noclip_enabled = not bool(self.tuning.noclip_enabled)

    def _step_noclip(self, *, dt: float, wish_dir: LVector3f, jump_held: bool, crouching: bool) -> None:
        if self.player is None:
            return
        up = 1.0 if jump_held else 0.0
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
            # Drain console output produced by background threads (MCP/control bridge) into the UI.
            try:
                if getattr(self, "_console_bus", None) is not None:
                    lines = self._console_bus.drain()
                    if lines:
                        self.console_ui.append(*lines)
            except Exception:
                pass

            if self._mode == "menu":
                if self.replay_input_ui.is_visible():
                    self.replay_input_ui.hide()
                self.ui.set_crosshair_visible(False)
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
                if self.replay_input_ui.is_visible():
                    self.replay_input_ui.hide()
                return Task.cont

            frame_dt = min(globalClock.getDt(), 0.25)
            now = float(globalClock.getFrameTime())
            if self._playback_active:
                if not self.replay_input_ui.is_visible():
                    self.replay_input_ui.show()
                # Replay must be driven only by recorded input frames.
                self._mouse_dx_accum = 0.0
                self._mouse_dy_accum = 0.0
                self._last_mouse = None
            else:
                if self.replay_input_ui.is_visible():
                    self.replay_input_ui.hide()
                self._poll_mouse_look_delta()

            if self.scene is not None:
                self.scene.tick(now=now)
            if self._replay_browser_open:
                self.replay_browser_ui.tick(now)

            menu_open = self._pause_menu_open or self._debug_menu_open or self._replay_browser_open or self._console_open
            self.ui.set_crosshair_visible(not menu_open)

            # Precompute wish from keyboard so debug overlay can show it even if movement seems dead.
            fwd_axis, right_axis = self._move_axes_from_keyboard()
            wish_dbg = self._wish_direction_from_axes(move_forward=fwd_axis, move_right=right_axis)

            if self.mouseWatcherNode is not None:
                self._feel_perf_text = self._feel_metrics.update_summary(now=now)
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
                    f"mode={self._mode} lock={self._pointer_locked} dt={frame_dt:.3f} hasMouse={has_mouse} mouse=({mx:+.2f},{my:+.2f})\n"
                    f"raw WASD={int(raw_w)}{int(raw_a)}{int(raw_s)}{int(raw_d)} ascii WASD={int(asc_w)}{int(asc_a)}{int(asc_s)}{int(asc_d)}\n"
                    f"wish=({wish_dbg.x:+.2f},{wish_dbg.y:+.2f}) pos=({pos.x:+.2f},{pos.y:+.2f},{pos.z:+.2f}) vel=({vel.x:+.2f},{vel.y:+.2f},{vel.z:+.2f}) grounded={int(grounded)}\n"
                    f"{self._net_perf_text if self._net_perf_text else 'net perf | waiting for samples...'}\n"
                    f"{self._feel_perf_text}"
                )
            if self._input_debug_until and globalClock.getFrameTime() >= self._input_debug_until:
                self._input_debug_until = 0.0
                self.input_debug.hide()

            self._sim_accumulator = min(0.25, self._sim_accumulator + frame_dt)
            self._poll_network_snapshot()
            while self._sim_accumulator >= self._sim_fixed_dt:
                cmd = (
                    self._sample_replay_input_command()
                    if self._playback_active
                    else self._sample_live_input_command(menu_open=menu_open)
                )
                self._simulate_input_tick(cmd=cmd, menu_open=menu_open)
                self._sim_accumulator -= self._sim_fixed_dt
            if self._net_connected:
                decay = math.exp(-max(0.0, float(self._net_reconcile_decay_hz)) * max(0.0, float(frame_dt)))
                self._net_reconcile_pos_offset *= float(decay)
                self._net_reconcile_yaw_offset *= float(decay)
                self._net_reconcile_pitch_offset *= float(decay)
            alpha = self._sim_accumulator / self._sim_fixed_dt if self._sim_fixed_dt > 0.0 else 1.0
            self._render_interpolated_state(alpha=alpha, frame_dt=frame_dt)
            self._render_remote_players(alpha=alpha)
            if self._net_connected:
                now_perf = float(time.monotonic())
                if self._net_perf_last_publish <= 0.0:
                    self._net_perf_last_publish = now_perf
                if (now_perf - float(self._net_perf_last_publish)) >= 1.0:
                    snap_mean_ms = (
                        (self._net_perf.snapshot_dt_sum / float(self._net_perf.snapshot_count)) * 1000.0
                        if self._net_perf.snapshot_count > 0
                        else 0.0
                    )
                    rec_mean = (
                        self._net_perf.reconcile_pos_err_sum / float(self._net_perf.reconcile_count)
                        if self._net_perf.reconcile_count > 0
                        else 0.0
                    )
                    replay_mean = (
                        self._net_perf.replay_time_sum_ms / float(self._net_perf.reconcile_count)
                        if self._net_perf.reconcile_count > 0
                        else 0.0
                    )
                    self._net_perf_text = (
                        "net perf | "
                        f"ack={self._net_last_acked_seq}/{self._net_seq_counter} "
                        f"pend={len(self._net_pending_inputs)} "
                        f"snap={snap_mean_ms:.1f}ms (max {self._net_perf.snapshot_dt_max * 1000.0:.1f}) "
                        f"corr={self._net_perf.reconcile_count} "
                        f"pos={rec_mean:.3f}m (max {self._net_perf.reconcile_pos_err_max:.3f}) "
                        f"replay={replay_mean:.2f}ms (max {self._net_perf.replay_time_max_ms:.2f}) "
                        f"steps={self._net_perf.replay_input_max}"
                    )
                    self._net_perf.reset()
                    self._net_perf_last_publish = now_perf

            hspeed = math.sqrt(self.player.vel.x * self.player.vel.x + self.player.vel.y * self.player.vel.y)
            self.ui.set_speed(hspeed)
            self.ui.set_health(self._local_hp)
            self.ui.set_status(
                f"speed: {hspeed:.2f} | z-vel: {self.player.vel.z:.2f} | grounded: {self.player.grounded} | "
                f"wall: {self.player.has_wall_for_jump()} | surf: {self.player.has_surf_surface()} | "
                f"grapple: {self.player.is_grapple_attached()} | hp: {self._local_hp} | net: {self._net_connected} | "
                f"rec: {self._active_recording is not None} | replay: {self._playback_active}"
            )

            if self._game_mode is not None:
                try:
                    self._game_mode.tick(now=now, player_pos=self.player.pos)
                except Exception as e:
                    self._handle_unhandled_error(context="mode.tick", exc=e)

            self._update_grapple_rope_visual()

            return Task.cont
        except Exception as e:
            self._handle_unhandled_error(context="update.loop", exc=e)
            return Task.cont

    def _update_menu_hold(self, *, now: float) -> None:
        _menu.update_menu_hold(self, now=now)

    def _is_crouching(self) -> bool:
        return self._is_key_down("c")

    def _smoke_exit(self, task: Task) -> int:
        self._smoke_frames -= 1
        if self._smoke_frames <= 0:
            self._write_smoke_screenshot()
            self.userExit()
            return Task.done
        return Task.cont

    def userExit(self, *args, **kwargs) -> None:  # type: ignore[override]
        try:
            if getattr(self, "console_control", None) is not None:
                try:
                    self.console_control.close()
                except Exception:
                    pass
        finally:
            super().userExit(*args, **kwargs)

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
    net_host: str | None = None,
    net_port: int = 7777,
    net_name: str = "player",
) -> None:
    app = RunnerDemo(
        RunConfig(
            smoke=smoke,
            smoke_screenshot=smoke_screenshot,
            map_json=map_json,
            hl_root=hl_root,
            hl_mod=hl_mod,
            net_host=net_host,
            net_port=int(net_port),
            net_name=net_name,
        )
    )
    app.run()
