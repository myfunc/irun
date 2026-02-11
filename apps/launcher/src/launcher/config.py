"""Persistent launcher settings stored at ~/.irun/launcher/config.json."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path


def _repo_root() -> Path:
    """Best-effort repo root: five levels up from this file (config.py -> launcher/ -> src/ -> apps/launcher/ -> apps/ -> repo)."""
    return Path(__file__).resolve().parents[4]


def _default_ivan_root() -> str:
    return str(_repo_root() / "apps" / "ivan")


def _default_maps_dir() -> str:
    return str(Path(_default_ivan_root()) / "assets" / "maps")


def _default_wad_dir() -> str:
    return str(Path(_default_ivan_root()) / "assets" / "textures")


def _default_materials_dir() -> str:
    return str(Path(_default_ivan_root()) / "assets" / "materials")


@dataclass
class LauncherConfig:
    """All user-configurable launcher settings.  Empty strings mean 'not set'."""

    # Path to the TrenchBroom executable.
    trenchbroom_exe: str = ""
    # Directory containing WAD files (TrenchBroom + engine).
    wad_dir: str = ""
    # Directory containing .material.json PBR definitions.
    materials_dir: str = ""
    # Half-Life / Steam install root (optional, for resource lookup at runtime).
    hl_root: str = ""
    # Directory to scan for .map files.
    maps_dir: str = ""
    # Python executable used to run ivan / tools (defaults to sys.executable).
    python_exe: str = ""
    # Enable --watch for Play Map.
    play_watch: bool = True
    # Force runtime lighting at launch.
    play_runtime_lighting: bool = False
    # Window geometry (persisted between sessions).
    window_width: int = 720
    window_height: int = 700
    # Window position (x_pos, y_pos). -99999 means "not set" (use default).
    window_x: int = -99999
    window_y: int = -99999

    # ── helpers ──────────────────────────────────────────────

    def effective_maps_dir(self) -> str:
        return self.maps_dir or _default_maps_dir()

    def effective_wad_dir(self) -> str:
        return self.wad_dir or _default_wad_dir()

    def effective_materials_dir(self) -> str:
        return self.materials_dir or _default_materials_dir()

    def effective_ivan_root(self) -> str:
        return _default_ivan_root()

    def effective_python(self) -> str:
        if self.python_exe and Path(self.python_exe).is_file():
            return self.python_exe
        import sys
        return sys.executable

    def has_valid_window_position(self) -> bool:
        """True if window_x/window_y are set and in valid range (not sentinel)."""
        return (
            self.window_x != _WINDOW_POS_SENTINEL
            and self.window_y != _WINDOW_POS_SENTINEL
        )


# ── persistence ──────────────────────────────────────────────


def _config_dir() -> Path:
    override = os.environ.get("IRUN_LAUNCHER_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".irun" / "launcher"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def _sanitize_stale_paths(cfg: LauncherConfig) -> LauncherConfig:
    """Clear project-internal paths that point to non-existent directories.

    This prevents stale absolute paths (e.g. from a moved/renamed repo clone)
    from silently breaking the launcher.  Only project-internal fields are
    checked — external tool paths (trenchbroom_exe, hl_root)
    are left as-is because they may be temporarily unavailable (USB drive, etc.).
    """
    _DIR_FIELDS = ("maps_dir", "wad_dir", "materials_dir")
    changed = False
    for field_name in _DIR_FIELDS:
        val = getattr(cfg, field_name, "")
        if val and not Path(val).is_dir():
            setattr(cfg, field_name, "")
            changed = True
    # python_exe: clear if the file doesn't exist.
    if cfg.python_exe and not Path(cfg.python_exe).is_file():
        cfg.python_exe = ""
        changed = True
    if changed:
        import logging
        logging.getLogger(__name__).warning(
            "Cleared stale project paths from launcher config (repo moved?)."
        )
    return cfg


_WINDOW_POS_SENTINEL = -99999
_WINDOW_POS_MIN = -10000
_WINDOW_POS_MAX = 10000
_WINDOW_WIDTH_MIN = 500
_WINDOW_WIDTH_MAX = 10000
_WINDOW_HEIGHT_MIN = 400
_WINDOW_HEIGHT_MAX = 10000


def _sanitize_window_geometry(cfg: LauncherConfig) -> LauncherConfig:
    """Clamp window size/position to valid ranges.  Invalid values reset to defaults."""
    if not (_WINDOW_WIDTH_MIN <= cfg.window_width <= _WINDOW_WIDTH_MAX):
        cfg.window_width = 720
    if not (_WINDOW_HEIGHT_MIN <= cfg.window_height <= _WINDOW_HEIGHT_MAX):
        cfg.window_height = 700
    if not (_WINDOW_POS_MIN <= cfg.window_x <= _WINDOW_POS_MAX):
        cfg.window_x = _WINDOW_POS_SENTINEL
    if not (_WINDOW_POS_MIN <= cfg.window_y <= _WINDOW_POS_MAX):
        cfg.window_y = _WINDOW_POS_SENTINEL
    return cfg


def load_config() -> LauncherConfig:
    p = _config_path()
    if not p.exists():
        return LauncherConfig()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return LauncherConfig()
    if not isinstance(raw, dict):
        return LauncherConfig()

    kwargs: dict = {}
    for fld in LauncherConfig.__dataclass_fields__:
        if fld in raw:
            val = raw[fld]
            # Coerce types to match field annotations.
            ann = LauncherConfig.__dataclass_fields__[fld].type
            if ann == "bool":
                if isinstance(val, bool):
                    kwargs[fld] = val
                elif isinstance(val, (int, float)):
                    kwargs[fld] = bool(val)
                elif isinstance(val, str):
                    kwargs[fld] = val.strip().lower() in ("1", "true", "yes", "on")
            elif ann == "int" and isinstance(val, (int, float)):
                kwargs[fld] = int(val)
            elif isinstance(val, str):
                kwargs[fld] = val
            elif isinstance(val, (int, float)):
                kwargs[fld] = int(val)
    cfg = LauncherConfig(**kwargs)
    cfg = _sanitize_stale_paths(cfg)
    return _sanitize_window_geometry(cfg)


def save_config(cfg: LauncherConfig) -> None:
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = _config_path()
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    tmp.write_text(
        json.dumps(asdict(cfg), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)
