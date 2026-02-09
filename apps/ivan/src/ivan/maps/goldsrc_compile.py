from __future__ import annotations

import shutil
from pathlib import Path


_TOOL_NAME_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Classic GoldSrc/VHLT naming.
    "hlcsg": ("hlcsg", "hlcsg_osx", "hlcsg_linux", "hlcsg.exe"),
    "hlbsp": ("hlbsp", "hlbsp_osx", "hlbsp_linux", "hlbsp.exe"),
    "hlvis": ("hlvis", "hlvis_osx", "hlvis_linux", "hlvis.exe"),
    "hlrad": ("hlrad", "hlrad_osx", "hlrad_linux", "hlrad.exe"),
}


def tool_name_candidates(tool: str) -> tuple[str, ...]:
    key = str(tool).strip().lower()
    if key not in _TOOL_NAME_CANDIDATES:
        raise ValueError(f"Unsupported GoldSrc compile tool: {tool}")
    return _TOOL_NAME_CANDIDATES[key]


def resolve_compile_tool(
    *,
    tool: str,
    explicit: Path | None,
    compile_bin: Path | None,
    game_root: Path | None,
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
    if game_root is not None:
        gr = game_root.expanduser().resolve()
        search_dirs.append(gr / "bin")
        search_dirs.append(gr)
        search_dirs.append(gr.parent / "bin")

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


def find_compiled_bsp(
    *,
    map_path: Path,
    game_root: Path | None,
    override_bsp_path: Path | None,
    started_at: float | None = None,
) -> Path | None:
    if override_bsp_path is not None:
        p = override_bsp_path.expanduser().resolve()
        if p.exists():
            return p

    stem = map_path.stem
    candidates = [
        map_path.with_suffix(".bsp"),
        map_path.parent / f"{stem}.bsp",
    ]
    if game_root is not None:
        gr = game_root.expanduser().resolve()
        candidates.extend(
            [
                gr / "maps" / f"{stem}.bsp",
                gr / f"{stem}.bsp",
            ]
        )

    existing: list[Path] = [p.resolve() for p in candidates if p.exists()]
    if not existing:
        return None

    if started_at is not None:
        recent = [p for p in existing if float(p.stat().st_mtime) >= float(started_at) - 2.0]
        if recent:
            return max(recent, key=lambda p: float(p.stat().st_mtime))

    return max(existing, key=lambda p: float(p.stat().st_mtime))
