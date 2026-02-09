from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


_TOOL_NAME_CANDIDATES: dict[str, tuple[str, ...]] = {
    "vbsp": ("vbsp", "vbsp_osx", "vbsp_linux", "vbsp.exe"),
    "vvis": ("vvis", "vvis_osx", "vvis_linux", "vvis.exe"),
    "vrad": ("vrad", "vrad_osx", "vrad_linux", "vrad.exe"),
}

_MAP_ASSET_DIRS = ("materials", "models", "sound", "resource", "scripts")


def tool_name_candidates(tool: str) -> tuple[str, ...]:
    key = str(tool).strip().lower()
    if key not in _TOOL_NAME_CANDIDATES:
        raise ValueError(f"Unsupported Source compile tool: {tool}")
    return _TOOL_NAME_CANDIDATES[key]


def resolve_compile_tool(
    *,
    tool: str,
    explicit: Path | None,
    compile_bin: Path | None,
    fallback_game_root: Path | None,
) -> Path | None:
    names = tool_name_candidates(tool)

    if explicit is not None:
        p = explicit.expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Explicit {tool} path does not exist: {p}")

    search_dirs: list[Path] = []
    if compile_bin is not None:
        search_dirs.append(compile_bin.expanduser().resolve())
    if fallback_game_root is not None:
        gr = fallback_game_root.expanduser().resolve()
        search_dirs.append(gr / "bin")
        search_dirs.append(gr)
        parent = gr.parent
        search_dirs.append(parent / "bin")
        search_dirs.append(parent / "game" / "bin")

    for d in search_dirs:
        for nm in names:
            p = (d / nm).resolve()
            if p.exists():
                return p

    for nm in names:
        found = shutil.which(nm)
        if found:
            return Path(found).resolve()
    return None


def create_temp_source_game_root(*, vmf_dir: Path, fallback_game_root: Path | None) -> Path:
    """
    Build an isolated Source game root for compilation.

    This keeps VMF-local assets (materials/models/...) visible to the compiler without mutating
    a real game install. If `fallback_game_root` is provided, we add it to SearchPaths.
    """

    root = Path(tempfile.mkdtemp(prefix="ivan-source-compile-")).resolve()
    (root / "maps").mkdir(parents=True, exist_ok=True)

    for folder in _MAP_ASSET_DIRS:
        src = (vmf_dir / folder).resolve()
        if not src.exists():
            continue
        dst = root / folder
        if dst.exists():
            continue
        try:
            dst.symlink_to(src, target_is_directory=src.is_dir())
        except Exception:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    search_paths = ['\t\t\tGame\t\t"|gameinfo_path|."']
    if fallback_game_root is not None:
        search_paths.append(f'\t\t\tGame\t\t"{fallback_game_root.resolve().as_posix()}"')

    gameinfo = (
        '"GameInfo"\n'
        "{\n"
        '\tgame\t\t"IVAN VMF Import Temp"\n'
        '\ttitle\t\t"IVAN VMF Import Temp"\n'
        "\tFileSystem\n"
        "\t{\n"
        "\t\tSearchPaths\n"
        "\t\t{\n"
        + "\n".join(search_paths)
        + "\n"
        "\t\t}\n"
        "\t}\n"
        "}\n"
    )
    (root / "gameinfo.txt").write_text(gameinfo, encoding="utf-8")
    return root


def find_compiled_bsp(
    *,
    vmf_path: Path,
    compile_game_root: Path,
    override_bsp_path: Path | None,
    started_at: float | None = None,
) -> Path | None:
    if override_bsp_path is not None:
        p = override_bsp_path.expanduser().resolve()
        if p.exists():
            return p

    stem = vmf_path.stem
    candidates = [
        vmf_path.with_suffix(".bsp"),
        vmf_path.parent / f"{stem}.bsp",
        compile_game_root / "maps" / f"{stem}.bsp",
        compile_game_root / "mapsrc" / f"{stem}.bsp",
    ]

    existing: list[Path] = [p.resolve() for p in candidates if p.exists()]
    if not existing:
        return None

    if started_at is not None:
        recent = [p for p in existing if float(p.stat().st_mtime) >= float(started_at) - 2.0]
        if recent:
            return max(recent, key=lambda p: float(p.stat().st_mtime))

    return max(existing, key=lambda p: float(p.stat().st_mtime))

