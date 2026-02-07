from __future__ import annotations

import argparse
import json
from pathlib import Path

import bsp_tool


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Dust2 Largo generated map asset from BSP.")
    parser.add_argument("--input", required=True, help="Path to Source BSP file.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--scale", type=float, default=0.03, help="Source-to-game unit scale.")
    args = parser.parse_args()

    bsp_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bsp = bsp_tool.load_bsp(str(bsp_path))

    triangles: list[list[float]] = []
    min_v = [float("inf"), float("inf"), float("inf")]
    max_v = [float("-inf"), float("-inf"), float("-inf")]

    face_count = len(bsp.FACES)
    for face_idx in range(face_count):
        try:
            mesh = bsp.face_mesh(face_idx)
        except Exception:
            continue

        for poly in mesh.polygons:
            if len(poly.vertices) < 3:
                continue

            verts = [convert_pos(v.position, args.scale) for v in poly.vertices]
            for i in range(1, len(verts) - 1):
                tri = [*verts[0], *verts[i], *verts[i + 1]]
                triangles.append(tri)
                for j in range(0, 9, 3):
                    px, py, pz = tri[j], tri[j + 1], tri[j + 2]
                    min_v[0] = min(min_v[0], px)
                    min_v[1] = min(min_v[1], py)
                    min_v[2] = min(min_v[2], pz)
                    max_v[0] = max(max_v[0], px)
                    max_v[1] = max(max_v[1], py)
                    max_v[2] = max(max_v[2], pz)

    spawn_pos, spawn_yaw = pick_spawn(bsp.ENTITIES, args.scale)

    payload = {
        "format_version": 1,
        "source_bsp": str(bsp_path),
        "scale": args.scale,
        "triangle_count": len(triangles),
        "bounds": {"min": min_v, "max": max_v},
        "spawn": {"position": spawn_pos, "yaw": spawn_yaw},
        "triangles": triangles,
    }

    out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} with {len(triangles)} triangles")


if __name__ == "__main__":
    main()
