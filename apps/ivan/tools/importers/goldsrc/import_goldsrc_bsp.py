from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import bsp_tool
from PIL import Image

from goldsrc_wad import Wad3

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

# Brush entity classnames that we treat as solid collision by default.
COLLIDE_BRUSH_CLASSNAMES = {
    "func_breakable",
    "func_button",
    "func_door",
    "func_door_rotating",
    "func_plat",
    "func_pushable",
    "func_rot_button",
    "func_rotating",
    "func_train",
    "func_wall",
}

# Brush entities that render but should not collide.
RENDER_NO_COLLIDE_CLASSNAMES = {
    "func_illusionary",
}

# Avoid copying code/binaries when users point the importer at a full Steam install.
# GoldSrc mods typically store executable game code under these dirs / extensions.
SKIP_RESOURCE_DIRS = {
    "bin",
    "cl_dlls",
    "dlls",
    "plugins",
}
SKIP_RESOURCE_EXTS = {
    ".a",
    ".dylib",
    ".dll",
    ".exe",
    ".lib",
    ".o",
    ".obj",
    ".pdb",
    ".so",
}


def _norm_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./").strip()


def parse_res_file(res_path: Path) -> list[str]:
    out: list[str] = []
    for raw in res_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("//"):
            continue
        line = line.strip().strip('"').strip()
        if not line:
            continue
        out.append(_norm_rel(line))
    return out


def find_case_insensitive(root: Path, rel: str) -> Path | None:
    p = root
    parts = [x for x in _norm_rel(rel).split("/") if x]
    for part in parts:
        direct = p / part
        if direct.exists():
            p = direct
            continue
        if not p.is_dir():
            return None
        matches = [c for c in p.iterdir() if c.name.lower() == part.lower()]
        if not matches:
            return None
        p = matches[0]
    return p


def should_copy_resource(rel: str) -> bool:
    rel = _norm_rel(rel)
    p = Path(rel)
    if any(part.lower() in SKIP_RESOURCE_DIRS for part in p.parts):
        return False
    if p.suffix.lower() in SKIP_RESOURCE_EXTS:
        return False
    return True


def _parse_wad_list(entities) -> list[str]:
    for ent in entities:
        if ent.get("classname") != "worldspawn":
            continue
        w = ent.get("wad")
        if not isinstance(w, str) or not w.strip():
            return []
        # Typically `;`-separated absolute paths.
        parts = [x.strip() for x in w.replace("\\", "/").split(";")]
        names = []
        for p in parts:
            if not p:
                continue
            names.append(Path(p).name)
        return names
    return []


def _parse_origin(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    parts = value.split()
    if len(parts) != 3:
        return None
    return float(parts[0]), float(parts[1]), float(parts[2])


def _parse_angles(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    parts = value.split()
    if len(parts) != 3:
        return None
    return float(parts[0]), float(parts[1]), float(parts[2])


def _pick_spawn(entities, scale: float) -> tuple[list[float], float]:
    fallback = ([0.0, 0.0, 2.0], 0.0)
    for ent in entities:
        if ent.get("classname") not in ("info_player_deathmatch", "info_player_start"):
            continue
        origin = _parse_origin(ent.get("origin"))
        if not origin:
            continue
        angles = _parse_angles(ent.get("angles"))
        yaw = float(angles[1]) if angles else 0.0
        pos = [origin[0] * scale, -origin[1] * scale, origin[2] * scale]
        return (pos, yaw)
    return fallback


def _skyname_from_entities(entities) -> str | None:
    for ent in entities:
        if ent.get("classname") == "worldspawn":
            name = ent.get("skyname")
            if isinstance(name, str) and name.strip():
                return name.strip()
            return None
    return None


def _scan_entities_for_resources(entities) -> set[str]:
    exts = (".wav", ".mp3", ".mdl", ".spr", ".tga", ".bmp", ".wad", ".txt", ".cfg", ".res")
    out: set[str] = set()
    for ent in entities:
        for _, v in ent.items():
            if not isinstance(v, str):
                continue
            s = v.strip().strip('"').strip()
            if not s or s.startswith("*"):
                continue
            s = _norm_rel(s)
            low = s.lower()
            if any(low.endswith(ext) for ext in exts) and ("/" in s or "\\" in v):
                out.add(s)
            # Common GoldSrc convention: sound paths are often stored without leading "sound/".
            if low.endswith(".wav") and not low.startswith("sound/"):
                out.add("sound/" + s)
            if low.endswith(".mp3") and not low.startswith("sound/"):
                out.add("sound/" + s)
            if low.endswith(".mdl") and not low.startswith("models/"):
                out.add("models/" + s)
            if low.endswith(".spr") and not low.startswith("sprites/"):
                out.add("sprites/" + s)
    return out


def _save_png(dst: Path, *, width: int, height: int, rgba: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.frombytes("RGBA", (width, height), rgba)
    img.save(dst)


def _should_render_texture(mat_name: str) -> bool:
    m = mat_name.strip().lower()
    if m in NO_RENDER_TEXTURES:
        return False
    return True


def _model_index_from_entity(ent: dict) -> int | None:
    m = ent.get("model")
    if not isinstance(m, str):
        return None
    m = m.strip()
    if not m.startswith("*"):
        return None
    try:
        return int(m[1:])
    except Exception:
        return None


def _decode_miptex_name(name) -> str:
    # bsp_tool uses bytes for miptex names in GoldSrc lumps.
    if isinstance(name, bytes):
        if b"\x00" in name:
            name = name.split(b"\x00", 1)[0]
        try:
            return name.decode("ascii", errors="ignore").strip()
        except Exception:
            return ""
    if isinstance(name, str):
        return name.strip()
    return ""


def _collect_used_texture_names(bsp) -> set[str]:
    used: set[str] = set()
    mip = getattr(bsp, "MIP_TEXTURES", None)
    if mip is None:
        return used
    for entry in mip:
        # GoldSrc: each element looks like (MipTexture(...), [mip0..mip3 bytes]).
        if isinstance(entry, tuple) and entry:
            mt = entry[0]
        else:
            mt = entry
        name = _decode_miptex_name(getattr(mt, "name", mt))
        if not name:
            continue
        used.add(name)
    return used


def _expand_animated_textures(names: set[str]) -> set[str]:
    # GoldSrc animated textures are commonly +0foo .. +9foo (and sometimes -0foo .. -9foo).
    out = set(names)
    pat = re.compile(r"^([+-])([0-9])(.*)$")
    for n in names:
        m = pat.match(n)
        if not m:
            continue
        sign = m.group(1)
        rest = m.group(3)
        for i in range(10):
            out.add(f"{sign}{i}{rest}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a GoldSrc/Xash3D BSP into an IVAN map bundle (geometry + extracted textures + resource copy)."
    )
    parser.add_argument("--bsp", required=True, help="Path to a GoldSrc/Xash3D BSP file.")
    parser.add_argument(
        "--game-root",
        required=True,
        help="Path to the mod folder (e.g. .../cstrike or .../valve) that contains maps/, sound/, models/, etc.",
    )
    parser.add_argument(
        "--out",
        required=False,
        default=None,
        help="Output directory for the imported map bundle (will write map.json + materials/ + resources/). Not required with --analyze.",
    )
    parser.add_argument("--map-id", default=None, help="Optional map id for debugging/node naming.")
    parser.add_argument("--scale", type=float, default=0.03, help="GoldSrc-to-game unit scale.")
    parser.add_argument(
        "--extract-all-wad-textures",
        action="store_true",
        help="Extract all textures from referenced WADs (default extracts only the textures referenced by the BSP).",
    )
    parser.add_argument(
        "--copy-resources",
        action="store_true",
        help="Copy non-texture resources listed in .res / entity scan into the bundle (sound/models/sprites/etc). Off by default.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze the BSP (WAD list + detected resource refs) and print a JSON report to stdout without writing a bundle.",
    )
    args = parser.parse_args()

    if not args.analyze and not args.out:
        parser.error("--out is required unless --analyze is set.")

    bsp_path = Path(args.bsp)
    game_root = Path(args.game_root)
    out_dir = Path(args.out or ".")
    if not args.analyze:
        out_dir.mkdir(parents=True, exist_ok=True)

    map_name = bsp_path.stem
    map_id = args.map_id or map_name
    map_json = out_dir / "map.json"

    bsp = bsp_tool.load_bsp(str(bsp_path))

    entities = getattr(bsp, "ENTITIES", [])
    spawn_pos, spawn_yaw = _pick_spawn(entities, args.scale)
    skyname = _skyname_from_entities(entities)

    model_entities: dict[int, dict] = {}
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        idx = _model_index_from_entity(ent)
        if idx is None:
            continue
        model_entities.setdefault(idx, ent)

    # Build triangles (best-effort; depends on bsp_tool support for the given BSP branch).
    render_triangles: list[dict] = []
    collision_triangles: list[list[float]] = []
    min_v = [float("inf"), float("inf"), float("inf")]
    max_v = [float("-inf"), float("-inf"), float("-inf")]

    brush_model_report: list[dict] = []
    models = getattr(bsp, "MODELS", [])
    for model_idx, model in enumerate(models):
        ent = model_entities.get(model_idx)
        classname = ent.get("classname") if isinstance(ent, dict) else None
        classname = classname if isinstance(classname, str) else ""
        cname = classname.strip().lower()

        if model_idx == 0:
            render_model = True
            collide_model = True
        elif cname.startswith("trigger_"):
            render_model = False
            collide_model = False
        elif cname in RENDER_NO_COLLIDE_CLASSNAMES:
            render_model = True
            collide_model = False
        elif cname in COLLIDE_BRUSH_CLASSNAMES:
            render_model = True
            collide_model = True
        else:
            # Conservative default: avoid importing invisible blockers.
            render_model = True
            collide_model = False

        first_face = getattr(model, "first_face", None)
        num_faces = getattr(model, "num_faces", None)
        if not isinstance(first_face, int) or not isinstance(num_faces, int) or num_faces <= 0:
            continue

        brush_model_report.append(
            {
                "model": int(model_idx),
                "classname": cname,
                "faces": [int(first_face), int(first_face + num_faces)],
                "render": bool(render_model),
                "collide": bool(collide_model),
            }
        )

        if not (render_model or collide_model):
            continue

        for face_idx in range(int(first_face), int(first_face + num_faces)):
            try:
                mesh = bsp.face_mesh(face_idx)
            except Exception:
                continue

            mat_name = mesh.material.name if getattr(mesh, "material", None) is not None else "unknown"
            mat_name = str(mat_name).strip()
            tri_renders = render_model and _should_render_texture(mat_name)

            for poly in mesh.polygons:
                if len(poly.vertices) < 3:
                    continue
                verts = poly.vertices
                for i in range(1, len(verts) - 1):
                    v0 = verts[0]
                    v1 = verts[i]
                    v2 = verts[i + 1]

                    # Same coordinate convention as Source conversion: flip Y.
                    p0 = [
                        float(v0.position.x) * args.scale,
                        -float(v0.position.y) * args.scale,
                        float(v0.position.z) * args.scale,
                    ]
                    p1 = [
                        float(v1.position.x) * args.scale,
                        -float(v1.position.y) * args.scale,
                        float(v1.position.z) * args.scale,
                    ]
                    p2 = [
                        float(v2.position.x) * args.scale,
                        -float(v2.position.y) * args.scale,
                        float(v2.position.z) * args.scale,
                    ]
                    pos9 = [*p0, *p1, *p2]

                    if collide_model:
                        collision_triangles.append(pos9)

                    if tri_renders:
                        n0 = [float(v0.normal.x), -float(v0.normal.y), float(v0.normal.z)]
                        n1 = [float(v1.normal.x), -float(v1.normal.y), float(v1.normal.z)]
                        n2 = [float(v2.normal.x), -float(v2.normal.y), float(v2.normal.z)]

                        # Some GoldSrc branches may not provide UV pairs; treat as best-effort.
                        try:
                            # BSP UV convention is effectively upside-down compared to how Panda3D
                            # samples images loaded from PNG. Flip V to match expected in-game orientation.
                            uv0 = [float(v0.uv[0].x), -float(v0.uv[0].y)]
                            uv1 = [float(v1.uv[0].x), -float(v1.uv[0].y)]
                            uv2 = [float(v2.uv[0].x), -float(v2.uv[0].y)]
                        except Exception:
                            uv0 = [0.0, 0.0]
                            uv1 = [0.0, 0.0]
                            uv2 = [0.0, 0.0]

                        # No baked vertex lighting for GoldSrc in this importer yet; keep white.
                        c0 = [1.0, 1.0, 1.0, 1.0]
                        c1 = [1.0, 1.0, 1.0, 1.0]
                        c2 = [1.0, 1.0, 1.0, 1.0]

                        tri = {
                            "m": mat_name,
                            "p": pos9,
                            "n": [
                                *n0,
                                *n1,
                                *n2,
                            ],
                            "uv": [*uv0, *uv1, *uv2],
                            "lm": [0.0] * 6,
                            "c": [*c0, *c1, *c2],
                        }
                        render_triangles.append(tri)

                    for j in range(0, 9, 3):
                        px, py, pz = pos9[j], pos9[j + 1], pos9[j + 2]
                        min_v[0] = min(min_v[0], px)
                        min_v[1] = min(min_v[1], py)
                        min_v[2] = min(min_v[2], pz)
                        max_v[0] = max(max_v[0], px)
                        max_v[1] = max(max_v[1], py)
                        max_v[2] = max(max_v[2], pz)

    # Resources: .res file + entity scan.
    res_path = bsp_path.with_suffix(".res")
    resources: set[str] = set()
    if res_path.exists():
        resources.update(parse_res_file(res_path))
    resources.update(_scan_entities_for_resources(entities))

    wad_names = _parse_wad_list(entities)
    for w in wad_names:
        resources.add(_norm_rel(w))

    # Used by the default texture extraction mode and useful for analysis output.
    used_textures = _expand_animated_textures(_collect_used_texture_names(bsp))

    if args.analyze:
        report = {
            "bsp": str(bsp_path),
            "game_root": str(game_root),
            "map_id": map_id,
            "scale": float(args.scale),
            "wad_names": wad_names,
            "used_textures": sorted(used_textures),
            "resources_detected": sorted(resources),
            "copy_policy": {
                "skip_dirs": sorted(SKIP_RESOURCE_DIRS),
                "skip_exts": sorted(SKIP_RESOURCE_EXTS),
            },
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    # Copy resources into bundle under resources/<path>.
    copied: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []
    if args.copy_resources:
        for rel in sorted(resources):
            if not should_copy_resource(rel):
                skipped.append(_norm_rel(rel))
                continue
            # Normalize common roots; allow both "sound/..." etc and bare wad names.
            src = find_case_insensitive(game_root, rel)
            if src is None:
                # If this is a bare WAD name, try common subdirs.
                if rel.lower().endswith(".wad"):
                    for sub in ("", "maps", "wads", "WAD", "gfx", "cstrike", "valve"):
                        cand = find_case_insensitive(game_root / sub, rel)
                        if cand is not None:
                            src = cand
                            break
            if src is None or not src.exists():
                missing.append(rel)
                continue
            dst = out_dir / "resources" / _norm_rel(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(_norm_rel(rel))

    # Extract textures from referenced WADs into bundle materials/.
    materials_dir = out_dir / "materials"
    extracted_textures: int = 0
    used_cf = {u.casefold() for u in used_textures}
    for wad_name in wad_names:
        wad_src = None
        # WAD paths in worldspawn are often absolute; treat as filename.
        wad_file = Path(wad_name).name
        for sub in ("", "wads", "WAD", "maps"):
            cand = find_case_insensitive(game_root / sub, wad_file)
            if cand and cand.exists():
                wad_src = cand
                break
        if wad_src is None:
            continue

        try:
            wad = Wad3.load(wad_src)
        except Exception:
            continue
        for tex in wad.iter_textures():
            if not args.extract_all_wad_textures:
                # Only extract textures used by this BSP (keeps import fast and bundle small).
                if tex.name.casefold() not in used_cf:
                    continue
                if not _should_render_texture(tex.name):
                    continue
            dst = materials_dir / f"{tex.name}.png"
            if dst.exists():
                continue
            try:
                _save_png(dst, width=tex.width, height=tex.height, rgba=tex.rgba)
                extracted_textures += 1
            except Exception:
                continue

    payload = {
        "format_version": 2,
        "map_id": map_id,
        "source_bsp": str(bsp_path),
        "scale": float(args.scale),
        "triangle_count": len(render_triangles),
        "collision_triangle_count": len(collision_triangles),
        "bounds": {"min": min_v, "max": max_v},
        "spawn": {"position": spawn_pos, "yaw": spawn_yaw},
        "skyname": skyname,
        "materials": {"root": None, "converted_root": "materials", "converted": extracted_textures},
        "resources": {
            "root": "resources",
            "copied": copied,
            "missing": missing,
            "skipped": skipped,
            "copied_enabled": bool(args.copy_resources),
            "skip_policy": {"dirs": sorted(SKIP_RESOURCE_DIRS), "exts": sorted(SKIP_RESOURCE_EXTS)},
        },
        "collision_triangles": collision_triangles,
        "triangles": render_triangles,
        "brush_models": brush_model_report,
    }
    map_json.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(
        f"Wrote {map_json} (render_tris={len(render_triangles)}, collision_tris={len(collision_triangles)}, "
        f"textures={extracted_textures}, copied={len(copied)}, missing={len(missing)})"
    )


if __name__ == "__main__":
    main()
