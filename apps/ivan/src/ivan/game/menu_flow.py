from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import KeyboardButton

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT
from ivan.paths import app_root as ivan_app_root
from ivan.state import update_state
from ivan.ui.main_menu import ImportRequest, MainMenuController


def enter_main_menu(host) -> None:
    host._mode = "menu"
    host._menu_hold_dir = 0
    host._pause_menu_open = False
    host._debug_menu_open = False
    host._replay_browser_open = False
    host._console_open = False
    host._feel_capture_open = False
    host._awaiting_noclip_rebind = False
    host._active_recording = None
    host._playback_active = False
    host._playback_frames = None
    host._playback_index = 0
    if host._net_client is not None:
        try:
            host._net_client.close()
        except Exception:
            pass
    host._net_client = None
    host._net_connected = False
    host._net_player_id = 0
    host._clear_remote_players()
    host._stop_embedded_server()
    host._set_pointer_lock(False)

    # Hide in-game HUD while picking.
    host.ui.set_speed_hud_visible(False)
    host.ui.set_crosshair_visible(False)
    host._grapple_rope_np.hide()
    host.ui.hide()
    host.pause_ui.hide()
    try:
        host.feel_capture_ui.hide()
    except Exception:
        pass
    host.replay_browser_ui.hide()
    try:
        host.console_ui.hide()
    except Exception:
        pass

    host._menu = MainMenuController(
        aspect2d=host.aspect2d,
        theme=host.ui_theme,
        initial_game_root=host.cfg.hl_root,
        initial_mod=host.cfg.hl_mod if host.cfg.hl_root else None,
        on_start_map_json=host._start_game,
        on_import_bsp=host._start_import_from_request,
        on_quit=host.userExit,
        on_apply_video=host._apply_video_settings,
    )


def back_to_menu(host) -> None:
    if host._mode != "game":
        return
    if host._importing:
        return
    host._teardown_game_mode()

    # Tear down active world state so returning to menu doesn't leak nodes/state.
    host.scene = None
    host.collision = None
    host.player = None
    try:
        host.world_root.removeNode()
    except Exception:
        pass
    host.world_root = host.render.attachNewNode("world-root")

    host.input_debug.hide()
    host._grapple_rope_np.hide()
    host.ui.hide()
    host.pause_ui.hide()
    host.replay_browser_ui.hide()
    try:
        host.feel_capture_ui.hide()
    except Exception:
        pass
    try:
        host.console_ui.hide()
    except Exception:
        pass
    host._replay_browser_open = False
    host._console_open = False
    host._feel_capture_open = False
    host._playback_active = False
    host._clear_remote_players()
    if host._net_client is not None:
        try:
            host._net_client.close()
        except Exception:
            pass
    host._net_client = None
    host._net_connected = False
    host._net_player_id = 0
    host._stop_embedded_server()

    enter_main_menu(host)


def menu_toggle_search(host) -> None:
    if host._mode == "menu" and host._menu is not None and not host._importing:
        host._menu.toggle_search()


def menu_nav_press(host, dir01: int) -> None:
    if host._mode == "game" and host._replay_browser_open:
        d = -1 if dir01 < 0 else 1
        host.replay_browser_ui.move(d)
        return
    if host._mode != "menu" or host._menu is None or host._importing:
        return
    if host._menu.is_search_active():
        return
    now = float(globalClock.getFrameTime())
    d = -1 if dir01 < 0 else 1
    if host._menu_hold_dir != d:
        host._menu_hold_dir = d
        host._menu_hold_since = now
        host._menu_hold_next = now + 0.28
    host._safe_call("menu.move", lambda: host._menu.move(d))


def menu_nav_release(host, dir01: int) -> None:
    d = -1 if dir01 < 0 else 1
    if host._menu_hold_dir == d:
        host._menu_hold_dir = 0


def menu_page(host, dir01: int) -> None:
    if host._mode == "game" and host._replay_browser_open:
        d = -1 if dir01 < 0 else 1
        host.replay_browser_ui.move(d * 10)
        return
    if host._mode != "menu" or host._menu is None or host._importing:
        return
    if host._menu.is_search_active():
        return
    d = -1 if dir01 < 0 else 1
    shift = False
    try:
        if host.mouseWatcherNode is not None:
            shift = bool(host.mouseWatcherNode.isButtonDown(KeyboardButton.shift()))
    except Exception:
        shift = False
    jump = 20 if shift else 10
    host._safe_call("menu.page", lambda: host._menu.move(d * jump))


def menu_select(host) -> None:
    if host._mode == "game" and host._replay_browser_open:
        host.replay_browser_ui.on_enter()
        return
    if host._mode != "menu" or host._menu is None or host._importing:
        return
    host._safe_call("menu.enter", host._menu.on_enter)


def menu_delete(host) -> None:
    if host._mode != "menu" or host._menu is None or host._importing:
        return
    host._safe_call("menu.delete", host._menu.on_delete)


def update_menu_hold(host, *, now: float) -> None:
    if host._menu_hold_dir == 0 or host._menu is None or host._importing:
        return
    if host._menu.is_search_active():
        return
    if now < host._menu_hold_next:
        return

    t = max(0.0, now - host._menu_hold_since)
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

    d = host._menu_hold_dir * step
    host._safe_call("menu.hold", lambda: host._menu.move(d))
    host._menu_hold_next = now + interval


def start_import_from_request(host, req: ImportRequest) -> None:
    update_state(last_game_root=req.game_root, last_mod=req.mod)

    app_root = ivan_app_root()
    # Default to a packed bundle so imported maps don't create huge file trees in git.
    out_ref = app_root / "assets" / "imported" / "halflife" / req.mod / f"{req.map_label}{PACKED_BUNDLE_EXT}"
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
        str(out_ref),
        "--map-id",
        req.map_label,
        "--scale",
        "0.03",
    ]

    host._importing = True
    host._import_error = None
    host._pending_map_json = None
    if host._menu is not None:
        host._menu.set_loading_status(f"Importing {req.map_label}", started_at=globalClock.getFrameTime())

    def worker() -> None:
        try:
            out_ref.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()
                # Prefer the last non-empty line (usually the exception), but keep a short tail for context.
                if err:
                    lines = [line for line in err.splitlines() if line.strip()]
                    tail = "\n".join(lines[-6:]) if lines else err
                    host._import_error = tail[-800:]
                else:
                    host._import_error = f"Importer failed with code {proc.returncode}"
                return
            # Importer writes either:
            # - <out-dir>/map.json  (directory bundle)
            # - <out>.irunmap       (packed bundle)
            host._pending_map_json = str(out_ref)
        except Exception as e:
            host._import_error = str(e)
        finally:
            host._importing = False

    host._import_thread = threading.Thread(target=worker, daemon=True)
    host._import_thread.start()


__all__ = [
    "back_to_menu",
    "enter_main_menu",
    "menu_delete",
    "menu_nav_press",
    "menu_nav_release",
    "menu_page",
    "menu_select",
    "menu_toggle_search",
    "start_import_from_request",
    "update_menu_hold",
]
