from __future__ import annotations

import argparse
import json
from pathlib import Path

import bsp_tool
from PIL import Image

from vtf_decode import decode_vtf_highres_rgba


def parse_origin(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    parts = value.split()
    if len(parts) != 3:
        return None
    return float(parts[0]), float(parts[1]), float(parts[2])


def parse_angles(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    parts = value.split()
    if len(parts) != 3:
        return None
    return float(parts[0]), float(parts[1]), float(parts[2])


def convert_pos(pos, scale: float) -> list[float]:
    # Source -> Panda convention: keep Z-up and flip Y to keep handedness usable in Panda scene.
    return [float(pos.x) * scale, -float(pos.y) * scale, float(pos.z) * scale]


def convert_normal(n) -> list[float]:
    # Flip Y to match convert_pos; normals are unit vectors (no scaling).
    return [float(n.x), -float(n.y), float(n.z)]

def convert_uv(uv) -> list[float]:
    # Source BSP UV convention is effectively upside-down compared to how Panda3D
    # samples images loaded from PNG. Flip V to match expected in-game orientation.
    return [float(uv.x), -float(uv.y)]


def pick_spawn(entities, scale: float) -> tuple[list[float], float]:
    fallback = ([0.0, 0.0, 2.0], 0.0)
    for ent in entities:
        if ent.get("classname") != "info_deathmatch_spawn":
            continue
        origin = parse_origin(ent.get("origin"))
        if not origin:
            continue
        angles = parse_angles(ent.get("angles"))
        yaw = float(angles[1]) if angles else 0.0
        pos = [origin[0] * scale, -origin[1] * scale, origin[2] * scale]
        return (pos, yaw)
    return fallback


def skyname_from_entities(entities) -> str | None:
    for ent in entities:
        if ent.get("classname") == "worldspawn":
            name = ent.get("skyname")
            if isinstance(name, str) and name.strip():
                return name.strip()
            return None
    return None


def _vtf_to_png(vtf_path: Path, png_path: Path) -> None:
    w, h, rgba = decode_vtf_highres_rgba(vtf_path)
    img = Image.frombytes("RGBA", (w, h), rgba)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path)


def convert_material_textures(*, materials_root: Path, out_root: Path) -> int:
    converted = 0
    for vtf in materials_root.rglob("*.vtf"):
        rel = vtf.relative_to(materials_root)
        out = out_root / rel.with_suffix(".png")
        if out.exists() and out.stat().st_mtime >= vtf.stat().st_mtime:
            continue
        _vtf_to_png(vtf, out)
        converted += 1
    return converted


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a Source BSP into IVAN runtime assets (triangles + textures).")
    parser.add_argument("--input", required=True, help="Path to a Source BSP file.")
    parser.add_argument("--output", required=True, help="Output JSON path (map bundle).")
    parser.add_argument("--map-id", default=None, help="Optional map id for debugging/node naming.")
    parser.add_argument("--scale", type=float, default=0.03, help="Source-to-game unit scale.")
    parser.add_argument("--materials-root", required=True, help="Folder containing Source materials (VTF/VMT).")
    parser.add_argument(
        "--materials-out",
        required=True,
        help="Output folder for converted textures (PNG). Recommended: <map-bundle-dir>/materials",
    )
    args = parser.parse_args()

    bsp_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bsp = bsp_tool.load_bsp(str(bsp_path))

    # Triangles include material + UV + vertex color for baked lighting.
    triangles: list[dict] = []
    min_v = [float("inf"), float("inf"), float("inf")]
    max_v = [float("-inf"), float("-inf"), float("-inf")]

    face_count = len(bsp.FACES)
    for face_idx in range(face_count):
        try:
            mesh = bsp.face_mesh(face_idx)
        except Exception:
            continue

        mat_name = mesh.material.name if getattr(mesh, "material", None) is not None else "unknown"

        for poly in mesh.polygons:
            if len(poly.vertices) < 3:
                continue

            verts = poly.vertices
            for i in range(1, len(verts) - 1):
                v0 = verts[0]
                v1 = verts[i]
                v2 = verts[i + 1]

                p0 = convert_pos(v0.position, args.scale)
                p1 = convert_pos(v1.position, args.scale)
                p2 = convert_pos(v2.position, args.scale)

                n0 = convert_normal(v0.normal)
                n1 = convert_normal(v1.normal)
                n2 = convert_normal(v2.normal)

                # bsp_tool provides UV pairs: [base, lightmap].
                uv0 = convert_uv(v0.uv[0])
                uv1 = convert_uv(v1.uv[0])
                uv2 = convert_uv(v2.uv[0])
                lm0 = convert_uv(v0.uv[1])
                lm1 = convert_uv(v1.uv[1])
                lm2 = convert_uv(v2.uv[1])

                c0 = list(map(float, v0.colour))
                c1 = list(map(float, v1.colour))
                c2 = list(map(float, v2.colour))

                tri = {
                    "m": mat_name,
                    "p": [*p0, *p1, *p2],
                    "n": [*n0, *n1, *n2],
                    "uv": [*uv0, *uv1, *uv2],
                    "lm": [*lm0, *lm1, *lm2],
                    "c": [*c0, *c1, *c2],
                }
                triangles.append(tri)
                for j in range(0, 9, 3):
                    px, py, pz = tri["p"][j], tri["p"][j + 1], tri["p"][j + 2]
                    min_v[0] = min(min_v[0], px)
                    min_v[1] = min(min_v[1], py)
                    min_v[2] = min(min_v[2], pz)
                    max_v[0] = max(max_v[0], px)
                    max_v[1] = max(max_v[1], py)
                    max_v[2] = max(max_v[2], pz)

    spawn_pos, spawn_yaw = pick_spawn(bsp.ENTITIES, args.scale)
    skyname = skyname_from_entities(bsp.ENTITIES)

    materials_root = Path(args.materials_root)
    materials_out = Path(args.materials_out)
    converted = convert_material_textures(materials_root=materials_root, out_root=materials_out)

    # Prefer a materials path relative to the map bundle for portability.
    try:
        materials_out_rel = str(materials_out.resolve().relative_to(out_path.parent.resolve()))
    except Exception:
        materials_out_rel = str(materials_out)

    payload = {
        "format_version": 2,
        "map_id": args.map_id or out_path.stem,
        "source_bsp": str(bsp_path),
        "scale": args.scale,
        "triangle_count": len(triangles),
        "bounds": {"min": min_v, "max": max_v},
        "spawn": {"position": spawn_pos, "yaw": spawn_yaw},
        "skyname": skyname,
        "materials": {
            "root": str(materials_root),
            "converted_root": materials_out_rel,
            "converted": converted,
        },
        "triangles": triangles,
    }

    out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} with {len(triangles)} triangles")


if __name__ == "__main__":
    main()
