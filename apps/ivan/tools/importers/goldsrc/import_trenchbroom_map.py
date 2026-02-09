from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

from ivan.maps.goldsrc_compile import find_compiled_bsp, resolve_compile_tool


def _run_checked(*, cmd: list[str], label: str) -> None:
    print(f"[{label}] {shlex.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = (proc.stdout or "").strip()[-8000:]
        raise RuntimeError(f"{label} failed (exit {proc.returncode})\n{tail}")
    out = (proc.stdout or "").strip()
    if out:
        print(out[-2000:])


def _split_cli_args(raw: str | None) -> list[str]:
    if not raw:
        return []
    return shlex.split(raw)


def _supports_game_flag(tool_path: Path) -> bool:
    """
    Detect compiler families that accept `-game`.

    SDHLT tools (`sdHLCSG`, etc.) do not support this flag, while classic
    GoldSrc toolchains often do.
    """
    name = tool_path.name.strip().lower()
    if name.startswith("sdhl"):
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a TrenchBroom GoldSrc/Valve220 .map (hlcsg/hlbsp/hlvis/hlrad) "
            "and import the resulting BSP into an IVAN map bundle."
        )
    )
    parser.add_argument("--map", required=True, help="Path to a TrenchBroom .map file.")
    parser.add_argument(
        "--game-root",
        required=True,
        help="Path to a GoldSrc/Xash3D mod root (e.g. .../valve or .../cstrike).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help=(
            "Output for the imported IVAN map bundle.\n"
            "- directory (writes map.json + materials/ + lightmaps/ + resources/)\n"
            "- map.json path\n"
            "- packed .irunmap path"
        ),
    )
    parser.add_argument(
        "--out-format",
        choices=("auto", "dir", "irunmap"),
        default="auto",
        help="Output format passed through to GoldSrc BSP importer (default: auto).",
    )
    parser.add_argument("--map-id", default=None, help="Optional map id override in output map.json.")
    parser.add_argument("--scale", type=float, default=0.03, help="GoldSrc-to-game unit scale.")
    parser.add_argument(
        "--extract-all-wad-textures",
        action="store_true",
        help="Extract all textures from referenced WADs (default extracts only used textures).",
    )
    parser.add_argument(
        "--copy-resources",
        action="store_true",
        help="Copy non-texture resources listed in .res / entity scan into the bundle.",
    )

    parser.add_argument(
        "--compile-bin",
        default=None,
        help="Optional directory containing hlcsg/hlbsp/hlvis/hlrad binaries.",
    )
    parser.add_argument("--hlcsg", default=None, help="Explicit hlcsg binary path.")
    parser.add_argument("--hlbsp", default=None, help="Explicit hlbsp binary path.")
    parser.add_argument("--hlvis", default=None, help="Explicit hlvis binary path.")
    parser.add_argument("--hlrad", default=None, help="Explicit hlrad binary path.")
    parser.add_argument("--skip-hlvis", action="store_true", help="Skip VIS compile stage.")
    parser.add_argument("--skip-hlrad", action="store_true", help="Skip RAD/light compile stage.")
    parser.add_argument(
        "--hlcsg-args",
        default=None,
        help="Extra args appended to hlcsg (single string, shell-split).",
    )
    parser.add_argument(
        "--hlbsp-args",
        default=None,
        help="Extra args appended to hlbsp (single string, shell-split).",
    )
    parser.add_argument(
        "--hlvis-args",
        default=None,
        help="Extra args appended to hlvis (single string, shell-split).",
    )
    parser.add_argument(
        "--hlrad-args",
        default=None,
        help="Extra args appended to hlrad (single string, shell-split).",
    )
    parser.add_argument(
        "--bsp-out",
        default=None,
        help="Optional explicit BSP output path if compile tools write to a custom location.",
    )
    args = parser.parse_args()

    map_path = Path(args.map).expanduser().resolve()
    if not map_path.exists():
        raise FileNotFoundError(f"--map does not exist: {map_path}")
    if map_path.suffix.lower() != ".map":
        raise ValueError(f"--map must point to a .map file: {map_path}")

    game_root = Path(args.game_root).expanduser().resolve()
    if not game_root.exists():
        raise FileNotFoundError(f"--game-root does not exist: {game_root}")

    out_ref = Path(args.out).expanduser().resolve()
    if args.out_format == "dir" and out_ref.suffix.lower() == ".json":
        raise ValueError("--out-format=dir expects a directory or .irunmap path, not .json")

    compile_bin = Path(args.compile_bin).expanduser().resolve() if args.compile_bin else None
    if compile_bin is not None and not compile_bin.exists():
        raise FileNotFoundError(f"--compile-bin does not exist: {compile_bin}")

    hlcsg = resolve_compile_tool(
        tool="hlcsg",
        explicit=Path(args.hlcsg) if args.hlcsg else None,
        compile_bin=compile_bin,
        game_root=game_root,
    )
    if hlcsg is None:
        raise RuntimeError("Could not find `hlcsg`. Install GoldSrc compile tools or pass --hlcsg / --compile-bin.")

    hlbsp = resolve_compile_tool(
        tool="hlbsp",
        explicit=Path(args.hlbsp) if args.hlbsp else None,
        compile_bin=compile_bin,
        game_root=game_root,
    )
    if hlbsp is None:
        raise RuntimeError("Could not find `hlbsp`. Install GoldSrc compile tools or pass --hlbsp / --compile-bin.")

    hlvis = None
    if not args.skip_hlvis:
        hlvis = resolve_compile_tool(
            tool="hlvis",
            explicit=Path(args.hlvis) if args.hlvis else None,
            compile_bin=compile_bin,
            game_root=game_root,
        )
        if hlvis is None:
            raise RuntimeError(
                "Could not find `hlvis`. Install GoldSrc compile tools, pass --hlvis / --compile-bin, or use --skip-hlvis."
            )

    hlrad = None
    if not args.skip_hlrad:
        hlrad = resolve_compile_tool(
            tool="hlrad",
            explicit=Path(args.hlrad) if args.hlrad else None,
            compile_bin=compile_bin,
            game_root=game_root,
        )
        if hlrad is None:
            raise RuntimeError(
                "Could not find `hlrad`. Install GoldSrc compile tools, pass --hlrad / --compile-bin, or use --skip-hlrad."
            )

    override_bsp = Path(args.bsp_out).expanduser().resolve() if args.bsp_out else None
    csg_game_args = ["-game", str(game_root)] if _supports_game_flag(hlcsg) else []
    bsp_game_args = ["-game", str(game_root)] if _supports_game_flag(hlbsp) else []
    vis_game_args = ["-game", str(game_root)] if hlvis is not None and _supports_game_flag(hlvis) else []
    rad_game_args = ["-game", str(game_root)] if hlrad is not None and _supports_game_flag(hlrad) else []
    started_at = time.time()
    _run_checked(
        cmd=[
            str(hlcsg),
            *csg_game_args,
            *_split_cli_args(args.hlcsg_args),
            str(map_path),
        ],
        label="hlcsg",
    )

    compiled_bsp = find_compiled_bsp(
        map_path=map_path,
        game_root=game_root,
        override_bsp_path=override_bsp,
        started_at=started_at,
    )
    if compiled_bsp is None:
        raise RuntimeError(
            "hlcsg finished but compiled BSP was not found. Pass --bsp-out if your setup writes BSPs to a non-standard path."
        )

    _run_checked(
        cmd=[
            str(hlbsp),
            *bsp_game_args,
            *_split_cli_args(args.hlbsp_args),
            str(compiled_bsp),
        ],
        label="hlbsp",
    )

    if hlvis is not None:
        _run_checked(
            cmd=[
                str(hlvis),
                *vis_game_args,
                *_split_cli_args(args.hlvis_args),
                str(compiled_bsp),
            ],
            label="hlvis",
        )

    if hlrad is not None:
        _run_checked(
            cmd=[
                str(hlrad),
                *rad_game_args,
                *_split_cli_args(args.hlrad_args),
                str(compiled_bsp),
            ],
            label="hlrad",
        )

    final_bsp = find_compiled_bsp(
        map_path=map_path,
        game_root=game_root,
        override_bsp_path=override_bsp,
        started_at=started_at,
    )
    if final_bsp is None:
        final_bsp = compiled_bsp

    import_script = Path(__file__).resolve().parent / "import_goldsrc_bsp.py"
    import_cmd = [
        sys.executable,
        str(import_script),
        "--bsp",
        str(final_bsp),
        "--game-root",
        str(game_root),
        "--out",
        str(out_ref),
        "--out-format",
        str(args.out_format),
        "--scale",
        str(float(args.scale)),
    ]
    if args.map_id:
        import_cmd.extend(["--map-id", str(args.map_id)])
    if args.extract_all_wad_textures:
        import_cmd.append("--extract-all-wad-textures")
    if args.copy_resources:
        import_cmd.append("--copy-resources")

    _run_checked(cmd=import_cmd, label="import_goldsrc_bsp")


if __name__ == "__main__":
    main()
