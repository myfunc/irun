"""Pack a .map file into an IVAN .irunmap bundle without baking (no lightmaps).

Parses a Valve 220 / Standard .map file, converts brush geometry to triangles,
resolves WAD textures, and writes a map bundle that the IVAN runtime can load.

This is the fast-iteration path: no ericw-tools compilation, no BSP, no lightmaps.
Use ``bake_map.py`` when production-quality lighting is needed.

Usage::

    python tools/pack_map.py \\
        --map path/to/mymap.map \\
        --output path/to/output.irunmap \\
        --scale 0.03 \\
        --wad-dirs path/to/wad/directory \\
        [--dir-bundle]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Project imports.  ``ivan.maps.map_parser`` already exists.  The geometry
# and material modules are expected to be created in the near future; the
# import names below match the planned API surface.
# ---------------------------------------------------------------------------

# Ensure the ivan package is importable when running from the tools/ directory.
_APPS_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_APPS_SRC) not in sys.path:
    sys.path.insert(0, str(_APPS_SRC))

from ivan.maps.map_parser import parse_map, MapEntity  # noqa: E402
from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, pack_bundle_dir_to_irunmap  # noqa: E402

# These modules do not exist yet.  Importing them will fail until they are
# implemented.  We guard with a try/except so the rest of the script can be
# inspected, but actual execution requires the modules.
try:
    from ivan.maps.brush_geometry import (  # type: ignore[import-not-found]
        Triangle as _Triangle,
        brush_to_triangles,
        apply_phong_normals,
    )
except ImportError:
    _Triangle = None  # type: ignore[assignment]
    brush_to_triangles = None  # type: ignore[assignment]
    apply_phong_normals = None  # type: ignore[assignment]

try:
    from ivan.maps.material_defs import MaterialResolver  # type: ignore[import-not-found]
except ImportError:
    MaterialResolver = None  # type: ignore[assignment]

# The WAD texture extractor from the GoldSrc importer pipeline.
_TOOLS_DIR = Path(__file__).resolve().parent
_GOLDSRC_DIR = _TOOLS_DIR / "importers" / "goldsrc"
if str(_GOLDSRC_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDSRC_DIR))

try:
    from goldsrc_wad import Wad3  # noqa: E402
except ImportError:
    Wad3 = None  # type: ignore[assignment,misc]

try:
    from PIL import Image  # noqa: E402
except ImportError:
    Image = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Texture helpers
# ---------------------------------------------------------------------------

NO_RENDER_TEXTURES = {
    "aaatrigger",
    "clip",
    "hint",
    "null",
    "nodraw",
    "origin",
    "playerclip",
    "skip",
    "trigger",
}


def _should_render_texture(name: str) -> bool:
    return name.strip().lower() not in NO_RENDER_TEXTURES


def _discover_wads(wad_dirs: list[Path]) -> list[Path]:
    """Find all .wad files inside the given directories."""
    wads: list[Path] = []
    seen: set[Path] = set()
    for d in wad_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.wad")):
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                wads.append(p)
    return wads


def _extract_wad_textures(
    wad_paths: list[Path],
    used_names: set[str],
    materials_dir: Path,
) -> int:
    """Extract matching textures from WAD files into *materials_dir* as PNG."""
    if Wad3 is None:
        print("[pack] WARNING: goldsrc_wad not available; skipping WAD texture extraction.")
        return 0
    if Image is None:
        print("[pack] WARNING: Pillow not available; skipping WAD texture extraction.")
        return 0

    used_cf = {n.casefold() for n in used_names}
    extracted = 0
    for wad_path in wad_paths:
        try:
            wad = Wad3.load(wad_path)
        except Exception as exc:
            print(f"[pack] WARNING: could not load WAD {wad_path}: {exc}")
            continue
        for tex in wad.iter_textures():
            if tex.name.casefold() not in used_cf:
                continue
            if not _should_render_texture(tex.name):
                continue
            dst = materials_dir / f"{tex.name}.png"
            if dst.exists():
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                img = Image.frombytes("RGBA", (tex.width, tex.height), tex.rgba)
                img.save(dst)
                extracted += 1
            except Exception as exc:
                print(f"[pack] WARNING: failed to save texture {tex.name}: {exc}")
    return extracted


# ---------------------------------------------------------------------------
# Spawn helpers
# ---------------------------------------------------------------------------

def _pick_spawn(entities: list[MapEntity], scale: float) -> tuple[list[float], float]:
    """Find the first player start and return (position, yaw)."""
    for ent in entities:
        cname = ent.properties.get("classname", "")
        if cname not in ("info_player_start", "info_player_deathmatch"):
            continue
        origin_raw = ent.properties.get("origin")
        if not origin_raw:
            continue
        parts = origin_raw.split()
        if len(parts) != 3:
            continue
        x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        angles_raw = ent.properties.get("angles")
        yaw = 0.0
        if angles_raw:
            a = angles_raw.split()
            if len(a) >= 2:
                yaw = float(a[1])
        return [x * scale, y * scale, z * scale], yaw
    return [0.0, 0.0, 2.0], 0.0


# ---------------------------------------------------------------------------
# Geometry conversion
# ---------------------------------------------------------------------------

def _collect_texture_names(entities: list[MapEntity]) -> set[str]:
    """Gather all texture names referenced by brush faces."""
    names: set[str] = set()
    for ent in entities:
        for brush in ent.brushes:
            for face in brush.faces:
                if face.texture:
                    names.add(face.texture)
    return names


def _convert_geometry(
    entities: list[MapEntity],
    scale: float,
) -> tuple[list[dict], list[list[float]], list[float], list[float]]:
    """Convert parsed brushes to render and collision triangles.

    Returns (render_triangles, collision_triangles, bounds_min, bounds_max).
    """
    if brush_to_triangles is None:
        print(
            "[pack] ERROR: ivan.maps.brush_geometry module is not available.\n"
            "       This module must be implemented before pack_map.py can convert\n"
            "       brush geometry to triangles.  See the project roadmap."
        )
        sys.exit(1)

    render_tris: list[dict] = []
    collision_tris: list[list[float]] = []
    min_v = [float("inf"), float("inf"), float("inf")]
    max_v = [float("-inf"), float("-inf"), float("-inf")]

    for ent in entities:
        cname = ent.properties.get("classname", "worldspawn")
        is_world = cname == "worldspawn"

        for brush in ent.brushes:
            # brush_to_triangles returns a list of Triangle dataclass instances
            # with attributes: positions, normals, uvs, material.
            triangles = brush_to_triangles(brush, scale=scale)

            if apply_phong_normals is not None:
                triangles = apply_phong_normals(triangles)

            for tri in triangles:
                mat = tri.material
                pos9 = list(tri.positions)  # 9 floats: x0,y0,z0, x1,y1,z1, x2,y2,z2

                # Update bounds.
                for j in range(0, 9, 3):
                    px, py, pz = pos9[j], pos9[j + 1], pos9[j + 2]
                    min_v[0] = min(min_v[0], px)
                    min_v[1] = min(min_v[1], py)
                    min_v[2] = min(min_v[2], pz)
                    max_v[0] = max(max_v[0], px)
                    max_v[1] = max(max_v[1], py)
                    max_v[2] = max(max_v[2], pz)

                # Collision for worldspawn (and explicitly colliding brush entities).
                if is_world:
                    collision_tris.append(pos9)

                # Render triangle.
                if _should_render_texture(mat):
                    render_tris.append({
                        "m": mat,
                        "lmi": None,
                        "p": pos9,
                        "n": list(tri.normals),
                        "uv": list(tri.uvs),
                        "lm": [0.0] * 6,
                        "c": [1.0, 1.0, 1.0, 1.0] * 3,
                    })

    return render_tris, collision_tris, min_v, max_v


# ---------------------------------------------------------------------------
# Material resolution
# ---------------------------------------------------------------------------

def _resolve_materials(
    texture_names: set[str],
    materials_dir: Path,
) -> None:
    """Apply material definitions if the MaterialResolver module is available.

    Scans *materials_dir* for ``.material.json`` files and resolves each
    texture name through the resolver.  This is best-effort; missing modules
    or definitions are silently skipped.
    """
    if MaterialResolver is None:
        return
    try:
        resolver = MaterialResolver([materials_dir])
        for tex_name in sorted(texture_names):
            # Best-effort: resolve each texture to pick up any .material.json
            # files present in the output materials directory.
            albedo = materials_dir / f"{tex_name}.png"
            resolver.resolve(
                tex_name,
                albedo_path=albedo if albedo.exists() else None,
            )
    except Exception as exc:
        print(f"[pack] WARNING: material resolution failed: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Pack a .map file into an IVAN .irunmap bundle without baking. "
            "No ericw-tools required; produces geometry from raw brush data."
        ),
    )
    parser.add_argument(
        "--map",
        required=True,
        help="Path to the .map file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path (.irunmap or directory if --dir-bundle).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.03,
        help="World-unit scale factor (default: 0.03).",
    )
    parser.add_argument(
        "--wad-dirs",
        nargs="*",
        default=[],
        help="Directories to search for .wad files (for texture extraction).",
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
        print(f"[pack] ERROR: .map file not found: {map_file}")
        sys.exit(1)

    output = Path(args.output).resolve()
    wad_dirs = [Path(d).resolve() for d in args.wad_dirs]

    print(f"[pack] Map     : {map_file}")
    print(f"[pack] Output  : {output}")
    print(f"[pack] Scale   : {args.scale}")
    print(f"[pack] WAD dirs: {wad_dirs if wad_dirs else '(none)'}")
    print(f"[pack] Format  : {'directory' if args.dir_bundle else '.irunmap'}")

    # ------------------------------------------------------------------
    # 2. Parse .map
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[pack] Parsing .map file...")
    map_text = map_file.read_text(encoding="utf-8", errors="replace")
    entities = parse_map(map_text)
    elapsed = time.perf_counter() - t0
    total_brushes = sum(len(e.brushes) for e in entities)
    print(f"[pack] Parsed {len(entities)} entities, {total_brushes} brushes ({elapsed:.2f}s)")

    # ------------------------------------------------------------------
    # 3. Collect texture names
    # ------------------------------------------------------------------
    texture_names = _collect_texture_names(entities)
    print(f"[pack] Found {len(texture_names)} unique texture references")

    # ------------------------------------------------------------------
    # 4. Prepare output directory
    # ------------------------------------------------------------------
    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.dir_bundle:
        out_dir = output
        out_dir.mkdir(parents=True, exist_ok=True)
        packed_out: Path | None = None
    else:
        packed_out = output
        packed_out.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = tempfile.TemporaryDirectory(
            prefix=f"irun-pack-{map_file.stem}-",
            dir=str(packed_out.parent),
        )
        out_dir = Path(tmp_dir.name)

    try:
        materials_dir = out_dir / "materials"
        materials_dir.mkdir(parents=True, exist_ok=True)

        # ----------------------------------------------------------
        # 5. Extract WAD textures
        # ----------------------------------------------------------
        t0 = time.perf_counter()
        wad_paths = _discover_wads(wad_dirs)
        if wad_paths:
            print(f"\n[pack] Found {len(wad_paths)} WAD file(s), extracting textures...")
            extracted = _extract_wad_textures(wad_paths, texture_names, materials_dir)
            elapsed = time.perf_counter() - t0
            print(f"[pack] Extracted {extracted} textures ({elapsed:.2f}s)")
        else:
            print("[pack] No WAD files found; skipping texture extraction.")

        # ----------------------------------------------------------
        # 6. Resolve material definitions
        # ----------------------------------------------------------
        _resolve_materials(texture_names, materials_dir)

        # ----------------------------------------------------------
        # 7. Convert brush geometry to triangles
        # ----------------------------------------------------------
        t0 = time.perf_counter()
        print("\n[pack] Converting brushes to triangles...")
        render_tris, collision_tris, min_v, max_v = _convert_geometry(entities, args.scale)
        elapsed = time.perf_counter() - t0
        print(
            f"[pack] {len(render_tris)} render triangles, "
            f"{len(collision_tris)} collision triangles ({elapsed:.2f}s)"
        )

        # ----------------------------------------------------------
        # 8. Pick spawn point
        # ----------------------------------------------------------
        spawn_pos, spawn_yaw = _pick_spawn(entities, args.scale)

        # ----------------------------------------------------------
        # 9. Write map.json
        # ----------------------------------------------------------
        skyname = None
        for ent in entities:
            if ent.properties.get("classname") == "worldspawn":
                skyname = ent.properties.get("skyname") or ent.properties.get("sky")
                break

        map_id = map_file.stem
        payload = {
            "format_version": 2,
            "map_id": map_id,
            "source_map": str(map_file),
            "scale": float(args.scale),
            "triangle_count": len(render_tris),
            "collision_triangle_count": len(collision_tris),
            "bounds": {"min": min_v, "max": max_v},
            "spawn": {"position": spawn_pos, "yaw": spawn_yaw},
            "skyname": skyname,
            "materials": {
                "root": None,
                "converted_root": "materials",
                "converted": len(list(materials_dir.glob("*.png"))),
            },
            "lightmaps": None,
            "lightstyles": {},
            "resources": {
                "root": "resources",
                "copied": [],
                "missing": [],
                "skipped": [],
                "copied_enabled": False,
            },
            "collision_triangles": collision_tris,
            "triangles": render_tris,
            "brush_models": [],
        }

        map_json = out_dir / "map.json"
        map_json.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

        # ----------------------------------------------------------
        # 10. Pack into .irunmap if needed
        # ----------------------------------------------------------
        if packed_out is not None:
            t0 = time.perf_counter()
            print(f"\n[pack] Packing {packed_out}...")
            pack_bundle_dir_to_irunmap(bundle_dir=out_dir, out_path=packed_out, compresslevel=1)
            elapsed = time.perf_counter() - t0
            print(f"[pack] Packed ({elapsed:.2f}s)")

        total_elapsed = time.perf_counter() - total_t0
        final_path = packed_out if packed_out else out_dir
        print(f"\n[pack] Done! Total time: {total_elapsed:.1f}s")
        print(f"[pack] Output: {final_path}")

    finally:
        if tmp_dir is not None:
            try:
                tmp_dir.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    main()
