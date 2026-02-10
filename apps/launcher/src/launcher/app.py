"""Dear PyGui application – IVAN Launcher Toolbox."""

from __future__ import annotations

import re
import shutil
import threading
import time
from collections import deque
from pathlib import Path

import dearpygui.dearpygui as dpg

from launcher.actions import ProcessHandle, spawn_bake, spawn_game, spawn_pack, spawn_trenchbroom
from launcher.config import LauncherConfig, load_config, save_config
from launcher.map_browser import MapEntry, scan_maps

# ── global state ─────────────────────────────────────────────

_cfg: LauncherConfig = LauncherConfig()
_map_entries: list[MapEntry] = []
_selected_map: MapEntry | None = None
_processes: list[ProcessHandle] = []
_log_lines: deque[str] = deque(maxlen=3000)
_log_lock = threading.Lock()

# Tag constants for Dear PyGui items.
_TAG_LOG = "log_text"
_TAG_MAP_LIST = "map_listbox"
_TAG_SELECTED_LABEL = "selected_map_label"
_TAG_BTN_PLAY = "btn_play"
_TAG_BTN_PLAY_BAKED = "btn_play_baked"
_TAG_BTN_EDIT = "btn_edit"
_TAG_BTN_PACK = "btn_pack"
_TAG_BTN_BAKE = "btn_bake"
_TAG_BTN_STOP = "btn_stop"
_TAG_BTN_CREATE = "btn_create"
_TAG_BTN_LAUNCH = "btn_launch"

# Settings input tags.
_TAG_TB_EXE = "inp_tb_exe"
_TAG_WAD_DIR = "inp_wad_dir"
_TAG_MAT_DIR = "inp_mat_dir"
_TAG_HL_ROOT = "inp_hl_root"
_TAG_ERICW = "inp_ericw"
_TAG_MAPS_DIR = "inp_maps_dir"
_TAG_PYTHON = "inp_python"
_TAG_PLAY_PROFILE = "inp_play_profile"
_TAG_PLAY_WATCH = "inp_play_watch"
_TAG_PACK_PROFILE = "inp_pack_profile"
_TAG_BAKE_PROFILE = "inp_bake_profile"
_TAG_BAKE_NO_VIS = "inp_bake_no_vis"
_TAG_BAKE_NO_LIGHT = "inp_bake_no_light"
_TAG_BAKE_LIGHT_EXTRA = "inp_bake_light_extra"
_TAG_BAKE_BOUNCE = "inp_bake_bounce"

# Create map dialog tags.
_TAG_CREATE_DLG = "create_map_dlg"
_TAG_CREATE_NAME = "create_map_name"

# WAD import dialog tags.
_TAG_WAD_DLG = "wad_import_dlg"
_TAG_WAD_LIST_GROUP = "wad_list_group"
_TAG_WAD_STATUS = "wad_status_text"
_TAG_BTN_IMPORT_WAD = "btn_import_wad"

# Discovered WAD files for the import dialog.
_wad_candidates: list[Path] = []

# Label width for settings table (characters).
_LABEL_COL_WIDTH = 130
_PIPELINE_PROFILES = ("dev-fast", "prod-baked")


# ── minimal .map template ────────────────────────────────────

_MAP_TEMPLATE = (
    "// Game: IVAN\n"
    "// Format: Valve\n"
    "{\n"
    '"classname" "worldspawn"\n'
    '"mapversion" "220"\n'
    '"wad" ""\n'
    "{\n"
    "( -64 -64 -8 ) ( -64 64 -8 ) ( -64 64 8 ) __TB_empty [ 0 1 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
    "( 64 -64 -8 ) ( 64 64 -8 ) ( 64 64 8 ) __TB_empty [ 0 1 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
    "( -64 -64 -8 ) ( 64 -64 -8 ) ( 64 -64 8 ) __TB_empty [ 1 0 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
    "( -64 64 -8 ) ( 64 64 -8 ) ( 64 64 8 ) __TB_empty [ 1 0 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
    "( -64 -64 -8 ) ( 64 -64 -8 ) ( 64 64 -8 ) __TB_empty [ 1 0 0 0 ] [ 0 -1 0 0 ] 0 1 1\n"
    "( -64 -64 8 ) ( 64 -64 8 ) ( 64 64 8 ) __TB_empty [ 1 0 0 0 ] [ 0 -1 0 0 ] 0 1 1\n"
    "}\n"
    "}\n"
    "{\n"
    '"classname" "info_player_start"\n'
    '"origin" "0 0 32"\n'
    '"angle" "0"\n'
    "}\n"
)


# ── helpers ──────────────────────────────────────────────────


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    with _log_lock:
        _log_lines.append(f"[{ts}] {msg}")


def _flush_log() -> None:
    """Copy the shared log deque into the Dear PyGui multiline text widget."""
    with _log_lock:
        text = "\n".join(_log_lines)
    dpg.set_value(_TAG_LOG, text)
    # Auto-scroll to bottom.
    dpg.set_y_scroll("log_child", dpg.get_y_scroll_max("log_child"))


def _on_process_line(line: str) -> None:
    """Callback invoked from reader threads – thread-safe append."""
    _log(line)


def _refresh_maps() -> None:
    global _map_entries, _selected_map
    maps_dir = _cfg.effective_maps_dir()
    _map_entries = scan_maps(maps_dir)
    items = [f"{e.name}  ({e.age_label})" for e in _map_entries]
    dpg.configure_item(_TAG_MAP_LIST, items=items)
    if _map_entries and _selected_map is None:
        _select_map(0)
    elif _selected_map is not None:
        # Re-select the same map if it still exists.
        for i, e in enumerate(_map_entries):
            if e.path == _selected_map.path:
                dpg.set_value(_TAG_MAP_LIST, items[i] if items else "")
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
    has_ericw = bool(_cfg.ericw_tools_dir) and Path(_cfg.ericw_tools_dir).is_dir()
    game_running = any(p.alive and p.label == "IVAN Game" for p in _processes)

    dpg.configure_item(_TAG_BTN_PLAY, enabled=has_map and not game_running)
    baked_exists = bool(_selected_map is not None and _selected_map.path.with_suffix(".irunmap").is_file())
    if dpg.does_item_exist(_TAG_BTN_PLAY_BAKED):
        dpg.configure_item(_TAG_BTN_PLAY_BAKED, enabled=baked_exists and not game_running)
    dpg.configure_item(_TAG_BTN_LAUNCH, enabled=not game_running)
    dpg.configure_item(_TAG_BTN_EDIT, enabled=has_map and has_tb)
    dpg.configure_item(_TAG_BTN_PACK, enabled=has_map)
    dpg.configure_item(_TAG_BTN_BAKE, enabled=has_map and has_ericw)
    dpg.configure_item(_TAG_BTN_STOP, enabled=game_running)


def _sanitize_profile(raw: str, *, default: str) -> str:
    value = (raw or "").strip()
    if value in _PIPELINE_PROFILES:
        return value
    return default


def _profile_from_tag(tag: str, *, default: str) -> str:
    if not dpg.does_item_exist(tag):
        return default
    return _sanitize_profile(dpg.get_value(tag), default=default)


def _save_settings_from_ui() -> None:
    """Read current UI input values back into config and persist."""
    _cfg.trenchbroom_exe = dpg.get_value(_TAG_TB_EXE) or ""
    _cfg.wad_dir = dpg.get_value(_TAG_WAD_DIR) or ""
    _cfg.materials_dir = dpg.get_value(_TAG_MAT_DIR) or ""
    _cfg.hl_root = dpg.get_value(_TAG_HL_ROOT) or ""
    _cfg.ericw_tools_dir = dpg.get_value(_TAG_ERICW) or ""
    _cfg.maps_dir = dpg.get_value(_TAG_MAPS_DIR) or ""
    _cfg.python_exe = dpg.get_value(_TAG_PYTHON) or ""
    _cfg.play_map_profile = _profile_from_tag(_TAG_PLAY_PROFILE, default="dev-fast")
    _cfg.play_watch = bool(dpg.get_value(_TAG_PLAY_WATCH)) if dpg.does_item_exist(_TAG_PLAY_WATCH) else True
    _cfg.pack_profile = _profile_from_tag(_TAG_PACK_PROFILE, default="dev-fast")
    _cfg.bake_profile = _profile_from_tag(_TAG_BAKE_PROFILE, default="prod-baked")
    _cfg.bake_no_vis = bool(dpg.get_value(_TAG_BAKE_NO_VIS)) if dpg.does_item_exist(_TAG_BAKE_NO_VIS) else False
    _cfg.bake_no_light = bool(dpg.get_value(_TAG_BAKE_NO_LIGHT)) if dpg.does_item_exist(_TAG_BAKE_NO_LIGHT) else False
    _cfg.bake_light_extra = (
        bool(dpg.get_value(_TAG_BAKE_LIGHT_EXTRA)) if dpg.does_item_exist(_TAG_BAKE_LIGHT_EXTRA) else False
    )
    if dpg.does_item_exist(_TAG_BAKE_BOUNCE):
        try:
            _cfg.bake_bounce = max(0, int(dpg.get_value(_TAG_BAKE_BOUNCE)))
        except (TypeError, ValueError):
            _cfg.bake_bounce = 0
    save_config(_cfg)
    _log("Settings saved.")
    _update_buttons()


# ── file dialog callbacks ────────────────────────────────────

def _make_file_dialog(target_tag: str, *, directory: bool = False) -> None:
    """Open a native-ish file/folder picker and write result into *target_tag* input."""

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


# ── create map ───────────────────────────────────────────────

def _sanitize_map_name(raw: str) -> str:
    """Turn user input into a safe filename (lowercase, no spaces, no special chars)."""
    name = raw.strip().lower()
    name = re.sub(r"[^a-z0-9_\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "untitled"


def _cb_create_map_ok(sender, app_data) -> None:
    raw_name = dpg.get_value(_TAG_CREATE_NAME) or ""
    name = _sanitize_map_name(raw_name)
    if not name:
        return

    maps_dir = Path(_cfg.effective_maps_dir())
    map_dir = maps_dir / name
    map_file = map_dir / f"{name}.map"

    if map_file.exists():
        _log(f"Map already exists: {map_file}")
        dpg.configure_item(_TAG_CREATE_DLG, show=False)
        return

    try:
        map_dir.mkdir(parents=True, exist_ok=True)
        map_file.write_text(_MAP_TEMPLATE, encoding="utf-8")
    except OSError as exc:
        _log(f"Failed to create map: {exc}")
        dpg.configure_item(_TAG_CREATE_DLG, show=False)
        return

    _log(f"Created new map: {map_file}")
    dpg.configure_item(_TAG_CREATE_DLG, show=False)
    _refresh_maps()

    # Auto-select the new map.
    for i, e in enumerate(_map_entries):
        if e.path == map_file:
            _select_map(i)
            items = dpg.get_item_configuration(_TAG_MAP_LIST).get("items", [])
            if i < len(items):
                dpg.set_value(_TAG_MAP_LIST, items[i])
            break

    # Offer to open in TrenchBroom if configured.
    has_tb = bool(_cfg.trenchbroom_exe) and Path(_cfg.trenchbroom_exe).is_file()
    if has_tb and _selected_map is not None:
        _log(f"Opening {_selected_map.name} in TrenchBroom ...")
        h = spawn_trenchbroom(
            trenchbroom_exe=_cfg.trenchbroom_exe,
            map_path=str(_selected_map.path),
            on_line=_on_process_line,
        )
        _processes.append(h)


def _cb_create_map_cancel(sender, app_data) -> None:
    dpg.configure_item(_TAG_CREATE_DLG, show=False)


def _cb_create_map(sender, app_data) -> None:
    """Show the 'Create Map' name dialog."""
    dpg.set_value(_TAG_CREATE_NAME, "")
    dpg.configure_item(_TAG_CREATE_DLG, show=True)


# ── WAD import ────────────────────────────────────────────────

def _scan_wads_in_dir(root: Path) -> list[Path]:
    """Recursively find all .wad files under *root*."""
    if not root.is_dir():
        return []
    wads: list[Path] = []
    try:
        for p in root.rglob("*.wad"):
            if p.is_file():
                wads.append(p)
    except OSError:
        pass
    wads.sort(key=lambda w: w.name.lower())
    return wads


def _already_imported_wads() -> set[str]:
    """Return lowercase names of WAD files already in the textures directory."""
    tex_dir = Path(_cfg.effective_wad_dir())
    if not tex_dir.is_dir():
        return set()
    return {p.name.lower() for p in tex_dir.glob("*.wad") if p.is_file()}


def _rebuild_wad_checklist() -> None:
    """Populate the WAD import dialog with checkboxes for discovered WADs."""
    global _wad_candidates

    # Clear old children.
    if dpg.does_item_exist(_TAG_WAD_LIST_GROUP):
        dpg.delete_item(_TAG_WAD_LIST_GROUP, children_only=True)

    # Scan for WADs in common locations.
    search_dirs: list[Path] = []
    hl_root = _cfg.hl_root or (dpg.get_value(_TAG_HL_ROOT) if dpg.does_item_exist(_TAG_HL_ROOT) else "")
    if hl_root and Path(hl_root).is_dir():
        search_dirs.append(Path(hl_root))

    _wad_candidates = []
    for d in search_dirs:
        _wad_candidates.extend(_scan_wads_in_dir(d))

    # Deduplicate by absolute path.
    seen: set[str] = set()
    unique: list[Path] = []
    for w in _wad_candidates:
        key = str(w.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(w)
    _wad_candidates = unique

    already = _already_imported_wads()

    if not _wad_candidates:
        dpg.set_value(_TAG_WAD_STATUS, "No WAD files found. Set Steam/HL root in Settings, or use Browse.")
        return

    dpg.set_value(
        _TAG_WAD_STATUS,
        f"Found {len(_wad_candidates)} WAD file(s). Check the ones to import:",
    )

    for i, wad in enumerate(_wad_candidates):
        is_imported = wad.name.lower() in already
        label = wad.name
        if is_imported:
            label += "  (already imported)"
        dpg.add_checkbox(
            label=label,
            tag=f"_wad_cb_{i}",
            default_value=False,
            enabled=not is_imported,
            parent=_TAG_WAD_LIST_GROUP,
        )
        # Show the source path as a tooltip.
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(str(wad))


def _cb_import_wad(sender, app_data) -> None:
    """Show the WAD import dialog."""
    _save_settings_from_ui()
    _rebuild_wad_checklist()
    dpg.configure_item(_TAG_WAD_DLG, show=True)


def _cb_wad_import_ok(sender, app_data) -> None:
    """Copy checked WAD files to the textures directory."""
    tex_dir = Path(_cfg.effective_wad_dir())
    tex_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for i, wad in enumerate(_wad_candidates):
        cb_tag = f"_wad_cb_{i}"
        if dpg.does_item_exist(cb_tag) and dpg.get_value(cb_tag):
            dest = tex_dir / wad.name
            if dest.exists():
                _log(f"Skipped {wad.name} (already exists)")
                continue
            try:
                shutil.copy2(wad, dest)
                _log(f"Imported {wad.name} -> {dest}")
                count += 1
            except OSError as exc:
                _log(f"Failed to copy {wad.name}: {exc}")

    if count == 0:
        _log("No WAD files were imported (none selected or all already present).")
    else:
        _log(f"Imported {count} WAD file(s). Add them to your map in TrenchBroom (worldspawn 'wad' property).")

    dpg.configure_item(_TAG_WAD_DLG, show=False)


def _cb_wad_import_cancel(sender, app_data) -> None:
    dpg.configure_item(_TAG_WAD_DLG, show=False)


def _cb_wad_browse(sender, app_data) -> None:
    """Open a file picker for manually selecting WAD files to import."""

    def _callback(sender, app_data):
        selections = app_data.get("selections", {})
        if not selections:
            fp = app_data.get("file_path_name", "")
            if fp:
                selections = {"0": fp}

        tex_dir = Path(_cfg.effective_wad_dir())
        tex_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for path_str in selections.values():
            src = Path(path_str)
            if not src.is_file() or src.suffix.lower() != ".wad":
                continue
            dest = tex_dir / src.name
            if dest.exists():
                _log(f"Skipped {src.name} (already exists)")
                continue
            try:
                shutil.copy2(src, dest)
                _log(f"Imported {src.name} -> {dest}")
                count += 1
            except OSError as exc:
                _log(f"Failed to copy {src.name}: {exc}")

        if count > 0:
            _log(f"Imported {count} WAD file(s) via browse.")
        dpg.configure_item(_TAG_WAD_DLG, show=False)

    tag = "_dlg_wad_browse"
    if dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    with dpg.file_dialog(
        callback=_callback,
        tag=tag,
        show=True,
        width=600,
        height=400,
    ):
        dpg.add_file_extension(".wad", color=(0, 255, 0, 255))
        dpg.add_file_extension(".*")


# ── action callbacks ─────────────────────────────────────────


def _cb_play(sender, app_data) -> None:
    if _selected_map is None:
        return
    _save_settings_from_ui()
    play_profile = _sanitize_profile(_cfg.play_map_profile, default="dev-fast")
    watch_enabled = bool(_cfg.play_watch)
    _log(
        f"Launching IVAN with {_selected_map.name} "
        f"(profile={play_profile}, watch={'on' if watch_enabled else 'off'}) ..."
    )
    h = spawn_game(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=str(_selected_map.path),
        map_profile=play_profile,
        watch=watch_enabled,
        hl_root=_cfg.hl_root,
        on_line=_on_process_line,
    )
    _processes.append(h)
    _update_buttons()


def _cb_play_baked(sender, app_data) -> None:
    if _selected_map is None:
        return
    baked = _selected_map.path.with_suffix(".irunmap")
    if not baked.is_file():
        _log(f"Baked bundle not found: {baked}. Run Pack or Bake first.")
        _update_buttons()
        return
    _save_settings_from_ui()
    _log(f"Launching IVAN with baked bundle {baked.name} (profile=prod-baked) ...")
    h = spawn_game(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=str(baked),
        map_profile="prod-baked",
        watch=False,
        hl_root=_cfg.hl_root,
        on_line=_on_process_line,
    )
    _processes.append(h)
    _update_buttons()


def _cb_launch(sender, app_data) -> None:
    """Launch IVAN without a specific map (default graybox scene or main menu)."""
    _save_settings_from_ui()
    game_running = any(p.alive and p.label == "IVAN Game" for p in _processes)
    if game_running:
        return
    _log("Launching IVAN (no map) ...")
    h = spawn_game(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        hl_root=_cfg.hl_root,
        on_line=_on_process_line,
    )
    _processes.append(h)
    _update_buttons()


def _cb_stop(sender, app_data) -> None:
    for p in _processes:
        if p.label == "IVAN Game" and p.alive:
            p.kill()
            _log("Stopped IVAN game process.")
    _update_buttons()


def _cb_edit(sender, app_data) -> None:
    if _selected_map is None or not _cfg.trenchbroom_exe:
        return
    _save_settings_from_ui()
    _log(f"Opening {_selected_map.name} in TrenchBroom ...")
    h = spawn_trenchbroom(
        trenchbroom_exe=_cfg.trenchbroom_exe,
        map_path=str(_selected_map.path),
        on_line=_on_process_line,
    )
    _processes.append(h)


def _cb_pack(sender, app_data) -> None:
    if _selected_map is None:
        return
    _save_settings_from_ui()
    pack_profile = _sanitize_profile(_cfg.pack_profile, default="dev-fast")
    _log(f"Packing {_selected_map.name} -> .irunmap (profile={pack_profile}) ...")
    wad_dirs = [_cfg.effective_wad_dir()] if _cfg.effective_wad_dir() else []
    h = spawn_pack(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=str(_selected_map.path),
        profile=pack_profile,
        wad_dirs=wad_dirs,
        on_line=_on_process_line,
    )
    _processes.append(h)


def _cb_bake(sender, app_data) -> None:
    if _selected_map is None:
        return
    _save_settings_from_ui()
    if not _cfg.ericw_tools_dir:
        _log("Bake requires ericw-tools directory. Set it in Settings.")
        return
    if not _cfg.hl_root:
        _log("Bake requires Steam/HL root (game-root for textures). Set it in Settings.")
        return
    bake_profile = _sanitize_profile(_cfg.bake_profile, default="prod-baked")
    _log(
        f"Baking lightmaps for {_selected_map.name} "
        f"(profile={bake_profile}, no_vis={_cfg.bake_no_vis}, "
        f"no_light={_cfg.bake_no_light}, extra={_cfg.bake_light_extra}, bounce={_cfg.bake_bounce}) ..."
    )
    h = spawn_bake(
        python=_cfg.effective_python(),
        ivan_root=_cfg.effective_ivan_root(),
        map_path=str(_selected_map.path),
        profile=bake_profile,
        no_vis=bool(_cfg.bake_no_vis),
        no_light=bool(_cfg.bake_no_light),
        light_extra=bool(_cfg.bake_light_extra),
        bounce=max(0, int(_cfg.bake_bounce or 0)),
        ericw_tools_dir=_cfg.ericw_tools_dir,
        game_root=_cfg.hl_root,
        on_line=_on_process_line,
    )
    _processes.append(h)


def _cb_refresh(sender, app_data) -> None:
    _refresh_maps()
    _log("Map list refreshed.")


def _cb_clear_log(sender, app_data) -> None:
    with _log_lock:
        _log_lines.clear()
    dpg.set_value(_TAG_LOG, "")


def _cb_map_selected(sender, app_data) -> None:
    # app_data is the selected item string.
    items = dpg.get_item_configuration(_TAG_MAP_LIST).get("items", [])
    try:
        idx = items.index(app_data)
    except (ValueError, IndexError):
        idx = -1
    _select_map(idx)


def _cb_save_settings(sender, app_data) -> None:
    _save_settings_from_ui()


# ── tick / frame update ──────────────────────────────────────

_last_refresh_time: float = 0.0
_REFRESH_INTERVAL: float = 5.0  # seconds


def _frame_update() -> None:
    global _last_refresh_time

    # Flush process output into the log widget.
    for p in _processes:
        while p.log_lines:
            line = p.log_lines.popleft()
            with _log_lock:
                _log_lines.append(line)
    _flush_log()

    # Periodically refresh map list.
    now = time.time()
    if now - _last_refresh_time > _REFRESH_INTERVAL:
        _last_refresh_time = now
        _refresh_maps()

    # Clean up finished processes.
    for p in list(_processes):
        if not p.alive:
            rc = p.proc.returncode
            _log(f"{p.label} exited (code {rc}).")
            _processes.remove(p)
            _update_buttons()


# ── build UI ─────────────────────────────────────────────────


def _build_ui() -> None:
    # ── Create Map modal (hidden by default) ─────────
    with dpg.window(
        tag=_TAG_CREATE_DLG,
        label="Create New Map",
        modal=True,
        show=False,
        no_resize=True,
        width=360,
        height=120,
        pos=[180, 200],
    ):
        dpg.add_text("Map name (letters, digits, underscores):")
        dpg.add_input_text(tag=_TAG_CREATE_NAME, hint="e.g. my_first_map", width=-1)
        dpg.add_spacer(height=4)
        with dpg.group(horizontal=True):
            dpg.add_button(label="  Create  ", callback=_cb_create_map_ok)
            dpg.add_button(label="  Cancel  ", callback=_cb_create_map_cancel)

    # ── WAD Import modal (hidden by default) ────────
    with dpg.window(
        tag=_TAG_WAD_DLG,
        label="Import WAD Textures",
        modal=True,
        show=False,
        width=500,
        height=380,
        pos=[110, 80],
    ):
        dpg.add_text("", tag=_TAG_WAD_STATUS)
        dpg.add_spacer(height=4)
        with dpg.child_window(tag=_TAG_WAD_LIST_GROUP, height=240, horizontal_scrollbar=True):
            pass  # checkboxes are added dynamically
        dpg.add_spacer(height=6)
        with dpg.group(horizontal=True):
            dpg.add_button(label="  Import Selected  ", callback=_cb_wad_import_ok)
            dpg.add_button(label="  Browse...  ", callback=_cb_wad_browse)
            dpg.add_button(label="  Cancel  ", callback=_cb_wad_import_cancel)

    # ── Main window ──────────────────────────────────
    with dpg.window(tag="primary", label="IVAN Launcher"):

        # ── Settings (collapsible) ───────────────────
        with dpg.collapsing_header(label="Settings", default_open=False):
            with dpg.table(header_row=False, resizable=False,
                           borders_innerH=False, borders_outerH=False,
                           borders_innerV=False, borders_outerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=_LABEL_COL_WIDTH)
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=36)

                _settings_row("TrenchBroom exe", _TAG_TB_EXE, _cfg.trenchbroom_exe, directory=False)
                _settings_row("WAD directory", _TAG_WAD_DIR, _cfg.wad_dir, directory=True)
                _settings_row("Materials dir", _TAG_MAT_DIR, _cfg.materials_dir, directory=True)
                _settings_row("Steam/HL root", _TAG_HL_ROOT, _cfg.hl_root, directory=True)
                _settings_row("ericw-tools dir", _TAG_ERICW, _cfg.ericw_tools_dir, directory=True)
                _settings_row("Maps directory", _TAG_MAPS_DIR, _cfg.maps_dir, directory=True)
                _settings_row("Python exe", _TAG_PYTHON, _cfg.python_exe, directory=False)

            dpg.add_spacer(height=4)
            dpg.add_button(label="Save Settings", callback=_cb_save_settings)

        dpg.add_spacer(height=6)

        # ── Map Workspace ────────────────────────────
        with dpg.collapsing_header(label="Map Workspace", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_text("Maps in: " + _cfg.effective_maps_dir())
                dpg.add_button(label="Refresh", callback=_cb_refresh)
            dpg.add_listbox(
                tag=_TAG_MAP_LIST,
                items=[],
                num_items=8,
                callback=_cb_map_selected,
                width=-1,
            )
            dpg.add_text("No map selected", tag=_TAG_SELECTED_LABEL)

        dpg.add_spacer(height=6)

        # ── Workflow ──────────────────────────────────
        with dpg.collapsing_header(label="Workflow", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_button(label="  Play Map (quick)  ", tag=_TAG_BTN_PLAY, callback=_cb_play)
                dpg.add_button(label="  Play Baked (.irunmap)  ", tag=_TAG_BTN_PLAY_BAKED, callback=_cb_play_baked)
                dpg.add_button(label="  Stop Game  ", tag=_TAG_BTN_STOP, callback=_cb_stop)
                dpg.add_button(label="  Edit in TrenchBroom  ", tag=_TAG_BTN_EDIT, callback=_cb_edit)
            dpg.add_text("Quick path: Play Map loads source .map (fast iteration profile).")
            dpg.add_text("Baked path: Play Baked runs sibling .irunmap (build first via Pack/Bake).")

        dpg.add_spacer(height=4)

        # ── Pipeline Controls ─────────────────────────
        with dpg.collapsing_header(label="Pipeline Controls", default_open=True):
            dpg.add_text("Run profile:")
            with dpg.group(horizontal=True):
                dpg.add_text("Play profile:")
                dpg.add_combo(
                    _PIPELINE_PROFILES,
                    tag=_TAG_PLAY_PROFILE,
                    default_value=_sanitize_profile(_cfg.play_map_profile, default="dev-fast"),
                    width=140,
                )
                dpg.add_checkbox(tag=_TAG_PLAY_WATCH, label="watch (.map auto-reload)", default_value=bool(_cfg.play_watch))
            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_text("Pack profile:")
                dpg.add_combo(
                    _PIPELINE_PROFILES,
                    tag=_TAG_PACK_PROFILE,
                    default_value=_sanitize_profile(_cfg.pack_profile, default="dev-fast"),
                    width=140,
                )
                dpg.add_text("Bake profile:")
                dpg.add_combo(
                    _PIPELINE_PROFILES,
                    tag=_TAG_BAKE_PROFILE,
                    default_value=_sanitize_profile(_cfg.bake_profile, default="prod-baked"),
                    width=140,
                )
            dpg.add_spacer(height=4)
            dpg.add_text("Bake overrides:")
            with dpg.group(horizontal=True):
                dpg.add_checkbox(tag=_TAG_BAKE_NO_VIS, label="--no-vis", default_value=bool(_cfg.bake_no_vis))
                dpg.add_checkbox(tag=_TAG_BAKE_NO_LIGHT, label="--no-light", default_value=bool(_cfg.bake_no_light))
                dpg.add_checkbox(tag=_TAG_BAKE_LIGHT_EXTRA, label="--light-extra", default_value=bool(_cfg.bake_light_extra))
                dpg.add_text("bounce:")
                dpg.add_input_int(
                    tag=_TAG_BAKE_BOUNCE,
                    default_value=max(0, int(_cfg.bake_bounce)),
                    width=80,
                    min_value=0,
                    min_clamped=True,
                )
            dpg.add_text("Tip: prod-baked + no-light/no-vis off is the full lightmap bake path.")

        dpg.add_spacer(height=4)

        # ── Build & Export ────────────────────────────
        with dpg.collapsing_header(label="Build & Export", default_open=False):
            dpg.add_text("Recommended: compile/bake in your editor, then use Pack for distribution.")
            dpg.add_text("Pack: creates .irunmap from .map (profile from Pipeline Controls).")
            dpg.add_text("Bake Lightmaps button is optional CLI bake (advanced/legacy workflow).")
            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_button(label="  Pack .irunmap  ", tag=_TAG_BTN_PACK, callback=_cb_pack)
                dpg.add_button(label="  Bake Lightmaps (legacy)  ", tag=_TAG_BTN_BAKE, callback=_cb_bake)

        dpg.add_spacer(height=4)

        # ── Tools ────────────────────────────────────
        with dpg.collapsing_header(label="Tools", default_open=False):
            with dpg.group(horizontal=True):
                dpg.add_button(label="  Launch Game  ", tag=_TAG_BTN_LAUNCH, callback=_cb_launch)
                dpg.add_button(label="  Create Map  ", tag=_TAG_BTN_CREATE, callback=_cb_create_map)
                dpg.add_button(label="  Import WAD  ", tag=_TAG_BTN_IMPORT_WAD, callback=_cb_import_wad)

        dpg.add_spacer(height=6)

        # ── Log ──────────────────────────────────────
        with dpg.collapsing_header(label="Log", default_open=True):
            dpg.add_button(label="Clear", callback=_cb_clear_log)
            with dpg.child_window(tag="log_child", height=200, horizontal_scrollbar=True):
                dpg.add_text("", tag=_TAG_LOG, wrap=0)


def _settings_row(label: str, tag: str, default: str, *, directory: bool) -> None:
    """One table row: label | stretching text input | browse button."""
    with dpg.table_row():
        dpg.add_text(f"{label}:")
        dpg.add_input_text(tag=tag, default_value=default, width=-1)
        dpg.add_button(label="...", callback=lambda: _make_file_dialog(tag, directory=directory))


# ── main entry ───────────────────────────────────────────────


def run_launcher() -> None:
    global _cfg, _last_refresh_time

    _cfg = load_config()

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

    # Initial map scan.
    _last_refresh_time = time.time()
    _refresh_maps()
    _log("IVAN Launcher started.")

    # Main loop with per-frame update.
    while dpg.is_dearpygui_running():
        _frame_update()
        dpg.render_dearpygui_frame()

    # Cleanup: kill any lingering child processes.
    for p in _processes:
        p.kill()

    # Persist window size.
    try:
        vp_w = dpg.get_viewport_width()
        vp_h = dpg.get_viewport_height()
        if vp_w > 100 and vp_h > 100:
            _cfg.window_width = vp_w
            _cfg.window_height = vp_h
            save_config(_cfg)
    except Exception:
        pass

    dpg.destroy_context()
