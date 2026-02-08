from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

import bsp_tool
from PIL import Image

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, pack_bundle_dir_to_irunmap
from goldsrc_wad import Wad3
from goldsrc_wad import WadError, decode_wad3_miptex

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
        # GoldSrc BSP coordinates match Panda3D's world axes for our runtime:
        # X right, Y forward, Z up. Keep positions in the same space (scale only).
        pos = [origin[0] * scale, origin[1] * scale, origin[2] * scale]
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


def _try_extract_skybox_textures(*, game_root: Path, materials_dir: Path, skyname: str | None) -> int:
    """
    GoldSrc convention: gfx/env/<skyname><face>.(tga|bmp)

    We convert those into bundle materials under materials/skybox/ so the runtime skybox
    lookup can be shared with the Source pipeline.
    """
    if not skyname:
        return 0
    skyname = skyname.strip()
    if not skyname:
        return 0
    faces = ("ft", "bk", "lf", "rt", "up", "dn")
    exts = (".tga", ".bmp")
    extracted = 0
    for suf in faces:
        src = None
        for ext in exts:
            rel = f"gfx/env/{skyname}{suf}{ext}"
            p = find_case_insensitive(game_root, rel)
            if p and p.exists():
                src = p
                break
        if not src:
            continue
        dst = materials_dir / "skybox" / f"{skyname}{suf}.png"
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            img = Image.open(src)
            img = img.convert("RGBA")
            img.save(dst)
            extracted += 1
        except Exception:
            continue
    return extracted


def _parse_lightmap_scale(entities) -> float:
    """
    GoldSrc/Quake-family lightmap scale is world-units per luxel (typically 16).

    Some toolchains embed overrides in worldspawn keyvalues. Keep this best-effort.
    """

    keys = ("_lightmap_scale", "lightmap_scale", "_world_units_per_luxel", "world_units_per_luxel")
    for ent in entities:
        if not isinstance(ent, dict) or ent.get("classname") != "worldspawn":
            continue
        for k in keys:
            v = ent.get(k)
            if not isinstance(v, str):
                continue
            try:
                f = float(v.strip())
                if f > 0:
                    return float(f)
            except Exception:
                continue
    return 16.0


def _face_style_bytes(face) -> list[int]:
    """
    GoldSrc face light styles are stored as 4 bytes.

    In bsp_tool's current GoldSrc branch, the Face struct is inherited from Quake and names
    the bytes as (lighting_type, base_light, light[0], light[1]). For GoldSrc, interpret
    them as `styles[4]`.
    """

    out: list[int] = []
    for a in ("lighting_type", "base_light"):
        try:
            out.append(int(getattr(face, a)) & 0xFF)
        except Exception:
            out.append(255)
    try:
        l = getattr(face, "light")
        if isinstance(l, (tuple, list)) and len(l) >= 2:
            out.append(int(l[0]) & 0xFF)
            out.append(int(l[1]) & 0xFF)
        else:
            out.extend([255, 255])
    except Exception:
        out.extend([255, 255])

    return _normalize_goldsrc_face_styles(out[:4])


def _normalize_goldsrc_face_styles(styles: list[int]) -> list[int]:
    """
    Normalize a GoldSrc `styles[4]` array.

    GoldSrc expects unused style slots to be 255. Some maps/tools may emit duplicates instead.
    Treat later duplicates as unused to avoid reading extra style blocks from LIGHTING.
    """

    s = [(int(x) & 0xFF) for x in (styles[:4] + [255, 255, 255, 255])[:4]]
    first = int(s[0])
    if first != 255:
        for i in range(1, 4):
            if int(s[i]) == first:
                s[i] = 255
    return s


def _tex_s_t(*, texinfo, pos) -> tuple[float, float]:
    s_axis = texinfo.s.axis
    t_axis = texinfo.t.axis
    s = float(pos.x) * float(s_axis.x) + float(pos.y) * float(s_axis.y) + float(pos.z) * float(s_axis.z) + float(texinfo.s.offset)
    t = float(pos.x) * float(t_axis.x) + float(pos.y) * float(t_axis.y) + float(pos.z) * float(t_axis.z) + float(texinfo.t.offset)
    return (s, t)


def _face_lightmap_meta(*, bsp, face_idx: int, lightmap_scale: float) -> dict | None:
    """
    Compute GoldSrc lightmap extents and return metadata required for extraction + UV mapping.
    """

    try:
        face = bsp.FACES[int(face_idx)]
    except Exception:
        return None
    off = getattr(face, "lighting_offset", None)
    if not isinstance(off, int) or off < 0:
        return None
    try:
        texinfo = bsp.TEXTURE_INFO[face.texture_info]
    except Exception:
        return None

    # Derive a polygon vertex list using bsp_tool's mesh helper (keeps this importer branch-agnostic).
    try:
        mesh = bsp.face_mesh(int(face_idx))
        poly = mesh.polygons[0]
        verts = poly.vertices
        if not verts:
            return None
        positions = [v.position for v in verts]
    except Exception:
        return None

    st = [_tex_s_t(texinfo=texinfo, pos=p) for p in positions]
    ss = [x[0] for x in st]
    ts = [x[1] for x in st]
    min_s = min(ss)
    max_s = max(ss)
    min_t = min(ts)
    max_t = max(ts)

    scale = float(lightmap_scale)
    mins_s = int(math.floor(min_s / scale))
    mins_t = int(math.floor(min_t / scale))
    maxs_s = int(math.ceil(max_s / scale))
    maxs_t = int(math.ceil(max_t / scale))
    w = int(maxs_s - mins_s + 1)
    h = int(maxs_t - mins_t + 1)
    if w <= 0 or h <= 0:
        return None

    styles = _face_style_bytes(face)
    if all(int(s) == 255 for s in styles):
        # Technically "no styles" means "no lightmap".
        return None

    return {
        "offset": int(off),
        "styles": [int(s) for s in styles],
        "mins_s": int(mins_s),
        "mins_t": int(mins_t),
        "w": int(w),
        "h": int(h),
        "scale": float(scale),
    }


def _decode_goldsrc_lightmap_rgb_to_rgba(raw: bytes) -> bytes:
    if len(raw) % 3 != 0:
        raw = raw[: len(raw) - (len(raw) % 3)]
    out = bytearray((len(raw) // 3) * 4)
    oi = 0
    for i in range(0, len(raw), 3):
        out[oi + 0] = raw[i + 0]
        out[oi + 1] = raw[i + 1]
        out[oi + 2] = raw[i + 2]
        out[oi + 3] = 255
        oi += 4
    return bytes(out)


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


def _discover_wad_files(game_root: Path) -> list[Path]:
    """
    Best-effort WAD discovery.

    Some GoldSrc maps omit the worldspawn "wad" key. In that case we fall back to
    scanning common locations under the provided game_root.
    """

    cands: list[Path] = []
    for sub in ("", "wads", "WAD", "maps"):
        d = game_root / sub
        if not d.exists() or not d.is_dir():
            continue
        try:
            cands.extend(sorted(d.glob("*.wad")))
        except Exception:
            continue

    # De-dupe by real path; keep stable ordering.
    seen: set[Path] = set()
    out: list[Path] = []
    for p in cands:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def _extract_embedded_textures(
    *,
    bsp,
    materials_dir: Path,
    used_textures_cf: set[str],
    extract_all: bool,
) -> int:
    """
    Extract textures embedded in the BSP texture lump (MIPTEXTURES).

    Many community maps embed custom textures directly in the BSP. When present,
    this avoids needing external WADs.
    """

    extracted = 0
    mip = getattr(bsp, "MIP_TEXTURES", None)
    if mip is None:
        return 0

    for entry in mip:
        if not (isinstance(entry, tuple) and len(entry) == 2):
            continue
        mt, mips = entry
        if not (isinstance(mips, list) and len(mips) == 4):
            continue
        if not any(isinstance(b, (bytes, bytearray)) and len(b) for b in mips):
            continue

        name = _decode_miptex_name(getattr(mt, "name", mt))
        if not name:
            continue
        if not extract_all:
            if name.casefold() not in used_textures_cf:
                continue
            if not _should_render_texture(name):
                continue

        dst = materials_dir / f"{name}.png"
        if dst.exists():
            continue

        # Reconstruct a WAD3-style MIPTEX lump and reuse the existing decoder.
        # The BSP texture lump uses the same on-disk layout for each embedded texture.
        try:
            size = getattr(mt, "size", None)
            offsets = getattr(mt, "offsets", None)
            if size is None or offsets is None:
                continue
            w = int(float(getattr(size, "x", 0)))
            h = int(float(getattr(size, "y", 0)))
            if w <= 0 or h <= 0:
                continue

            # Offsets are relative to the start of the miptex struct.
            o0 = int(getattr(offsets, "full"))
            o1 = int(getattr(offsets, "half"))
            o2 = int(getattr(offsets, "quarter"))
            o3 = int(getattr(offsets, "eighth"))
            if o0 <= 0 or o1 <= 0 or o2 <= 0 or o3 <= 0:
                # External texture reference (not embedded).
                continue

            # Name field is fixed 16 bytes in the struct.
            raw_name = getattr(mt, "name", b"")
            if isinstance(raw_name, bytes):
                name16 = (raw_name + b"\x00" * 16)[:16]
            else:
                name16 = (str(raw_name).encode("ascii", errors="ignore") + b"\x00" * 16)[:16]

            # The last element in bsp_tool's mips list appears to include mip3 plus palette bytes.
            # Slice the expected mip3 length; keep the remainder as palette payload.
            mip3_len = max(1, (w // 8)) * max(1, (h // 8))
            mip0 = bytes(mips[0] or b"")
            mip1 = bytes(mips[1] or b"")
            mip2 = bytes(mips[2] or b"")
            tail = bytes(mips[3] or b"")
            mip3 = tail[:mip3_len]
            pal = tail[mip3_len:]

            # Build the blob with explicit padding to match offsets.
            header = bytearray()
            header += name16
            header += int(w).to_bytes(4, "little", signed=False)
            header += int(h).to_bytes(4, "little", signed=False)
            header += int(o0).to_bytes(4, "little", signed=False)
            header += int(o1).to_bytes(4, "little", signed=False)
            header += int(o2).to_bytes(4, "little", signed=False)
            header += int(o3).to_bytes(4, "little", signed=False)

            buf = bytearray(header)
            if len(buf) < o0:
                buf += b"\x00" * (o0 - len(buf))
            buf += mip0
            if len(buf) < o1:
                buf += b"\x00" * (o1 - len(buf))
            buf += mip1
            if len(buf) < o2:
                buf += b"\x00" * (o2 - len(buf))
            buf += mip2
            if len(buf) < o3:
                buf += b"\x00" * (o3 - len(buf))
            buf += mip3
            buf += pal

            tex = decode_wad3_miptex(name=name, data=bytes(buf))
            _save_png(dst, width=tex.width, height=tex.height, rgba=tex.rgba)
            extracted += 1
        except (WadError, ValueError, OverflowError):
            continue
        except Exception:
            continue

    return extracted


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
        help=(
            "Output for the imported map bundle.\n"
            "- If --out-format=dir: directory (writes map.json + materials/ + lightmaps/ + resources/)\n"
            "- If --out-format=irunmap: output .irunmap file\n"
            "- If --out-format=auto (default): infer from --out extension (.irunmap => packed; otherwise directory)\n"
            "Not required with --analyze."
        ),
    )
    parser.add_argument(
        "--out-format",
        choices=("auto", "dir", "irunmap"),
        default="auto",
        help="Output format (default: auto).",
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
    out_ref = Path(args.out or ".")

    out_format = str(args.out_format or "auto").strip().lower()
    if out_format == "auto":
        out_format = "irunmap" if out_ref.suffix.lower() == PACKED_BUNDLE_EXT else "dir"
    if out_format not in ("dir", "irunmap"):
        parser.error("--out-format must be one of: auto, dir, irunmap")

    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    out_dir = out_ref
    packed_out: Path | None = None

    try:
        if not args.analyze:
            if out_format == "dir":
                out_dir = out_ref
                out_dir.mkdir(parents=True, exist_ok=True)
            else:
                packed_out = out_ref
                packed_out.parent.mkdir(parents=True, exist_ok=True)
                tmp_dir = tempfile.TemporaryDirectory(
                    prefix=f"irun-import-{bsp_path.stem}-",
                    dir=str(packed_out.parent),
                )
                out_dir = Path(tmp_dir.name)

        map_name = bsp_path.stem
        map_id = args.map_id or map_name
        map_json = out_dir / "map.json"

        bsp = bsp_tool.load_bsp(str(bsp_path))

        entities = getattr(bsp, "ENTITIES", [])
        spawn_pos, spawn_yaw = _pick_spawn(entities, args.scale)
        skyname = _skyname_from_entities(entities)
        lightmap_scale = _parse_lightmap_scale(entities)
        lightstyles: dict[str, str] = {"0": "m"}
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            style_raw = ent.get("style")
            pat = ent.get("pattern")
            if not isinstance(style_raw, str) or not isinstance(pat, str):
                continue
            try:
                style = int(style_raw.strip())
            except Exception:
                continue
            pat = pat.strip()
            if not pat:
                continue
            # Store as string keys for JSON stability.
            lightstyles[str(style)] = pat

        model_entities: dict[int, dict] = {}
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            idx = _model_index_from_entity(ent)
            if idx is None:
                continue
            model_entities.setdefault(idx, ent)

        # Precompute per-face lightmap metadata (used for extraction and UV mapping).
        face_lm_meta: dict[int, dict] = {}
        face_lm_bundle: dict[str, dict] = {}
        lighting = getattr(bsp, "LIGHTING", None)
        if lighting is not None:
            for face_idx in range(len(getattr(bsp, "FACES", []))):
                meta = _face_lightmap_meta(bsp=bsp, face_idx=int(face_idx), lightmap_scale=lightmap_scale)
                if meta is not None:
                    face_lm_meta[int(face_idx)] = meta

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

                lm_meta = face_lm_meta.get(int(face_idx))
                texinfo = None
                if lm_meta is not None:
                    try:
                        texinfo = bsp.TEXTURE_INFO[bsp.FACES[int(face_idx)].texture_info]
                    except Exception:
                        texinfo = None

                for poly in mesh.polygons:
                    if len(poly.vertices) < 3:
                        continue
                    verts = poly.vertices
                    for i in range(1, len(verts) - 1):
                        # Use a consistent winding order for Panda3D (CCW in view space).
                        # Historically we achieved this by mirroring the coordinate system (Y flip),
                        # but that made the whole map mirrored. Keep coordinates unmirrored and instead
                        # flip the triangle winding here.
                        v0 = verts[0]
                        v1 = verts[i + 1]
                        v2 = verts[i]

                        # Keep GoldSrc BSP coordinates in the same space as the runtime (scale only).
                        p0 = [
                            float(v0.position.x) * args.scale,
                            float(v0.position.y) * args.scale,
                            float(v0.position.z) * args.scale,
                        ]
                        p1 = [
                            float(v1.position.x) * args.scale,
                            float(v1.position.y) * args.scale,
                            float(v1.position.z) * args.scale,
                        ]
                        p2 = [
                            float(v2.position.x) * args.scale,
                            float(v2.position.y) * args.scale,
                            float(v2.position.z) * args.scale,
                        ]
                        pos9 = [*p0, *p1, *p2]

                        if collide_model:
                            collision_triangles.append(pos9)

                        if tri_renders:
                            n0 = [float(v0.normal.x), float(v0.normal.y), float(v0.normal.z)]
                            n1 = [float(v1.normal.x), float(v1.normal.y), float(v1.normal.z)]
                            n2 = [float(v2.normal.x), float(v2.normal.y), float(v2.normal.z)]

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

                            # GoldSrc baked lighting lives in LIGHTING lump (RGB) and is mapped via texture vectors.
                            if lm_meta is not None and texinfo is not None:
                                w = float(lm_meta["w"])
                                h = float(lm_meta["h"])
                                mins_s = float(lm_meta["mins_s"])
                                mins_t = float(lm_meta["mins_t"])
                                scale = float(lm_meta["scale"])

                                def lm_uv(pos) -> list[float]:
                                    s, t = _tex_s_t(texinfo=texinfo, pos=pos)
                                    u = (s / scale - mins_s + 0.5) / w
                                    v = (t / scale - mins_t + 0.5) / h
                                    # Panda's texture V origin differs from GoldSrc lightmap row order; flip V.
                                    return [float(u), float(1.0 - v)]

                                lm0 = lm_uv(v0.position)
                                lm1 = lm_uv(v1.position)
                                lm2 = lm_uv(v2.position)
                                lmi = int(face_idx)
                            else:
                                lm0 = [0.0, 0.0]
                                lm1 = [0.0, 0.0]
                                lm2 = [0.0, 0.0]
                                lmi = None

                            tri = {
                                "m": mat_name,
                                "lmi": lmi,
                                "p": pos9,
                                "n": [
                                    *n0,
                                    *n1,
                                    *n2,
                                ],
                                "uv": [*uv0, *uv1, *uv2],
                                "lm": [*lm0, *lm1, *lm2],
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
        # Some maps omit the editor WAD list; fall back to scanning common WAD locations.
        if not wad_names:
            wad_names = [p.name for p in _discover_wad_files(game_root)]
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
                "lightstyles": lightstyles,
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

        # Extract textures embedded in the BSP and/or from referenced WADs into bundle materials/.
        materials_dir = out_dir / "materials"
        extracted_textures: int = 0
        used_cf = {u.casefold() for u in used_textures}

        # Skybox textures live outside WADs (gfx/env), so pull them explicitly.
        extracted_textures += _try_extract_skybox_textures(
            game_root=game_root,
            materials_dir=materials_dir,
            skyname=skyname,
        )

        extracted_textures += _extract_embedded_textures(
            bsp=bsp,
            materials_dir=materials_dir,
            used_textures_cf=used_cf,
            extract_all=bool(args.extract_all_wad_textures),
        )
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

        # Extract baked GoldSrc lightmaps (RGB) into bundle lightmaps/ and reference them from map.json.
        if lighting is not None and face_lm_meta:
            lightmaps_dir = out_dir / "lightmaps"
            lightmaps_dir.mkdir(parents=True, exist_ok=True)

            for face_idx, meta in sorted(face_lm_meta.items(), key=lambda it: int(it[0])):
                off = int(meta["offset"])
                w = int(meta["w"])
                h = int(meta["h"])
                styles = [int(x) for x in meta["styles"]]
                block_bytes = w * h * 3

                # GoldSrc stores one block per non-255 style, in slot order.
                paths: list[str | None] = [None, None, None, None]
                style_slots: list[int | None] = [None, None, None, None]
                block_idx = 0
                for slot in range(4):
                    style = int(styles[slot]) if slot < len(styles) else 255
                    if style == 255:
                        continue
                    start = off + block_idx * block_bytes
                    end = start + block_bytes
                    raw = bytes(lighting[start:end])
                    if len(raw) != block_bytes:
                        break
                    rgba = _decode_goldsrc_lightmap_rgb_to_rgba(raw)
                    img = Image.frombytes("RGBA", (w, h), rgba)
                    dst = lightmaps_dir / f"f{face_idx}_lm{slot}.png"
                    try:
                        img.save(dst)
                    except Exception:
                        break
                    paths[slot] = str(Path("lightmaps") / dst.name).replace("\\", "/")
                    style_slots[slot] = style
                    block_idx += 1

                if any(p is not None for p in paths):
                    face_lm_bundle[str(int(face_idx))] = {
                        "styles": style_slots,
                        "paths": paths,
                        "w": int(w),
                        "h": int(h),
                    }

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
            "lightmaps": {
                "scale": float(lightmap_scale),
                "encoding": "goldsrc_rgb",
                "faces": face_lm_bundle,
            },
            "lightstyles": lightstyles,
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
        if packed_out is not None:
            pack_bundle_dir_to_irunmap(bundle_dir=out_dir, out_path=packed_out, compresslevel=1)
            print(
                f"Wrote {packed_out} (render_tris={len(render_triangles)}, collision_tris={len(collision_triangles)}, "
                f"textures={extracted_textures}, copied={len(copied)}, missing={len(missing)})"
            )
        else:
            print(
                f"Wrote {map_json} (render_tris={len(render_triangles)}, collision_tris={len(collision_triangles)}, "
                f"textures={extracted_textures}, copied={len(copied)}, missing={len(missing)})"
            )
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


if __name__ == "__main__":
    main()
