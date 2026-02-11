"""Bake pipeline: compile a .map file with ericw-tools and import the resulting BSP.

Runs qbsp, vis (optional), and light (optional) on a Quake-family .map file,
then feeds the compiled BSP through the existing GoldSrc importer to produce
an IVAN .irunmap bundle with production-quality lightmaps.

Usage::

    python tools/bake_map.py \\
        --map path/to/mymap.map \\
        --output path/to/output.irunmap \\
        --ericw-tools /path/to/ericw-tools/bin \\
        --scale 0.03 \\
        --game-root path/to/game/assets \\
        [--profile dev-fast|prod-baked] \\
        [--no-vis] \\
        [--no-light] \\
        [--light-extra] \\
        [--bounce N] \\
        [--dir-bundle]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# The GoldSrc importer can be invoked as a subprocess (it lives outside the
# normal package hierarchy) or imported directly when ``sys.path`` is set up.
# We keep both options so this script works standalone.
# ---------------------------------------------------------------------------

_TOOLS_DIR = Path(__file__).resolve().parent
_GOLDSRC_IMPORTER = _TOOLS_DIR / "importers" / "goldsrc" / "import_goldsrc_bsp.py"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from pipeline_profiles import (  # noqa: E402
    PROFILE_DEV_FAST,
    add_profile_argument,
    get_profile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_windows() -> bool:
    return platform.system() == "Windows"


def _exe_suffix() -> str:
    return ".exe" if _is_windows() else ""


def _find_binary(ericw_dir: Path, name: str) -> Path | None:
    """Locate an ericw-tools binary inside *ericw_dir*."""
    candidate = ericw_dir / f"{name}{_exe_suffix()}"
    if candidate.is_file():
        return candidate
    # Some distributions nest binaries inside a ``bin/`` subdirectory.
    candidate = ericw_dir / "bin" / f"{name}{_exe_suffix()}"
    if candidate.is_file():
        return candidate
    return None


def _find_first_binary(root: Path, names: list[str]) -> Path | None:
    for n in names:
        p = _find_binary(root, n)
        if p is not None:
            return p
    return None


def _supports_game_flag(tool_path: Path) -> bool:
    """
    Detect compiler families that accept `-game`.

    SDHLT tools usually reject this flag while classic GoldSrc compilers accept it.
    """
    name = tool_path.name.strip().lower()
    if name.startswith("sdhl"):
        return False
    return True


def _find_case_insensitive_file(root: Path, filename: str) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    target = filename.casefold()
    try:
        for child in root.iterdir():
            if child.is_file() and child.name.casefold() == target:
                return child
    except Exception:
        return None
    return None


def _candidate_wad_dirs(*, map_file: Path, game_root: Path) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            return
        seen.add(rp)
        dirs.append(rp)

    # Project-local defaults first.
    _add(map_file.parent)
    _add(map_file.parent.parent)
    _add(map_file.parent.parent / "textures")
    _add(game_root)
    _add(game_root / "textures")
    _add(game_root / "wads")
    _add(game_root / "maps")

    # Optional explicit override: semicolon-separated directories.
    env_dirs = (os.getenv("IVAN_WAD_DIRS") or "").strip()
    if env_dirs:
        for raw in env_dirs.split(";"):
            raw = raw.strip()
            if raw:
                _add(Path(raw))

    # Common Steam locations on Windows.
    if _is_windows():
        steam_common = Path("C:/Program Files (x86)/Steam/steamapps/common")
        _add(steam_common / "Half-Life" / "valve")
        _add(steam_common / "Half-Life" / "valve_downloads")
        _add(steam_common / "Half-Life" / "valve_addon")
        _add(steam_common / "Half-Life SDK" / "valve")
        _add(steam_common / "Half-Life SDK")

    return [d for d in dirs if d.exists() and d.is_dir()]


def _prepare_map_for_compile(*, map_file: Path, work_dir: Path, game_root: Path) -> Path:
    """
    Copy .map to work_dir and normalize worldspawn `wad` paths for local compilers.

    This keeps authoring maps untouched while making compile-time WAD lookup robust.
    """
    local_map = work_dir / map_file.name
    text = map_file.read_text(encoding="utf-8", errors="replace")

    wad_re = re.compile(r'(?mi)^(\s*"wad"\s*")([^"]*)(".*)$')
    m = wad_re.search(text)
    if not m:
        local_map.write_text(text, encoding="utf-8")
        return local_map

    raw_wad = m.group(2).strip()
    wad_parts = [p.strip() for p in raw_wad.replace("\\", "/").split(";") if p.strip()]
    wad_names = [Path(p).name for p in wad_parts if Path(p).name]
    if not wad_names:
        local_map.write_text(text, encoding="utf-8")
        return local_map

    resolved: list[Path] = []
    search_dirs = _candidate_wad_dirs(map_file=map_file, game_root=game_root)
    for name in wad_names:
        found: Path | None = None
        for d in search_dirs:
            found = _find_case_insensitive_file(d, name)
            if found is not None:
                break
        if found is not None:
            resolved.append(found)

    if resolved:
        # Use forward slashes to avoid parser escape warnings on Windows.
        wad_value = ";".join(str(p).replace("\\", "/") for p in resolved)
        text = wad_re.sub(lambda mm: f'{mm.group(1)}{wad_value}{mm.group(3)}', text, count=1)
        print(f"[bake] worldspawn wad resolved: {len(resolved)}/{len(wad_names)}")
        for p in resolved:
            print(f"[bake]   wad -> {p}")
    else:
        print("[bake] WARNING: could not resolve worldspawn wad paths; compiler may miss textures.")
        print("[bake] searched wad dirs:")
        for d in search_dirs:
            print(f"[bake]   - {d}")

    local_map.write_text(text, encoding="utf-8")
    return local_map


def _run_tool(
    label: str,
    cmd: list[str | Path],
    *,
    cwd: Path | None = None,
) -> None:
    """Run an external tool, printing its output and timing."""
    print(f"\n{'=' * 60}")
    print(f"[bake] Running {label}:")
    print(f"  {' '.join(str(c) for c in cmd)}")
    print(f"{'=' * 60}")

    t0 = time.perf_counter()
    result = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    elapsed = time.perf_counter() - t0

    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"  {line}")

    if result.returncode != 0:
        print(f"\n[bake] ERROR: {label} exited with code {result.returncode} ({elapsed:.1f}s)")
        sys.exit(result.returncode)

    print(f"[bake] {label} finished in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_qbsp(qbsp: Path, map_file: Path, work_dir: Path, game_root: Path) -> Path:
    """Run qbsp on the .map and return the path to the produced .bsp."""
    # qbsp writes the .bsp next to the .map by default.  We copy the .map
    # into work_dir so intermediate files stay isolated.
    local_map = _prepare_map_for_compile(map_file=map_file, work_dir=work_dir, game_root=game_root)

    cmd: list[str | Path] = [qbsp, local_map]
    _run_tool("qbsp", cmd, cwd=work_dir)

    bsp_path = local_map.with_suffix(".bsp")
    if not bsp_path.is_file():
        print(f"[bake] ERROR: qbsp did not produce {bsp_path}")
        sys.exit(1)
    return bsp_path


def stage_hlcsg_hlbsp(
    hlcsg: Path,
    hlbsp: Path,
    map_file: Path,
    work_dir: Path,
    game_root: Path,
) -> Path:
    """
    Run classic GoldSrc compile front-end (hlcsg + hlbsp) and return .bsp path.
    """
    local_map = _prepare_map_for_compile(map_file=map_file, work_dir=work_dir, game_root=game_root)
    bsp_path = local_map.with_suffix(".bsp")
    csg_cmd: list[str | Path] = [hlcsg]
    if _supports_game_flag(hlcsg):
        csg_cmd += ["-game", game_root]
    csg_cmd.append(local_map)
    _run_tool("hlcsg", csg_cmd, cwd=work_dir)
    bsp_cmd: list[str | Path] = [hlbsp]
    if _supports_game_flag(hlbsp):
        bsp_cmd += ["-game", game_root]
    bsp_cmd.append(bsp_path)
    _run_tool("hlbsp", bsp_cmd, cwd=work_dir)
    if not bsp_path.is_file():
        print(f"[bake] ERROR: hlbsp did not produce {bsp_path}")
        sys.exit(1)
    return bsp_path


def stage_vis(vis: Path, bsp_path: Path) -> None:
    """Run vis on the .bsp (in-place)."""
    _run_tool("vis", [vis, bsp_path])


def stage_light(
    light: Path,
    bsp_path: Path,
    *,
    bounce: int | None = None,
    extra: bool = False,
) -> None:
    """Run light on the .bsp (in-place)."""
    cmd: list[str | Path] = [light]
    if bounce is not None and bounce > 0:
        cmd += ["-bounce", str(bounce)]
    if extra:
        cmd += ["-extra4"]
    cmd.append(bsp_path)
    _run_tool("light", cmd)


def stage_import(
    bsp_path: Path,
    output: Path,
    *,
    game_root: Path,
    scale: float,
    dir_bundle: bool,
) -> None:
    """Import the compiled BSP using the GoldSrc importer."""
    out_format = "dir" if dir_bundle else "irunmap"
    cmd: list[str | Path] = [
        sys.executable,
        str(_GOLDSRC_IMPORTER),
        "--bsp", str(bsp_path),
        "--game-root", str(game_root),
        "--out", str(output),
        "--out-format", out_format,
        "--scale", str(scale),
    ]
    _run_tool("import_goldsrc_bsp", cmd)


def _validate_import_non_empty(output: Path, *, dir_bundle: bool) -> bool:
    """
    Ensure import produced some geometry. A silent 0-triangle import usually means
    the compiler output is incompatible (or source textures/WADs are missing).
    """
    try:
        if dir_bundle:
            map_json = output / "map.json"
            if not map_json.is_file():
                return False
            payload = json.loads(map_json.read_text(encoding="utf-8"))
        else:
            with zipfile.ZipFile(output, "r") as zf:
                with zf.open("map.json", "r") as f:
                    payload = json.loads(f.read().decode("utf-8"))
        tri_count = int(payload.get("triangle_count", 0))
        col_count = int(payload.get("collision_triangle_count", 0))
        if tri_count > 0 or col_count > 0:
            return True
        return False
    except Exception:
        return False


@dataclass(frozen=True)
class CompilerToolchain:
    kind: str  # "ericw" | "goldsrc"
    csg_or_qbsp: Path
    bsp_or_vis: Path
    vis: Path | None
    light: Path | None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bake pipeline: compile a .map with ericw-tools (qbsp/vis/light) "
            "then import the BSP into an IVAN .irunmap bundle."
        ),
    )
    add_profile_argument(parser)
    parser.add_argument(
        "--map",
        required=True,
        help="Path to the .map file to compile.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path. Produces .irunmap by default (or a directory if --dir-bundle).",
    )
    parser.add_argument(
        "--ericw-tools",
        required=True,
        help="Directory containing ericw-tools binaries (qbsp, vis, light).",
    )
    parser.add_argument(
        "--game-root",
        required=True,
        help="Path to the game/mod asset root (for WAD/texture lookup during import).",
    )
    parser.add_argument(
        "--compiler",
        default="auto",
        choices=("auto", "ericw", "goldsrc"),
        help=(
            "Compiler backend: auto (prefer goldsrc if available), "
            "ericw (qbsp/vis/light), or goldsrc (hlcsg/hlbsp/hlvis/hlrad)."
        ),
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.03,
        help="World-unit scale factor passed to the GoldSrc importer (default: 0.03).",
    )
    parser.add_argument(
        "--no-vis",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Skip the vis stage (default for dev-fast profile).",
    )
    parser.add_argument(
        "--no-light",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Skip the light stage (default for dev-fast profile).",
    )
    parser.add_argument(
        "--light-extra",
        action="store_true",
        help="Enable -extra4 quality for the light stage.",
    )
    parser.add_argument(
        "--bounce",
        type=int,
        default=None,
        help="Number of bounce passes for the light stage.",
    )
    parser.add_argument(
        "--dir-bundle",
        action="store_true",
        help="Output as a directory bundle instead of a packed .irunmap archive.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Apply profile defaults for --no-vis and --no-light when not explicitly set.
    profile = get_profile(args)
    no_vis = getattr(args, "no_vis", None)
    no_light = getattr(args, "no_light", None)
    if no_vis is None:
        no_vis = profile == PROFILE_DEV_FAST
    if no_light is None:
        no_light = profile == PROFILE_DEV_FAST
    args.no_vis = no_vis
    args.no_light = no_light

    total_t0 = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Validate inputs
    # ------------------------------------------------------------------
    map_file = Path(args.map).resolve()
    if not map_file.is_file():
        print(f"[bake] ERROR: .map file not found: {map_file}")
        sys.exit(1)

    ericw_dir = Path(args.ericw_tools).resolve()
    if not ericw_dir.is_dir():
        print(f"[bake] ERROR: ericw-tools directory not found: {ericw_dir}")
        sys.exit(1)

    game_root = Path(args.game_root).resolve()
    if not game_root.is_dir():
        print(f"[bake] ERROR: game-root directory not found: {game_root}")
        sys.exit(1)

    output = Path(args.output).resolve()

    # Locate binaries.
    qbsp_bin = _find_binary(ericw_dir, "qbsp")
    vis_ericw = _find_binary(ericw_dir, "vis")
    light_ericw = _find_binary(ericw_dir, "light")

    hlcsg_bin = _find_first_binary(ericw_dir, ["hlcsg", "hlcsgs"])
    hlbsp_bin = _find_first_binary(ericw_dir, ["hlbsp", "hlbsps"])
    hlvis_bin = _find_first_binary(ericw_dir, ["hlvis", "hlviss", "vis"])
    hlrad_bin = _find_first_binary(ericw_dir, ["hlrad", "hlrads", "light"])

    forced = str(args.compiler).strip().lower()
    use_goldsrc = False
    if forced == "goldsrc":
        use_goldsrc = True
    elif forced == "ericw":
        use_goldsrc = False
    else:
        # auto: prefer native GoldSrc chain when present.
        use_goldsrc = bool(hlcsg_bin is not None and hlbsp_bin is not None)

    if use_goldsrc:
        if hlcsg_bin is None or hlbsp_bin is None:
            print(
                f"[bake] ERROR: goldsrc compiler selected but hlcsg/hlbsp not found in {ericw_dir}. "
                "Provide a directory containing hlcsg.exe, hlbsp.exe, hlvis.exe, hlrad.exe."
            )
            sys.exit(1)
        vis_bin: Path | None = None
        if not args.no_vis:
            vis_bin = hlvis_bin
            if vis_bin is None:
                print(f"[bake] ERROR: hlvis binary not found in {ericw_dir}")
                sys.exit(1)
        light_bin: Path | None = None
        if not args.no_light:
            light_bin = hlrad_bin
            if light_bin is None:
                print(f"[bake] ERROR: hlrad binary not found in {ericw_dir}")
                sys.exit(1)
        toolchain = CompilerToolchain(
            kind="goldsrc",
            csg_or_qbsp=hlcsg_bin,
            bsp_or_vis=hlbsp_bin,
            vis=vis_bin,
            light=light_bin,
        )
    else:
        if qbsp_bin is None:
            print(
                f"[bake] ERROR: ericw compiler selected but qbsp not found in {ericw_dir}. "
                "Provide qbsp/vis/light binaries or switch --compiler goldsrc."
            )
            sys.exit(1)
        vis_bin = None
        if not args.no_vis:
            vis_bin = vis_ericw
            if vis_bin is None:
                print(f"[bake] ERROR: vis binary not found in {ericw_dir}")
                sys.exit(1)
        light_bin = None
        if not args.no_light:
            light_bin = light_ericw
            if light_bin is None:
                print(f"[bake] ERROR: light binary not found in {ericw_dir}")
                sys.exit(1)
        toolchain = CompilerToolchain(
            kind="ericw",
            csg_or_qbsp=qbsp_bin,
            bsp_or_vis=Path(""),
            vis=vis_bin,
            light=light_bin,
        )

    if not _GOLDSRC_IMPORTER.is_file():
        print(f"[bake] ERROR: GoldSrc importer not found: {_GOLDSRC_IMPORTER}")
        sys.exit(1)

    print(f"[bake] Map       : {map_file}")
    print(f"[bake] Output    : {output}")
    print(f"[bake] Profile   : {profile}")
    print(f"[bake] compiler  : {toolchain.kind}")
    print(f"[bake] ericw-tools: {ericw_dir}")
    print(f"[bake] game-root : {game_root}")
    print(f"[bake] scale     : {args.scale}")
    print(f"[bake] vis       : {'skip' if args.no_vis else 'yes'}")
    print(f"[bake] light     : {'skip' if args.no_light else 'yes'}")
    if not args.no_light:
        extras = []
        if args.light_extra:
            extras.append("-extra4")
        if args.bounce is not None:
            extras.append(f"-bounce {args.bounce}")
        print(f"[bake] light opts: {' '.join(extras) if extras else '(default)'}")

    # ------------------------------------------------------------------
    # 2. Create temp directory for intermediate files
    # ------------------------------------------------------------------
    tmp_dir = tempfile.mkdtemp(prefix=f"irun-bake-{map_file.stem}-")
    work_dir = Path(tmp_dir)
    print(f"\n[bake] Temp dir: {work_dir}")

    try:
        # --------------------------------------------------------------
        # 3. Compile geometry to BSP
        # --------------------------------------------------------------
        if toolchain.kind == "goldsrc":
            bsp_path = stage_hlcsg_hlbsp(
                toolchain.csg_or_qbsp,
                toolchain.bsp_or_vis,
                map_file,
                work_dir,
                game_root,
            )
        else:
            bsp_path = stage_qbsp(toolchain.csg_or_qbsp, map_file, work_dir, game_root)

        # --------------------------------------------------------------
        # 4. vis (optional)
        # --------------------------------------------------------------
        if toolchain.vis is not None:
            stage_vis(toolchain.vis, bsp_path)

        # --------------------------------------------------------------
        # 5. light (optional)
        # --------------------------------------------------------------
        if toolchain.light is not None:
            if toolchain.kind == "goldsrc":
                # GoldSrc compilers usually use "-extra" instead of ericw's "-extra4".
                cmd: list[str | Path] = [toolchain.light]
                if args.light_extra:
                    cmd += ["-extra"]
                if args.bounce is not None and args.bounce > 0:
                    cmd += ["-bounce", str(args.bounce)]
                cmd.append(bsp_path)
                _run_tool("hlrad", cmd, cwd=work_dir)
            else:
                stage_light(
                    toolchain.light,
                    bsp_path,
                    bounce=args.bounce,
                    extra=args.light_extra,
                )

        # --------------------------------------------------------------
        # 6. Import compiled BSP via GoldSrc importer
        # --------------------------------------------------------------
        stage_import(
            bsp_path,
            output,
            game_root=game_root,
            scale=args.scale,
            dir_bundle=args.dir_bundle,
        )
        if not _validate_import_non_empty(output, dir_bundle=bool(args.dir_bundle)):
            print(
                "[bake] ERROR: import produced empty geometry (0 render/collision triangles). "
                "Common causes: missing WAD textures in map worldspawn, or incompatible compiler output. "
                "For GoldSrc maps prefer --compiler goldsrc with hlcsg/hlbsp/hlvis/hlrad."
            )
            sys.exit(2)

        total_elapsed = time.perf_counter() - total_t0
        print(f"\n[bake] Done! Total time: {total_elapsed:.1f}s")
        print(f"[bake] Output: {output}")

    finally:
        # --------------------------------------------------------------
        # 7. Clean up temp directory
        # --------------------------------------------------------------
        try:
            shutil.rmtree(work_dir)
            print(f"[bake] Cleaned up temp dir: {work_dir}")
        except Exception as exc:
            print(f"[bake] Warning: could not remove temp dir {work_dir}: {exc}")


if __name__ == "__main__":
    main()
