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
        [--no-vis] \\
        [--no-light] \\
        [--light-extra] \\
        [--bounce N] \\
        [--dir-bundle]
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# The GoldSrc importer can be invoked as a subprocess (it lives outside the
# normal package hierarchy) or imported directly when ``sys.path`` is set up.
# We keep both options so this script works standalone.
# ---------------------------------------------------------------------------

_TOOLS_DIR = Path(__file__).resolve().parent
_GOLDSRC_IMPORTER = _TOOLS_DIR / "importers" / "goldsrc" / "import_goldsrc_bsp.py"


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

def stage_qbsp(qbsp: Path, map_file: Path, work_dir: Path) -> Path:
    """Run qbsp on the .map and return the path to the produced .bsp."""
    # qbsp writes the .bsp next to the .map by default.  We copy the .map
    # into work_dir so intermediate files stay isolated.
    local_map = work_dir / map_file.name
    shutil.copy2(map_file, local_map)

    cmd: list[str | Path] = [qbsp, local_map]
    _run_tool("qbsp", cmd, cwd=work_dir)

    bsp_path = local_map.with_suffix(".bsp")
    if not bsp_path.is_file():
        print(f"[bake] ERROR: qbsp did not produce {bsp_path}")
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
        "--scale",
        type=float,
        default=0.03,
        help="World-unit scale factor passed to the GoldSrc importer (default: 0.03).",
    )
    parser.add_argument(
        "--no-vis",
        action="store_true",
        help="Skip the vis stage.",
    )
    parser.add_argument(
        "--no-light",
        action="store_true",
        help="Skip the light stage.",
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
    if qbsp_bin is None:
        print(f"[bake] ERROR: qbsp binary not found in {ericw_dir}")
        sys.exit(1)

    vis_bin: Path | None = None
    if not args.no_vis:
        vis_bin = _find_binary(ericw_dir, "vis")
        if vis_bin is None:
            print(f"[bake] ERROR: vis binary not found in {ericw_dir}")
            sys.exit(1)

    light_bin: Path | None = None
    if not args.no_light:
        light_bin = _find_binary(ericw_dir, "light")
        if light_bin is None:
            print(f"[bake] ERROR: light binary not found in {ericw_dir}")
            sys.exit(1)

    if not _GOLDSRC_IMPORTER.is_file():
        print(f"[bake] ERROR: GoldSrc importer not found: {_GOLDSRC_IMPORTER}")
        sys.exit(1)

    print(f"[bake] Map       : {map_file}")
    print(f"[bake] Output    : {output}")
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
        # 3. qbsp
        # --------------------------------------------------------------
        bsp_path = stage_qbsp(qbsp_bin, map_file, work_dir)

        # --------------------------------------------------------------
        # 4. vis (optional)
        # --------------------------------------------------------------
        if vis_bin is not None:
            stage_vis(vis_bin, bsp_path)

        # --------------------------------------------------------------
        # 5. light (optional)
        # --------------------------------------------------------------
        if light_bin is not None:
            stage_light(
                light_bin,
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
