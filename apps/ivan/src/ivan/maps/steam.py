from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from ivan.maps.catalog import resolve_goldsrc_install_root


def _unescape_vdf_string(s: str) -> str:
    # libraryfolders.vdf commonly escapes backslashes for Windows paths.
    return s.replace("\\\\", "\\")


def parse_libraryfolders_vdf_paths(text: str) -> list[Path]:
    """
    Extract Steam library folder paths from `libraryfolders.vdf`.

    Supports both modern and older formats:
    - modern: `"path" "<dir>"`
    - older:  `"<digit>" "<dir>"`
    """

    out: list[Path] = []
    seen: set[str] = set()

    # 1) Modern: "path" "/some/dir"
    for m in re.finditer(r"\"path\"\s*\"([^\"]+)\"", text):
        raw = _unescape_vdf_string(m.group(1).strip())
        if not raw:
            continue
        key = raw.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(raw).expanduser())

    # 2) Older: "1" "/some/dir"
    for m in re.finditer(r"\"(\d+)\"\s*\"([^\"]+)\"", text):
        raw = _unescape_vdf_string(m.group(2).strip())
        if not raw:
            continue
        key = raw.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(raw).expanduser())

    return out


def default_steam_roots() -> list[Path]:
    home = Path.home()
    roots: list[Path] = []

    if sys.platform == "darwin":
        roots.append(home / "Library" / "Application Support" / "Steam")
        return roots

    if sys.platform.startswith("win"):
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            v = os.environ.get(env)
            if not v:
                continue
            roots.append(Path(v) / "Steam")
        return roots

    # Linux / other
    roots.append(home / ".steam" / "steam")
    roots.append(home / ".local" / "share" / "Steam")
    return roots


def steam_library_roots(steam_root: Path) -> list[Path]:
    """
    Return library roots (directories that contain `steamapps/`).
    """

    roots: list[Path] = []
    sr = Path(steam_root)
    if (sr / "steamapps").is_dir():
        roots.append(sr)

    vdf = sr / "steamapps" / "libraryfolders.vdf"
    if not vdf.exists():
        return roots

    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return roots

    for p in parse_libraryfolders_vdf_paths(text):
        # In some cases the VDF stores a library root; ensure it contains steamapps.
        if (p / "steamapps").is_dir():
            roots.append(p)

    # De-dupe while keeping order.
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        k = str(r).casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def detect_steam_halflife_game_root(*, steam_roots: list[Path] | None = None) -> Path | None:
    """
    Detect a Half-Life (GoldSrc) install under Steam and return a usable `game_root`
    for IVAN's importer (a directory that directly contains mod folders like `valve/`).
    """

    roots = steam_roots or default_steam_roots()
    game_names = ["Half-Life"]

    for steam_root in roots:
        for lib_root in steam_library_roots(steam_root):
            common = lib_root / "steamapps" / "common"
            if not common.is_dir():
                continue
            for name in game_names:
                install = common / name
                if not install.exists():
                    continue
                resolved = resolve_goldsrc_install_root(install)
                if resolved is not None and resolved.exists():
                    return resolved
    return None
