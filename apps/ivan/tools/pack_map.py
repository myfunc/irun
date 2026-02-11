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
        [--profile dev-fast|prod-baked] \\
        [--dir-bundle]
"""

from __future__ import annotations

import argparse
import json
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
from ivan.maps.bundle_io import pack_bundle_dir_to_irunmap  # noqa: E402

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

from pipeline_profiles import (  # noqa: E402
    PROFILE_DEV_FAST,
    add_profile_argument,
    get_profile,
)

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
# Light and fog extraction (map.json payload parity with BSP importer)
# ---------------------------------------------------------------------------

def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _extract_light_entities(entities: list[MapEntity], scale: float) -> list[dict]:
    """Extract light, light_spot, light_environment entities for map.json lights payload."""
    out: list[dict] = []
    for ent in entities:
        cn = ent.properties.get("classname", "").strip().lower()
        if cn not in {"light", "light_spot", "light_environment"}:
            continue
        origin_raw = ent.properties.get("origin")
        if not origin_raw:
            continue
        parts = origin_raw.split()
        if len(parts) != 3:
            continue
        try:
            ox, oy, oz = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue

        # GoldSrc _light "R G B I" or _color + light
        light_raw = ent.properties.get("_light", "").strip()
        lp = light_raw.split() if light_raw else []
        r, g, b, intensity = 255.0, 255.0, 255.0, 200.0
        if len(lp) >= 3:
            try:
                r, g, b = float(lp[0]), float(lp[1]), float(lp[2])
                if len(lp) >= 4:
                    intensity = float(lp[3])
            except ValueError:
                pass
        else:
            color_raw = ent.properties.get("_color", "255 255 255")
            try:
                cp = color_raw.split()
                if len(cp) >= 3:
                    r, g, b = float(cp[0]), float(cp[1]), float(cp[2])
            except ValueError:
                pass
            intensity = _parse_float(ent.properties.get("light"), 200.0)

        pitch = _parse_float(ent.properties.get("pitch"), 0.0)
        angles_raw = ent.properties.get("angles", "0 0 0").split()
        angles = (0.0, 0.0, 0.0)
        if len(angles_raw) >= 3:
            try:
                angles = (float(angles_raw[0]), float(angles_raw[1]), float(angles_raw[2]))
            except ValueError:
                pass
        if cn == "light_environment" and angles == (0.0, 0.0, 0.0):
            angles = (0.0, _parse_float(ent.properties.get("angle"), 0.0), 0.0)

        out.append({
            "classname": cn,
            "origin": [ox * scale, oy * scale, oz * scale],
            "color": [
                max(0.0, min(1.0, r / 255.0)),
                max(0.0, min(1.0, g / 255.0)),
                max(0.0, min(1.0, b / 255.0)),
            ],
            "brightness": float(intensity),
            "pitch": float(pitch),
            "angles": [float(angles[0]), float(angles[1]), float(angles[2])],
            "inner_cone": _parse_float(ent.properties.get("_cone"), 0.0),
            "outer_cone": _parse_float(ent.properties.get("_cone2"), 0.0),
            "fade": _parse_float(ent.properties.get("_fade"), 1.0),
            "falloff": int(_parse_float(ent.properties.get("_falloff"), 0)),
            "style": int(_parse_float(ent.properties.get("style"), 0)),
        })
    return out


def _extract_fog_from_entities(entities: list[MapEntity]) -> dict | None:
    """Extract fog from env_fog or worldspawn (GoldSrc convention). Optional; None if absent."""
    for ent in entities:
        cn = ent.properties.get("classname", "").strip().lower()
        if cn == "env_fog":
            start_s = ent.properties.get("fogstart") or ent.properties.get("fog_start")
            end_s = ent.properties.get("fogend") or ent.properties.get("fog_end")
            color_s = ent.properties.get("fogcolor") or ent.properties.get("fog_color") or "128 128 128"
            try:
                start = float(start_s) if start_s else 80.0
                end = float(end_s) if end_s else 200.0
            except (TypeError, ValueError):
                continue
            parts = str(color_s).split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]) / 255.0, float(parts[1]) / 255.0, float(parts[2]) / 255.0
                    return {"enabled": True, "start": start, "end": end, "color": [r, g, b]}
                except (TypeError, ValueError):
                    pass
    for ent in entities:
        if ent.properties.get("classname") != "worldspawn":
            continue
        start_s = ent.properties.get("fogstart") or ent.properties.get("fog_start")
        end_s = ent.properties.get("fogend") or ent.properties.get("fog_end")
        color_s = ent.properties.get("fogcolor") or ent.properties.get("fog_color")
        if not (start_s and end_s and color_s):
            continue
        try:
            start, end = float(start_s), float(end_s)
        except (TypeError, ValueError):
            continue
        parts = str(color_s).split()
        if len(parts) >= 3:
            try:
                r, g, b = float(parts[0]) / 255.0, float(parts[1]) / 255.0, float(parts[2]) / 255.0
                return {"enabled": True, "start": start, "end": end, "color": [r, g, b]}
            except (TypeError, ValueError):
                pass
    return None


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
    add_profile_argument(parser)
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

    profile = get_profile(args)
    compresslevel = 0 if profile == PROFILE_DEV_FAST else 6

    print(f"[pack] Map     : {map_file}")
    print(f"[pack] Output  : {output}")
    print(f"[pack] Profile : {profile}")
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
        # 8b. Extract lights and fog
        # ----------------------------------------------------------
        payload_lights = _extract_light_entities(entities, args.scale)
        payload_fog = _extract_fog_from_entities(entities)

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
            "lights": payload_lights,
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
        if payload_fog is not None:
            payload["fog"] = payload_fog

        map_json = out_dir / "map.json"
        map_json.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

        # ----------------------------------------------------------
        # 10. Pack into .irunmap if needed
        # ----------------------------------------------------------
        if packed_out is not None:
            t0 = time.perf_counter()
            print(f"\n[pack] Packing {packed_out}...")
            pack_bundle_dir_to_irunmap(
                bundle_dir=out_dir, out_path=packed_out, compresslevel=compresslevel
            )
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
