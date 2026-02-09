from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, pack_bundle_dir_to_irunmap
from ivan.maps.source_compile import (
    create_temp_source_game_root,
    find_compiled_bsp,
    resolve_compile_tool,
)


def _run_checked(*, cmd: list[str], label: str) -> None:
    print(f"[{label}] {shlex.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = (proc.stdout or "").strip()[-8000:]
        raise RuntimeError(f"{label} failed (exit {proc.returncode})\n{tail}")
    out = (proc.stdout or "").strip()
    if out:
        print(out[-2000:])


def _resolve_map_output(*, out_ref: Path) -> tuple[Path, Path | None]:
    """
    Resolve output layout.

    Returns:
      (bundle_dir, packed_out)
    """

    if out_ref.suffix.lower() == PACKED_BUNDLE_EXT:
        packed_out = out_ref.resolve()
        packed_out.parent.mkdir(parents=True, exist_ok=True)
        bundle_dir = Path(tempfile.mkdtemp(prefix=f"ivan-src-vmf-{out_ref.stem}-", dir=str(packed_out.parent))).resolve()
        return (bundle_dir, packed_out)

    out_resolved = out_ref.resolve()
    if out_resolved.suffix.lower() == ".json":
        bundle_dir = out_resolved.parent
    else:
        bundle_dir = out_resolved
    bundle_dir.mkdir(parents=True, exist_ok=True)
    return (bundle_dir, None)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a Source VMF (vbsp/vvis/vrad) and import it into an IVAN map bundle."
    )
    parser.add_argument("--vmf", required=True, help="Path to Source VMF source.")
    parser.add_argument(
        "--out",
        required=True,
        help=(
            "Output bundle reference.\n"
            "- directory (writes map.json + materials/ + lightmaps/)\n"
            "- map.json path\n"
            "- packed .irunmap path"
        ),
    )
    parser.add_argument("--map-id", default=None, help="Optional map id override for map.json.")
    parser.add_argument("--scale", type=float, default=0.03, help="Source-to-game scale.")

    parser.add_argument(
        "--materials-root",
        default=None,
        help="Folder with Source materials/VTFs for conversion (default: <vmf-dir>/materials).",
    )
    parser.add_argument(
        "--materials-out",
        default=None,
        help="Where to put converted PNG materials (default: <bundle>/materials).",
    )
    parser.add_argument(
        "--lightmaps-out",
        default=None,
        help="Where to write extracted lightmaps (default: <bundle>/lightmaps).",
    )

    parser.add_argument(
        "--game-root",
        default=None,
        help=(
            "Optional fallback Source game root containing gameinfo.txt and stock assets "
            "(e.g. Counter-Strike Source)."
        ),
    )
    parser.add_argument(
        "--compile-bin",
        default=None,
        help="Optional directory containing vbsp/vvis/vrad binaries.",
    )
    parser.add_argument("--vbsp", default=None, help="Explicit vbsp binary path.")
    parser.add_argument("--vvis", default=None, help="Explicit vvis binary path.")
    parser.add_argument("--vrad", default=None, help="Explicit vrad binary path.")
    parser.add_argument("--skip-vvis", action="store_true", help="Skip VIS compile stage.")
    parser.add_argument("--skip-vrad", action="store_true", help="Skip RAD/light compile stage.")
    parser.add_argument(
        "--bsp-out",
        default=None,
        help="Optional explicit BSP output path (if your compiler writes to a custom location).",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary compile/bundle dirs.")
    args = parser.parse_args()

    vmf_path = Path(args.vmf).expanduser().resolve()
    if not vmf_path.exists():
        raise FileNotFoundError(f"VMF does not exist: {vmf_path}")
    if vmf_path.suffix.lower() != ".vmf":
        raise ValueError(f"--vmf must point to a .vmf file: {vmf_path}")

    fallback_game_root = Path(args.game_root).expanduser().resolve() if args.game_root else None
    if fallback_game_root is not None and not fallback_game_root.exists():
        raise FileNotFoundError(f"--game-root does not exist: {fallback_game_root}")

    compile_bin = Path(args.compile_bin).expanduser().resolve() if args.compile_bin else None
    if compile_bin is not None and not compile_bin.exists():
        raise FileNotFoundError(f"--compile-bin does not exist: {compile_bin}")

    bundle_dir, packed_out = _resolve_map_output(out_ref=Path(args.out))
    map_json_out = bundle_dir / "map.json"
    materials_root = Path(args.materials_root).expanduser().resolve() if args.materials_root else (vmf_path.parent / "materials").resolve()
    materials_out = Path(args.materials_out).expanduser().resolve() if args.materials_out else (bundle_dir / "materials").resolve()
    lightmaps_out = Path(args.lightmaps_out).expanduser().resolve() if args.lightmaps_out else (bundle_dir / "lightmaps").resolve()
    override_bsp = Path(args.bsp_out).expanduser().resolve() if args.bsp_out else None

    temp_dirs: list[Path] = []
    compile_game_root: Path | None = None
    try:
        compile_game_root = create_temp_source_game_root(vmf_dir=vmf_path.parent, fallback_game_root=fallback_game_root)
        temp_dirs.append(compile_game_root)

        vbsp = resolve_compile_tool(
            tool="vbsp",
            explicit=Path(args.vbsp) if args.vbsp else None,
            compile_bin=compile_bin,
            fallback_game_root=fallback_game_root,
        )
        if vbsp is None:
            raise RuntimeError(
                "Could not find `vbsp`. Install Source compile tools or pass --vbsp / --compile-bin."
            )

        vvis = None
        if not args.skip_vvis:
            vvis = resolve_compile_tool(
                tool="vvis",
                explicit=Path(args.vvis) if args.vvis else None,
                compile_bin=compile_bin,
                fallback_game_root=fallback_game_root,
            )
            if vvis is None:
                raise RuntimeError(
                    "Could not find `vvis`. Install Source compile tools, pass --vvis / --compile-bin, or use --skip-vvis."
                )

        vrad = None
        if not args.skip_vrad:
            vrad = resolve_compile_tool(
                tool="vrad",
                explicit=Path(args.vrad) if args.vrad else None,
                compile_bin=compile_bin,
                fallback_game_root=fallback_game_root,
            )
            if vrad is None:
                raise RuntimeError(
                    "Could not find `vrad`. Install Source compile tools, pass --vrad / --compile-bin, or use --skip-vrad."
                )

        started_at = time.time()
        _run_checked(
            cmd=[str(vbsp), "-game", str(compile_game_root), str(vmf_path)],
            label="vbsp",
        )

        compiled_bsp = find_compiled_bsp(
            vmf_path=vmf_path,
            compile_game_root=compile_game_root,
            override_bsp_path=override_bsp,
            started_at=started_at,
        )
        if compiled_bsp is None:
            raise RuntimeError(
                "vbsp finished but compiled BSP was not found. "
                "Pass --bsp-out if your setup writes BSPs to a non-standard path."
            )

        if vvis is not None:
            _run_checked(
                cmd=[str(vvis), "-game", str(compile_game_root), str(compiled_bsp)],
                label="vvis",
            )
        if vrad is not None:
            _run_checked(
                cmd=[str(vrad), "-game", str(compile_game_root), str(compiled_bsp)],
                label="vrad",
            )

        if not materials_root.exists():
            raise FileNotFoundError(
                f"Materials root does not exist: {materials_root}. "
                "Pass --materials-root to a folder that contains Source VTF/VMT assets."
            )

        app_root = Path(__file__).resolve().parents[3]
        build_script = app_root / "tools" / "build_source_bsp_assets.py"
        cmd = [
            sys.executable,
            str(build_script),
            "--input",
            str(compiled_bsp),
            "--output",
            str(map_json_out),
            "--materials-root",
            str(materials_root),
            "--materials-out",
            str(materials_out),
            "--lightmaps-out",
            str(lightmaps_out),
            "--scale",
            str(float(args.scale)),
        ]
        if args.map_id:
            cmd += ["--map-id", str(args.map_id)]
        _run_checked(cmd=cmd, label="build_source_bsp_assets")

        if packed_out is not None:
            pack_bundle_dir_to_irunmap(bundle_dir=bundle_dir, out_path=packed_out, compresslevel=1)
            print(f"Wrote {packed_out}")
        else:
            print(f"Wrote {map_json_out}")
    finally:
        if not args.keep_temp:
            for d in temp_dirs:
                shutil.rmtree(d, ignore_errors=True)
            if packed_out is not None:
                # For packed output we built an intermediate directory under _resolve_map_output().
                shutil.rmtree(bundle_dir, ignore_errors=True)
        else:
            if compile_game_root is not None:
                print(f"Kept temp compile root: {compile_game_root}")
            if packed_out is not None:
                print(f"Kept temp bundle root: {bundle_dir}")


if __name__ == "__main__":
    main()

