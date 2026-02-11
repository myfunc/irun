"""Dear PyGui application - IVAN Launcher Toolbox."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

import dearpygui.dearpygui as dpg

from launcher.actions import ProcessHandle, spawn_game, spawn_pack, spawn_trenchbroom
from launcher.commands import CommandBus, EditMapCommand, PackMapCommand, PlayCommand, StopGameCommand
from launcher.config import LauncherConfig, load_config, save_config
from launcher.map_browser import MapEntry, scan_maps
from launcher.runflow import (
    AdvancedOverrides,
    resolve_launch_plan,
)

_cfg: LauncherConfig = LauncherConfig()
_map_entries: list[MapEntry] = []
_selected_map: MapEntry | None = None
_processes: list[ProcessHandle] = []
_log_lines: deque[str] = deque(maxlen=3000)
_log_lock = threading.Lock()

_TAG_LOG = "log_text"
_TAG_MAP_LIST = "map_listbox"
_TAG_SELECTED_LABEL = "selected_map_label"
_TAG_BTN_PLAY = "btn_play"
_TAG_BTN_PACK = "btn_pack"
_TAG_BTN_STOP = "btn_stop"
_TAG_BTN_EDIT = "btn_edit"

_TAG_TB_EXE = "inp_tb_exe"
_TAG_WAD_DIR = "inp_wad_dir"
_TAG_HL_ROOT = "inp_hl_root"
_TAG_MAPS_DIR = "inp_maps_dir"
_TAG_PYTHON = "inp_python"
_TAG_PLAY_WATCH = "inp_play_watch"
_TAG_PLAY_RUNTIME_LIGHTING = "inp_play_runtime_lighting"

_LABEL_COL_WIDTH = 130
_command_bus = CommandBus()


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    with _log_lock:
        _log_lines.append(f"[{ts}] {msg}")


def _flush_log() -> None:
    with _log_lock:
        text = "\n".join(_log_lines)
    dpg.set_value(_TAG_LOG, text)
    dpg.set_y_scroll("log_child", dpg.get_y_scroll_max("log_child"))


def _on_process_line(line: str) -> None:
    _log(line)


def _refresh_maps() -> None:
    global _map_entries, _selected_map
    _map_entries = scan_maps(_cfg.effective_maps_dir())
    items = [f"{entry.name}  ({entry.age_label})" for entry in _map_entries]
    dpg.configure_item(_TAG_MAP_LIST, items=items)
    if _map_entries and _selected_map is None:
        _select_map(0)
    elif _selected_map is not None:
        for idx, entry in enumerate(_map_entries):
            if entry.path == _selected_map.path:
                dpg.set_value(_TAG_MAP_LIST, items[idx] if items else "")
                break
    _update_buttons()


def _select_map(idx: int) -> None:
    global _selected_map
    if 0 <= idx < len(_map_entries):
        _selected_map = _map_entries[idx]
        dpg.set_value(_TAG_SELECTED_LABEL, f"Selected: {_selected_map.name}")
    else:
        _selected_map = None
        dpg.set_value(_TAG_SELECTED_LABEL, "No map selected")
    _update_buttons()


def _update_buttons() -> None:
    has_map = _selected_map is not None
    has_tb = bool(_cfg.trenchbroom_exe) and Path(_cfg.trenchbroom_exe).is_file()
    game_running = any(p.alive and p.label == "IVAN Game" for p in _processes)
    dpg.configure_item(_TAG_BTN_PLAY, enabled=has_map and not game_running)
    dpg.configure_item(_TAG_BTN_PACK, enabled=has_map)
    dpg.configure_item(_TAG_BTN_EDIT, enabled=has_map and has_tb)
    dpg.configure_item(_TAG_BTN_STOP, enabled=game_running)


def _save_settings_from_ui() -> None:
    _cfg.trenchbroom_exe = dpg.get_value(_TAG_TB_EXE) or ""
    _cfg.wad_dir = dpg.get_value(_TAG_WAD_DIR) or ""
    _cfg.hl_root = dpg.get_value(_TAG_HL_ROOT) or ""
    _cfg.maps_dir = dpg.get_value(_TAG_MAPS_DIR) or ""
    _cfg.python_exe = dpg.get_value(_TAG_PYTHON) or ""
    _cfg.play_watch = bool(dpg.get_value(_TAG_PLAY_WATCH)) if dpg.does_item_exist(_TAG_PLAY_WATCH) else True
    _cfg.play_runtime_lighting = (
        bool(dpg.get_value(_TAG_PLAY_RUNTIME_LIGHTING)) if dpg.does_item_exist(_TAG_PLAY_RUNTIME_LIGHTING) else False
    )
    save_config(_cfg)
    _log("Settings saved.")
    _update_buttons()


def _add_help_tooltip(text: str) -> None:
    with dpg.tooltip(dpg.last_item()):
        dpg.add_text(text, wrap=420)


def _make_file_dialog(target_tag: str, *, directory: bool = False) -> None:
    def _callback(sender, app_data):
        selections = app_data.get("selections", {})
        if selections:
            chosen = list(selections.values())[0]
        else:
            chosen = app_data.get("file_path_name", "")
        if chosen:
            dpg.set_value(target_tag, chosen)

    tag = f"_dlg_{target_tag}"
    if dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    with dpg.file_dialog(
        callback=_callback,
        tag=tag,
        directory_selector=directory,
        show=True,
        width=600,
        height=400,
    ):
        if not directory:
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".exe", color=(0, 255, 0, 255))


def _advanced_overrides_from_ui() -> AdvancedOverrides:
    return AdvancedOverrides(
        watch=bool(_cfg.play_watch),
        runtime_lighting=bool(_cfg.play_runtime_lighting),
    )


def _handle_play(cmd: PlayCommand) -> None:
    _save_settings_from_ui()
    try:
        plan = resolve_launch_plan(
            selected_map=_selected_map.path if _selected_map is not None else None,
            use_advanced=cmd.use_advanced,
            advanced=_advanced_overrides_from_ui(),
        )
    except ValueError as exc:
        _log(str(exc))
        _update_buttons()
        return

    _log(
        "Launching IVAN: "
        f"map={Path(plan.map_path).name}, profile={plan.map_profile}, "
        f"watch={'on' if plan.watch else 'off'}, runtime-lighting={'on' if plan.runtime_lighting else 'off'}"
    )
    handle = spawn_game(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=plan.map_path,
        map_profile=plan.map_profile,
        watch=plan.watch,
        runtime_lighting=plan.runtime_lighting,
        hl_root=_cfg.hl_root,
        on_line=_on_process_line,
    )
    _processes.append(handle)
    _update_buttons()


def _handle_stop_game(cmd: StopGameCommand) -> None:
    for process in _processes:
        if process.label == "IVAN Game" and process.alive:
            process.kill()
            _log("Stopped IVAN game process.")
    _update_buttons()


def _handle_pack_map(cmd: PackMapCommand) -> None:
    if _selected_map is None:
        return
    _save_settings_from_ui()
    pack_profile = "dev-fast"
    _log(f"Packing {_selected_map.name} -> .irunmap ...")
    wad_dirs = [_cfg.effective_wad_dir()] if _cfg.effective_wad_dir() else []
    handle = spawn_pack(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=str(_selected_map.path),
        profile=pack_profile,
        wad_dirs=wad_dirs,
        on_line=_on_process_line,
    )
    _processes.append(handle)


def _handle_edit_map(cmd: EditMapCommand) -> None:
    if _selected_map is None:
        return
    _save_settings_from_ui()
    if not _cfg.trenchbroom_exe or not Path(_cfg.trenchbroom_exe).is_file():
        _log("Set a valid TrenchBroom executable path in Settings.")
        _update_buttons()
        return
    _log(f"Opening {_selected_map.name} in TrenchBroom ...")
    handle = spawn_trenchbroom(
        trenchbroom_exe=_cfg.trenchbroom_exe,
        map_path=str(_selected_map.path),
        on_line=_on_process_line,
    )
    _processes.append(handle)
    _update_buttons()


def _dispatch(command: object) -> None:
    try:
        _command_bus.dispatch(command)
    except LookupError as exc:
        _log(str(exc))


def _cb_play(sender, app_data) -> None:
    _dispatch(PlayCommand(use_advanced=True))


def _cb_stop(sender, app_data) -> None:
    _dispatch(StopGameCommand())


def _cb_pack(sender, app_data) -> None:
    _dispatch(PackMapCommand())


def _cb_edit(sender, app_data) -> None:
    _dispatch(EditMapCommand())


def _cb_refresh(sender, app_data) -> None:
    _refresh_maps()
    _log("Map list refreshed.")


def _cb_clear_log(sender, app_data) -> None:
    with _log_lock:
        _log_lines.clear()
    dpg.set_value(_TAG_LOG, "")


def _cb_map_selected(sender, app_data) -> None:
    items = dpg.get_item_configuration(_TAG_MAP_LIST).get("items", [])
    try:
        idx = items.index(app_data)
    except (ValueError, IndexError):
        idx = -1
    _select_map(idx)


def _cb_save_settings(sender, app_data) -> None:
    _save_settings_from_ui()


_last_refresh_time: float = 0.0
_REFRESH_INTERVAL: float = 5.0


def _frame_update() -> None:
    global _last_refresh_time

    for process in _processes:
        while process.log_lines:
            line = process.log_lines.popleft()
            with _log_lock:
                _log_lines.append(line)
    _flush_log()

    now = time.time()
    if now - _last_refresh_time > _REFRESH_INTERVAL:
        _last_refresh_time = now
        _refresh_maps()

    for process in list(_processes):
        if not process.alive:
            _log(f"{process.label} exited (code {process.proc.returncode}).")
            _processes.remove(process)
            _update_buttons()


def _build_ui() -> None:
    with dpg.window(tag="primary", label="IVAN Launcher"):
        with dpg.collapsing_header(label="Settings", default_open=False):
            with dpg.table(
                header_row=False,
                resizable=False,
                borders_innerH=False,
                borders_outerH=False,
                borders_innerV=False,
                borders_outerV=False,
            ):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=_LABEL_COL_WIDTH)
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=36)
                _settings_row("TrenchBroom exe", _TAG_TB_EXE, _cfg.trenchbroom_exe, directory=False)
                _settings_row("WAD directory", _TAG_WAD_DIR, _cfg.wad_dir, directory=True)
                _settings_row("Steam/HL root", _TAG_HL_ROOT, _cfg.hl_root, directory=True)
                _settings_row("Maps directory", _TAG_MAPS_DIR, _cfg.maps_dir, directory=True)
                _settings_row("Python exe", _TAG_PYTHON, _cfg.python_exe, directory=False)
            dpg.add_spacer(height=4)
            dpg.add_button(label="Save Settings", callback=_cb_save_settings)

        dpg.add_spacer(height=6)
        with dpg.collapsing_header(label="Map Browser", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_text("Maps in: " + _cfg.effective_maps_dir())
                dpg.add_button(label="Refresh", callback=_cb_refresh)
            dpg.add_listbox(tag=_TAG_MAP_LIST, items=[], num_items=8, callback=_cb_map_selected, width=-1)
            dpg.add_text("No map selected", tag=_TAG_SELECTED_LABEL)

        dpg.add_spacer(height=6)
        with dpg.collapsing_header(label="Runflow", default_open=True):
            dpg.add_text("1) Choose map, 2) launch.")
            dpg.add_text("- One runtime path only: source .map + runtime lighting support.")
            dpg.add_text("- Map lights and skybox are resolved at runtime (no launcher bake flow).")

        dpg.add_spacer(height=4)
        with dpg.collapsing_header(label="Primary Actions", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_button(label="  Launch  ", tag=_TAG_BTN_PLAY, callback=_cb_play)
                _add_help_tooltip("Launch selected .map with runtime-first options.")
                dpg.add_button(label="  Edit in TrenchBroom  ", tag=_TAG_BTN_EDIT, callback=_cb_edit)
                _add_help_tooltip("Open selected .map in TrenchBroom.")
                dpg.add_button(label="  Pack  ", tag=_TAG_BTN_PACK, callback=_cb_pack)
                _add_help_tooltip("Build selected .map into sibling .irunmap.")
                dpg.add_button(label="  Stop Game  ", tag=_TAG_BTN_STOP, callback=_cb_stop)
                _add_help_tooltip("Terminate the active IVAN game process from this launcher.")

        dpg.add_spacer(height=4)
        with dpg.collapsing_header(label="Launch + Pack Options", default_open=False):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(tag=_TAG_PLAY_WATCH, label="watch (.map auto-reload)", default_value=bool(_cfg.play_watch))
                dpg.add_checkbox(
                    tag=_TAG_PLAY_RUNTIME_LIGHTING,
                    label="runtime lighting",
                    default_value=bool(_cfg.play_runtime_lighting),
                )
            dpg.add_text("Pack uses dev-fast profile by default.")

        dpg.add_spacer(height=6)
        with dpg.collapsing_header(label="Log", default_open=True):
            dpg.add_button(label="Clear", callback=_cb_clear_log)
            with dpg.child_window(tag="log_child", height=200, horizontal_scrollbar=True):
                dpg.add_text("", tag=_TAG_LOG, wrap=0)


def _settings_row(label: str, tag: str, default: str, *, directory: bool) -> None:
    with dpg.table_row():
        dpg.add_text(f"{label}:")
        dpg.add_input_text(tag=tag, default_value=default, width=-1)
        dpg.add_button(label="...", callback=lambda: _make_file_dialog(tag, directory=directory))


def run_launcher() -> None:
    global _cfg, _last_refresh_time
    _cfg = load_config()
    _command_bus.register(PlayCommand, _handle_play)
    _command_bus.register(StopGameCommand, _handle_stop_game)
    _command_bus.register(PackMapCommand, _handle_pack_map)
    _command_bus.register(EditMapCommand, _handle_edit_map)

    dpg.create_context()
    dpg.create_viewport(
        title="IVAN Launcher",
        width=_cfg.window_width,
        height=_cfg.window_height,
        min_width=500,
        min_height=400,
    )
    _build_ui()
    dpg.setup_dearpygui()
    dpg.set_primary_window("primary", True)
    dpg.show_viewport()

    _last_refresh_time = time.time()
    _refresh_maps()
    _log("IVAN Launcher started.")

    while dpg.is_dearpygui_running():
        _frame_update()
        dpg.render_dearpygui_frame()

    for process in _processes:
        process.kill()

    try:
        width = dpg.get_viewport_width()
        height = dpg.get_viewport_height()
        if width > 100 and height > 100:
            _cfg.window_width = width
            _cfg.window_height = height
            save_config(_cfg)
    except Exception:
        pass

    dpg.destroy_context()
