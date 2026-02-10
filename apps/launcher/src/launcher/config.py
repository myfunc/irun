"""Persistent launcher settings stored at ~/.irun/launcher/config.json."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
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
    # Half-Life / Steam install root (optional, for resource import).
    hl_root: str = ""
    # Directory containing ericw-tools binaries (optional, for bake workflow).
    ericw_tools_dir: str = ""
    # Directory to scan for .map files.
    maps_dir: str = ""
    # Python executable used to run ivan / tools (defaults to sys.executable).
    python_exe: str = ""
    # Runtime launch profile for Play Map.
    play_map_profile: str = "dev-fast"
    # Enable --watch for Play Map.
    play_watch: bool = True
    # Pack pipeline profile.
    pack_profile: str = "dev-fast"
    # Bake pipeline profile.
    bake_profile: str = "prod-baked"
    # Optional bake flags.
    bake_no_vis: bool = False
    bake_no_light: bool = False
    bake_light_extra: bool = False
    bake_bounce: int = 0
    # Window geometry (persisted between sessions).
    window_width: int = 720
    window_height: int = 700

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
    checked — external tool paths (trenchbroom_exe, hl_root, ericw_tools_dir)
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
    return _sanitize_stale_paths(cfg)


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
