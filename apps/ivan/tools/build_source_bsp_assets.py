from __future__ import annotations

import argparse
import json
from pathlib import Path

import bsp_tool
from PIL import Image

from vtf_decode import decode_vtf_highres_rgba


def _read_text_lossy(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


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
    # Keep BSP coordinates in the same space as the runtime (scale only).
    return [float(pos.x) * scale, float(pos.y) * scale, float(pos.z) * scale]


def convert_normal(n) -> list[float]:
    # Normals are unit vectors (no scaling).
    return [float(n.x), float(n.y), float(n.z)]

def convert_uv_base(uv) -> list[float]:
    # Source BSP UV convention is effectively upside-down compared to how Panda3D
    # samples images loaded from PNG. Flip V to match expected in-game orientation.
    return [float(uv.x), -float(uv.y)]

def convert_uv_lightmap(uv) -> list[float]:
    # bsp_tool produces lightmap UVs in [0..1] for Source BSPs. Keep them as-is.
    return [float(uv.x), float(uv.y)]


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
        pos = [origin[0] * scale, origin[1] * scale, origin[2] * scale]
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
        try:
            _vtf_to_png(vtf, out)
            converted += 1
        except Exception:
            # Keep import resilient when a map references exotic/unsupported VTF encodings.
            # Runtime falls back to checker for missing converted textures.
            continue
    return converted


def _tokenize_vmt(text: str) -> list[str]:
    # Minimal KeyValues tokenizer:
    # - supports quoted strings
    # - treats { and } as separate tokens
    # - strips // comments
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        i = 0
        while i < len(line):
            c = line[i]
            if c.isspace():
                i += 1
                continue
            if c in "{}":
                out.append(c)
                i += 1
                continue
            if c == '"':
                i += 1
                j = i
                while j < len(line) and line[j] != '"':
                    j += 1
                out.append(line[i:j])
                i = j + 1
                continue
            j = i
            while j < len(line) and (not line[j].isspace()) and line[j] not in "{}":
                j += 1
            out.append(line[i:j])
            i = j
    return out


def parse_vmt(text: str) -> dict[str, str]:
    """
    Parse a VMT (Valve Material) file into a flat dict of top-level key/value strings.

    This intentionally ignores nested blocks and advanced KeyValues features; we only need
    a few common keys to drive runtime rendering (base texture + transparency hints).
    """
    toks = _tokenize_vmt(text)
    # Usually: <shader> { <k> <v> ... }
    i = 0
    # Skip the first token (shader name) if present.
    if i < len(toks) and toks[i] not in ("{", "}"):
        i += 1
    # Seek first "{"
    while i < len(toks) and toks[i] != "{":
        i += 1
    if i >= len(toks) or toks[i] != "{":
        return {}
    i += 1
    depth = 1
    out: dict[str, str] = {}
    while i < len(toks) and depth > 0:
        t = toks[i]
        if t == "{":
            depth += 1
            i += 1
            continue
        if t == "}":
            depth -= 1
            i += 1
            continue
        if depth != 1:
            i += 1
            continue
        # depth == 1: parse key/value if present
        if i + 1 < len(toks) and toks[i + 1] not in ("{", "}"):
            key = toks[i].strip()
            val = toks[i + 1].strip()
            if key:
                out[key.casefold()] = val
            i += 2
            continue
        i += 1
    return out


def _normalize_vmt_ref(s: str) -> str:
    ref = s.strip().strip('"').replace("\\", "/").strip()
    if ref.casefold().startswith("materials/"):
        ref = ref[len("materials/") :]
    return ref.casefold().removesuffix(".vmt")


def _resolve_vmt_kv(
    *,
    vmt_path: Path,
    vmt_index: dict[str, Path],
    cache: dict[str, dict[str, str]],
    stack: set[str] | None = None,
) -> dict[str, str]:
    key = str(vmt_path).casefold()
    if key in cache:
        return cache[key]
    if stack is None:
        stack = set()
    if key in stack:
        return {}
    stack.add(key)

    kv = parse_vmt(_read_text_lossy(vmt_path))
    include_ref = kv.get("include")
    merged: dict[str, str] = {}
    if isinstance(include_ref, str) and include_ref.strip():
        inc = _normalize_vmt_ref(include_ref)
        inc_path = vmt_index.get(inc)
        if inc_path and inc_path.exists():
            merged.update(_resolve_vmt_kv(vmt_path=inc_path, vmt_index=vmt_index, cache=cache, stack=stack))

    merged.update(kv)
    cache[key] = merged
    stack.discard(key)
    return merged


def _parse_boolish(s: str | None) -> bool:
    if s is None:
        return False
    t = s.strip().strip('"').casefold()
    return t in ("1", "true", "yes", "on")


def _parse_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.strip().strip('"'))
    except Exception:
        return None


def build_vmt_index(materials_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in materials_root.rglob("*.vmt"):
        rel = p.relative_to(materials_root)
        key = str(rel.with_suffix("")).replace("\\", "/").casefold()
        index[key] = p
    return index


def _decode_rgbexp32_to_rgba(raw: bytes) -> bytes:
    """
    Decode Source `ColorRGBExp32` (r,g,b,exp) to 8-bit RGBA.

    This is a pragmatic decode for lightmaps:
    - scale = 2^exp (exp is signed int8)
    - component = clamp(r * scale, 0..255)
    """
    if len(raw) % 4 != 0:
        raw = raw[: len(raw) - (len(raw) % 4)]
    out = bytearray((len(raw) // 4) * 4)
    for i in range(0, len(raw), 4):
        r = raw[i + 0]
        g = raw[i + 1]
        b = raw[i + 2]
        exp_u8 = raw[i + 3]
        exp = exp_u8 - 256 if exp_u8 >= 128 else exp_u8
        scale = 2.0**exp
        rr = int(r * scale)
        gg = int(g * scale)
        bb = int(b * scale)
        if rr < 0:
            rr = 0
        elif rr > 255:
            rr = 255
        if gg < 0:
            gg = 0
        elif gg > 255:
            gg = 255
        if bb < 0:
            bb = 0
        elif bb > 255:
            bb = 255
        out[i + 0] = rr
        out[i + 1] = gg
        out[i + 2] = bb
        out[i + 3] = 255
    return bytes(out)


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
    parser.add_argument(
        "--lightmaps-out",
        required=False,
        default=None,
        help="Output folder for extracted lightmap PNGs. Default: <map-bundle-dir>/lightmaps",
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
    lightmaps_out = Path(args.lightmaps_out) if args.lightmaps_out else (out_path.parent / "lightmaps")
    lightmaps_out.mkdir(parents=True, exist_ok=True)
    # Source lightmaps are in LIGHTING_HDR for HDR builds; fall back to LIGHTING when needed.
    lighting_lump = getattr(bsp, "LIGHTING_HDR", None) or getattr(bsp, "LIGHTING", None)

    # Best-effort: build VMT index once; we only read VMT metadata for materials actually referenced.
    materials_root = Path(args.materials_root)
    vmt_index = build_vmt_index(materials_root)
    resolved_vmt_cache: dict[str, dict[str, str]] = {}
    materials_meta: dict[str, dict] = {}

    # Per-face lightmap textures (kept small and simple; batching/atlasing can come later).
    face_lightmaps: dict[str, str] = {}

    for face_idx in range(face_count):
        try:
            mesh = bsp.face_mesh(face_idx)
        except Exception:
            continue

        mat_name = mesh.material.name if getattr(mesh, "material", None) is not None else "unknown"

        # VMT metadata for runtime rendering (transparency, culling, basetexture override).
        if mat_name not in materials_meta:
            vmt_path = vmt_index.get(mat_name.replace("\\", "/").casefold())
            if vmt_path and vmt_path.exists():
                kv = _resolve_vmt_kv(vmt_path=vmt_path, vmt_index=vmt_index, cache=resolved_vmt_cache)
                base = kv.get("$basetexture")
                meta = {
                    "base_texture": base.strip().strip('"') if isinstance(base, str) and base.strip() else None,
                    "translucent": _parse_boolish(kv.get("$translucent")),
                    "additive": _parse_boolish(kv.get("$additive")),
                    "alphatest": _parse_boolish(kv.get("$alphatest")),
                    "nocull": _parse_boolish(kv.get("$nocull")),
                }
                alpha = _parse_float(kv.get("$alpha"))
                if alpha is not None:
                    meta["alpha"] = float(alpha)
                # Keep map.json small: only store non-empty metadata.
                materials_meta[mat_name] = {k: v for k, v in meta.items() if v not in (None, False)}
            else:
                materials_meta[mat_name] = {}

        # Extract a per-face lightmap PNG if available.
        if lighting_lump is not None and str(face_idx) not in face_lightmaps:
            try:
                face = bsp.FACES[face_idx]
                light_off = int(getattr(face, "light_offset", -1))
                if light_off >= 0 and hasattr(face, "lightmap"):
                    lm = getattr(face, "lightmap")
                    size = getattr(lm, "size", None)
                    if size is not None:
                        w = int(float(getattr(size, "x", 0))) + 1
                        h = int(float(getattr(size, "y", 0))) + 1
                        if w > 0 and h > 0:
                            need = w * h * 4
                            raw = bytes(lighting_lump[light_off : light_off + need])
                            if len(raw) == need:
                                rgba = _decode_rgbexp32_to_rgba(raw)
                                img = Image.frombytes("RGBA", (w, h), rgba)
                                dst = lightmaps_out / f"f{face_idx}.png"
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                img.save(dst)
                                # Prefer a path relative to the bundle for portability.
                                try:
                                    rel = str(dst.resolve().relative_to(out_path.parent.resolve())).replace("\\", "/")
                                except Exception:
                                    rel = str(dst)
                                face_lightmaps[str(face_idx)] = rel
            except Exception:
                pass

        for poly in mesh.polygons:
            if len(poly.vertices) < 3:
                continue

            verts = poly.vertices
            for i in range(1, len(verts) - 1):
                v0 = verts[0]
                # Keep coordinates unmirrored and instead flip triangle winding here
                # so Panda3D backface culling matches expected front faces.
                v1 = verts[i + 1]
                v2 = verts[i]

                p0 = convert_pos(v0.position, args.scale)
                p1 = convert_pos(v1.position, args.scale)
                p2 = convert_pos(v2.position, args.scale)

                n0 = convert_normal(v0.normal)
                n1 = convert_normal(v1.normal)
                n2 = convert_normal(v2.normal)

                # bsp_tool provides UV pairs: [base, lightmap].
                uv0 = convert_uv_base(v0.uv[0])
                uv1 = convert_uv_base(v1.uv[0])
                uv2 = convert_uv_base(v2.uv[0])
                lm0 = convert_uv_lightmap(v0.uv[1])
                lm1 = convert_uv_lightmap(v1.uv[1])
                lm2 = convert_uv_lightmap(v2.uv[1])

                c0 = list(map(float, v0.colour))
                c1 = list(map(float, v1.colour))
                c2 = list(map(float, v2.colour))

                tri = {
                    "m": mat_name,
                    "lmi": face_idx if str(face_idx) in face_lightmaps else None,
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
        "materials_meta": materials_meta,
        "lightmaps": {"faces": face_lightmaps},
        "triangles": triangles,
    }

    out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} with {len(triangles)} triangles")


if __name__ == "__main__":
    main()
