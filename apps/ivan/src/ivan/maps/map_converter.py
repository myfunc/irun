"""Convert a parsed .map file to the internal format expected by scene.py.

This module orchestrates the full pipeline:

1. Parse the ``.map`` text.
2. Discover and extract textures from referenced WAD files.
3. Convert brush geometry to triangles (render + collision).
4. Classify entities (worldspawn, func_wall, func_illusionary, triggers, …).
5. Locate spawn point.
6. Resolve material definitions.
7. Produce a :class:`MapConvertResult` that can be fed directly into the
   renderer or serialised to the ``map.json`` bundle format.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from ivan.maps.brush_geometry import (
    SKIP_RENDER_TEXTURES,
    ConvertedBrushResult,
    Triangle,
    convert_entity_brushes,
)
from ivan.maps.map_parser import MapEntity, parse_map
from ivan.maps.material_defs import MaterialDef, MaterialResolver
from ivan.paths import app_root as ivan_app_root

logger = logging.getLogger(__name__)
_TEXTURE_CACHE_MANIFEST = ".wad_texture_cache_manifest.json"
_TEXTURE_CACHE_SCHEMA = "ivan.map_texture_cache.v1"


# ---------------------------------------------------------------------------
# WAD import helper
# ---------------------------------------------------------------------------

def _import_goldsrc_wad():
    """Lazily import the ``goldsrc_wad`` tools module.

    The module lives outside the installable package tree
    (``apps/ivan/tools/importers/goldsrc/``) so we need a ``sys.path``
    shim the first time it is used.
    """

    try:
        import goldsrc_wad  # noqa: F811
        return goldsrc_wad
    except ImportError:
        pass

    tools_dir = ivan_app_root() / "tools" / "importers" / "goldsrc"
    tools_str = str(tools_dir)
    if tools_str not in sys.path:
        sys.path.insert(0, tools_str)
    import goldsrc_wad  # noqa: F811
    return goldsrc_wad


# ---------------------------------------------------------------------------
# Entity classification
# ---------------------------------------------------------------------------

# Solid brush entities that produce *both* render and collision geometry.
_RENDER_AND_COLLIDE: frozenset[str] = frozenset({
    "worldspawn",
    "func_wall",
    "func_detail",
    "func_group",
    "func_breakable",
    "func_pushable",
    "func_door",
    "func_door_rotating",
    "func_plat",
    "func_train",
    "func_rotating",
    "func_conveyor",
    "func_water",
})

# Solid brush entities that produce render geometry but *no* collision.
_RENDER_ONLY: frozenset[str] = frozenset({
    "func_illusionary",
})

# Entities whose brushes are completely invisible and produce no geometry.
_SKIP_ENTIRELY_PREFIXES: tuple[str, ...] = (
    "trigger_",
)


def _entity_category(classname: str) -> str:
    """Return ``"render_collide"``, ``"render_only"``, or ``"skip"``."""

    cn = classname.lower()

    # Trigger entities — skip everything.
    for prefix in _SKIP_ENTIRELY_PREFIXES:
        if cn.startswith(prefix):
            return "skip"

    if cn in _RENDER_AND_COLLIDE:
        return "render_collide"
    if cn in _RENDER_ONLY:
        return "render_only"

    # Conservative default for unknown brush entities: render, no collision.
    return "render_only"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class LightEntity:
    """Parsed Half-Life light entity from a ``.map`` file.

    Used to create Panda3D lights when previewing ``.map`` files directly
    (TrenchBroom workflow, no baked lightmaps).
    """

    classname: str  # 'light', 'light_environment', 'light_spot'
    origin: tuple[float, float, float]  # scaled world-space position
    color: tuple[float, float, float]   # normalised RGB (0-1)
    brightness: float  # HL intensity value (typically 0-300)

    # light_environment / light_spot direction.
    pitch: float = 0.0
    angles: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (pitch, yaw, roll)

    # light_spot cone.
    inner_cone: float = 0.0
    outer_cone: float = 0.0

    # Attenuation.
    fade: float = 1.0
    falloff: int = 0  # 0=default, 1=linear, 2=inverse-square
    style: int = 0


@dataclass
class MapConvertResult:
    """Result of converting a ``.map`` file to the internal format."""

    # Format-v2 triangle dicts (what scene.py expects from map.json).
    triangles: list[dict] = field(default_factory=list)
    # Position-only 9-float lists (collision mesh).
    collision_triangles: list[list[float]] = field(default_factory=list)

    spawn_position: tuple[float, float, float] | None = None
    spawn_yaw: float = 0.0
    map_id: str = "untitled"
    bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # texture_name -> albedo PNG path
    materials: dict[str, Path] = field(default_factory=dict)
    # texture_name -> full MaterialDef
    material_defs: dict[str, MaterialDef] = field(default_factory=dict)
    # texture_name -> (width, height) for UV computation
    texture_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)

    skyname: str | None = None

    # Parsed Half-Life light entities (for preview lighting in .map mode).
    lights: list[LightEntity] = field(default_factory=list)

    # Optional fog from worldspawn or env_fog (for runtime preview).
    fog: dict | None = None  # {"enabled": bool, "start": float, "end": float, "color": [r,g,b]}
    # Fine-grained converter stage timings (milliseconds).
    perf_stages_ms: dict[str, float] = field(default_factory=dict)
    # Basic converter counters (entities, brushes, texture/material cardinality, ...).
    perf_counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# WAD path resolution
# ---------------------------------------------------------------------------

def _parse_wad_paths(wad_value: str) -> list[str]:
    """Split the worldspawn ``wad`` key into individual path strings.

    The value is semicolon-separated and may use Windows back-slashes.
    Empty segments are ignored.
    """

    raw_paths: list[str] = []
    for segment in wad_value.replace("\\", "/").split(";"):
        segment = segment.strip()
        if segment:
            raw_paths.append(segment)
    return raw_paths


def _resolve_wad_files(
    raw_paths: list[str],
    *,
    map_dir: Path,
    wad_search_dirs: list[Path],
) -> list[Path]:
    """Resolve WAD path strings to actual files on disk.

    Resolution order for each path:
    1. Relative to the ``.map`` file's parent directory.
    2. Relative to each *wad_search_dir*.
    3. Basename-only search in each *wad_search_dir*.
    """

    found: list[Path] = []

    for raw in raw_paths:
        p = Path(raw)
        resolved: Path | None = None

        # 1) Relative to map directory.
        candidate = (map_dir / p).resolve()
        if candidate.is_file():
            resolved = candidate
        else:
            # 2) Relative to each search dir.
            for sd in wad_search_dirs:
                candidate = (sd / p).resolve()
                if candidate.is_file():
                    resolved = candidate
                    break

        # 3) Basename fallback.
        if resolved is None:
            basename = p.name
            for sd in wad_search_dirs:
                candidate = (sd / basename).resolve()
                if candidate.is_file():
                    resolved = candidate
                    break

        if resolved is not None:
            if resolved not in found:
                found.append(resolved)
        else:
            logger.warning("WAD not found: %s", raw)

    return found


# ---------------------------------------------------------------------------
# Texture extraction
# ---------------------------------------------------------------------------

def _extract_wad_textures(
    wad_paths: list[Path],
    *,
    cache_dir: Path,
) -> tuple[dict[str, Path], dict[str, tuple[int, int]], str]:
    """Extract all textures from a list of WAD files.

    Returns
    -------
    materials : dict[str, Path]
        Mapping of texture name (original case) to the written PNG path.
    texture_sizes : dict[str, tuple[int, int]]
        Mapping of texture name to ``(width, height)``.
    cache_status : str
        `hit` when cached PNG set is reused, otherwise `miss`.
    """

    materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}

    cache_dir.mkdir(parents=True, exist_ok=True)
    wad_fingerprints = _build_wad_fingerprints(wad_paths)
    manifest = _load_texture_cache_manifest(cache_dir)
    if _manifest_matches_wads(manifest=manifest, wad_fingerprints=wad_fingerprints):
        cached = _restore_cached_textures(cache_dir=cache_dir, manifest=manifest)
        if cached is not None:
            logger.info("WAD texture cache hit: %s (%d textures)", cache_dir, len(cached[0]))
            return cached[0], cached[1], "hit"

    # Cache miss or invalidated signature: remove stale PNGs/manifest before rebuild.
    _clear_texture_cache_dir(cache_dir)
    goldsrc_wad = _import_goldsrc_wad()

    for wad_path in wad_paths:
        logger.info("Loading WAD: %s", wad_path)
        try:
            wad = goldsrc_wad.Wad3.load(wad_path)
        except Exception as exc:
            logger.warning("Failed to load WAD %s: %s", wad_path, exc)
            continue

        for tex in wad.iter_textures():
            # GoldSrc texture names are case-insensitive.  Normalise to
            # lowercase so lookups from .map files (which may use any casing)
            # always match.
            key = tex.name.lower()

            # Skip if we already have this texture from a previous WAD
            # (first WAD wins, matching GoldSrc engine behaviour).
            if key in materials:
                continue

            texture_sizes[key] = (tex.width, tex.height)

            out_path = cache_dir / f"{key}.png"
            try:
                img = Image.frombytes("RGBA", (tex.width, tex.height), tex.rgba)
                img.save(out_path)
                materials[key] = out_path
            except Exception as exc:
                logger.warning(
                    "Failed to save texture %s from %s: %s",
                    tex.name, wad_path.name, exc,
                )

    # ── Fallback: recover sizes from cached PNGs ──────────────────────
    # If WAD loading failed or was incomplete, we may still have PNGs in
    # the cache from a previous run.  Read their dimensions so UVs are
    # computed correctly even without live WAD access.
    try:
        for png in cache_dir.glob("*.png"):
            key = png.stem.lower()
            if key not in materials:
                materials[key] = png
            if key not in texture_sizes:
                try:
                    with Image.open(png) as img:
                        texture_sizes[key] = (img.width, img.height)
                except Exception:
                    pass
    except Exception:
        pass

    _save_texture_cache_manifest(
        cache_dir=cache_dir,
        wad_fingerprints=wad_fingerprints,
        texture_sizes=texture_sizes,
    )
    return materials, texture_sizes, "miss"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _build_wad_fingerprints(wad_paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for wad in wad_paths:
        try:
            st = wad.stat()
            out.append(
                {
                    "path": str(wad.resolve()),
                    "size_bytes": int(st.st_size),
                    "mtime_ns": int(st.st_mtime_ns),
                    "sha256": str(_sha256_file(wad)),
                }
            )
        except Exception:
            out.append(
                {
                    "path": str(wad),
                    "size_bytes": 0,
                    "mtime_ns": 0,
                    "sha256": "",
                }
            )
    return out


def _manifest_path(cache_dir: Path) -> Path:
    return cache_dir / _TEXTURE_CACHE_MANIFEST


def _load_texture_cache_manifest(cache_dir: Path) -> dict[str, Any] | None:
    p = _manifest_path(cache_dir)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    if str(raw.get("schema")) != _TEXTURE_CACHE_SCHEMA:
        return None
    return raw


def _save_texture_cache_manifest(
    *,
    cache_dir: Path,
    wad_fingerprints: list[dict[str, Any]],
    texture_sizes: dict[str, tuple[int, int]],
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": _TEXTURE_CACHE_SCHEMA,
        "wads": list(wad_fingerprints),
        "texture_sizes": {str(k): [int(v[0]), int(v[1])] for k, v in texture_sizes.items()},
    }
    try:
        _manifest_path(cache_dir).write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        # Cache metadata is best-effort, runtime must continue.
        pass


def _manifest_matches_wads(*, manifest: dict[str, Any] | None, wad_fingerprints: list[dict[str, Any]]) -> bool:
    if not isinstance(manifest, dict):
        return False
    w = manifest.get("wads")
    if not isinstance(w, list):
        return False
    if len(w) != len(wad_fingerprints):
        return False
    for i, fp in enumerate(wad_fingerprints):
        row = w[i]
        if not isinstance(row, dict):
            return False
        if str(row.get("path")) != str(fp.get("path")):
            return False
        if str(row.get("sha256")) != str(fp.get("sha256")):
            return False
    return True


def _restore_cached_textures(
    *,
    cache_dir: Path,
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, Path], dict[str, tuple[int, int]]] | None:
    if not isinstance(manifest, dict):
        return None
    sizes_raw = manifest.get("texture_sizes")
    if not isinstance(sizes_raw, dict) or not sizes_raw:
        return None
    materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}
    for key_raw, sz_raw in sizes_raw.items():
        key = str(key_raw).strip().lower()
        if not key:
            return None
        if not isinstance(sz_raw, list) or len(sz_raw) != 2:
            return None
        try:
            w = int(sz_raw[0])
            h = int(sz_raw[1])
        except Exception:
            return None
        if w <= 0 or h <= 0:
            return None
        png = cache_dir / f"{key}.png"
        if not png.exists():
            return None
        materials[key] = png
        texture_sizes[key] = (w, h)
    return materials, texture_sizes


def _clear_texture_cache_dir(cache_dir: Path) -> None:
    try:
        for png in cache_dir.glob("*.png"):
            try:
                png.unlink()
            except Exception:
                pass
        m = _manifest_path(cache_dir)
        try:
            if m.exists():
                m.unlink()
        except Exception:
            pass
    except Exception:
        pass


def _load_loose_textures(
    *,
    texture_dirs: list[Path],
    referenced_names: set[str],
) -> tuple[dict[str, Path], dict[str, tuple[int, int]]]:
    """Load loose image textures from directories as fallback albedo sources."""
    if not referenced_names:
        return {}, {}
    allowed_ext = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
    ref_cf = {name.casefold() for name in referenced_names}
    materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}
    for base in texture_dirs:
        if not base.exists() or not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in allowed_ext:
                continue
            key = p.stem.casefold()
            if key not in ref_cf or key in materials:
                continue
            materials[key] = p
            try:
                with Image.open(p) as img:
                    texture_sizes[key] = (int(img.width), int(img.height))
            except Exception:
                # Keep albedo path even when metadata read fails.
                pass
    return materials, texture_sizes


# ---------------------------------------------------------------------------
# Triangle dict helpers
# ---------------------------------------------------------------------------

def _triangle_to_dict(tri: Triangle) -> dict:
    """Convert a :class:`Triangle` to the format-v2 dict scene.py expects."""

    return {
        "m": tri.material,
        "p": list(tri.positions),
        "n": list(tri.normals),
        "uv": list(tri.uvs),
        # Vertex colour: RGBA per vertex (3 verts × 4 channels = 12 floats).
        # White / full opacity — no baked vertex lighting for direct .map loads.
        "c": [1.0] * 12,
        # Lightmap UVs: all zero (no lightmaps for direct .map loading).
        "lm": [0.0] * 6,
    }


# ---------------------------------------------------------------------------
# Bounds computation
# ---------------------------------------------------------------------------

def _compute_bounds(
    triangles: list[dict],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Compute axis-aligned bounding box from format-v2 triangle dicts."""

    if not triangles:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    for td in triangles:
        p = td.get("p")
        if not isinstance(p, list) or len(p) != 9:
            continue
        for vi in range(3):
            x, y, z = p[vi * 3], p[vi * 3 + 1], p[vi * 3 + 2]
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            if z < min_z:
                min_z = z
            if z > max_z:
                max_z = z

    if min_x == float("inf"):
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    return (min_x, min_y, min_z), (max_x, max_y, max_z)


# ---------------------------------------------------------------------------
# Spawn point extraction
# ---------------------------------------------------------------------------

_SPAWN_CLASSNAMES: tuple[str, ...] = (
    "info_player_start",
    "info_player_deathmatch",
)


def _find_spawn(
    entities: list[MapEntity],
    *,
    scale: float,
) -> tuple[tuple[float, float, float] | None, float]:
    """Locate the first spawn-point entity and return (position, yaw).

    The position is scaled by *scale* to match the converted geometry.
    """

    for ent in entities:
        cn = ent.properties.get("classname", "").lower()
        if cn not in _SPAWN_CLASSNAMES:
            continue

        origin_str = ent.properties.get("origin", "")
        parts = origin_str.split()
        if len(parts) != 3:
            continue

        try:
            x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue

        yaw = 0.0
        angle_str = ent.properties.get("angle", "")
        if angle_str.strip():
            try:
                yaw = float(angle_str)
            except ValueError:
                pass

        return (x * scale, y * scale, z * scale), yaw

    return None, 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_map_file(
    map_path: Path,
    *,
    scale: float = 0.03,
    wad_search_dirs: list[Path] | None = None,
    materials_dirs: list[Path] | None = None,
    texture_cache_dir: Path | None = None,
) -> MapConvertResult:
    """Convert a ``.map`` file to the internal IVAN format.

    Parameters
    ----------
    map_path:
        Path to the ``.map`` file.
    scale:
        World scale (default ``0.03``, matching GoldSrc convention).
    wad_search_dirs:
        Directories to search for WAD files referenced in worldspawn.
    materials_dirs:
        Directories to search for ``.material.json`` files.
    texture_cache_dir:
        Directory to write extracted WAD textures as PNGs.
        Uses a temporary directory when *None*.
    """

    perf_stages_ms: dict[str, float] = {}
    perf_total_t0 = time.perf_counter()

    def _mark_stage(stage: str, t0: float) -> None:
        perf_stages_ms[str(stage)] = max(0.0, (time.perf_counter() - float(t0)) * 1000.0)

    map_path = Path(map_path).resolve()
    map_dir = map_path.parent
    wad_dirs = [Path(d).resolve() for d in (wad_search_dirs or [])]
    mat_dirs = [Path(d).resolve() for d in (materials_dirs or [])]

    # ── 1. Read and parse ──────────────────────────────────────────────
    logger.info("Parsing map: %s", map_path)
    t0 = time.perf_counter()
    map_text = map_path.read_text(encoding="utf-8", errors="replace")
    entities = parse_map(map_text)
    _mark_stage("read_parse_map", t0)

    if not entities:
        logger.warning("No entities found in %s", map_path)
        _mark_stage("total_convert", perf_total_t0)
        return MapConvertResult(perf_stages_ms=perf_stages_ms)

    # ── 2. Find worldspawn ─────────────────────────────────────────────
    worldspawn: MapEntity | None = None
    for ent in entities:
        if ent.properties.get("classname", "").lower() == "worldspawn":
            worldspawn = ent
            break

    if worldspawn is None:
        logger.warning("No worldspawn entity in %s", map_path)
        _mark_stage("total_convert", perf_total_t0)
        return MapConvertResult(perf_stages_ms=perf_stages_ms)

    # ── 3. Extract metadata ────────────────────────────────────────────
    ws_props = worldspawn.properties
    skyname = ws_props.get("skyname") or ws_props.get("sky") or None
    map_title = ws_props.get("message", "").strip()
    map_id = map_title if map_title else map_path.stem

    ws_phong = ws_props.get("_phong", "0").strip() == "1"
    try:
        ws_phong_angle = float(ws_props.get("_phong_angle", "89"))
    except ValueError:
        ws_phong_angle = 89.0

    # ── 4. Resolve WAD files ───────────────────────────────────────────
    wad_raw = ws_props.get("wad", "")
    raw_wad_paths = _parse_wad_paths(wad_raw)

    wad_files: list[Path] = []
    t0 = time.perf_counter()
    if raw_wad_paths:
        wad_files = _resolve_wad_files(
            raw_wad_paths,
            map_dir=map_dir,
            wad_search_dirs=wad_dirs,
        )
        logger.info("Resolved %d of %d WAD files", len(wad_files), len(raw_wad_paths))
    _mark_stage("resolve_wad_files", t0)

    # ── 5. Extract textures from WADs ──────────────────────────────────
    _temp_dir = None
    if texture_cache_dir is None:
        _temp_dir = tempfile.TemporaryDirectory(prefix="ivan_tex_")
        cache_dir = Path(_temp_dir.name)
    else:
        cache_dir = Path(texture_cache_dir).resolve()

    tex_materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}
    texture_cache_status = "none"

    t0 = time.perf_counter()
    if wad_files:
        tex_materials, texture_sizes, texture_cache_status = _extract_wad_textures(
            wad_files,
            cache_dir=cache_dir,
        )
        logger.info(
            "Extracted %d textures (%d with size info)",
            len(tex_materials),
            len(texture_sizes),
        )
    else:
        logger.warning(
            "No WAD files resolved from worldspawn 'wad' = %r  |  raw paths: %s  |  search dirs: %s",
            wad_raw, raw_wad_paths, wad_dirs,
        )
    _mark_stage("extract_textures", t0)

    # ── 6. Discover referenced texture names ───────────────────────────
    t0 = time.perf_counter()
    all_tex_names: set[str] = set()
    for ent in entities:
        for brush in ent.brushes:
            for face in brush.faces:
                if face.texture:
                    all_tex_names.add(face.texture.casefold())
    _mark_stage("scan_texture_references", t0)

    # ── 6a. Fallback to loose textures (editor texture folders) ───────
    t0 = time.perf_counter()
    loose_dirs = [
        map_dir / "textures",
        ivan_app_root() / "assets" / "textures_tb",
    ]
    loose_materials, loose_sizes = _load_loose_textures(
        texture_dirs=loose_dirs,
        referenced_names=all_tex_names,
    )
    added = 0
    for key, tex_path in loose_materials.items():
        if key not in tex_materials:
            tex_materials[key] = tex_path
            added += 1
    for key, size in loose_sizes.items():
        if key not in texture_sizes:
            texture_sizes[key] = size
    if added:
        logger.info("Resolved %d referenced textures from loose image folders", added)
    _mark_stage("resolve_loose_textures", t0)

    # ── 6b. Check for missing texture sizes ────────────────────────────
    #    If a face references a texture not in texture_sizes, UVs default
    #    to (1,1) producing pixel-space coordinates (wrong tiling).
    t0 = time.perf_counter()
    missing = all_tex_names - set(texture_sizes.keys())
    if missing:
        logger.warning(
            "%d textures missing size info (showing first 10): %s  |  texture_sizes has %d entries",
            len(missing), sorted(missing)[:10], len(texture_sizes),
        )
    else:
        logger.info("All %d texture sizes resolved OK", len(all_tex_names))
    _mark_stage("scan_texture_size_gaps", t0)

    # ── 6b. Convert worldspawn brushes ─────────────────────────────────
    all_tri_dicts: list[dict] = []
    all_collision: list[list[float]] = []

    t0 = time.perf_counter()
    if worldspawn.brushes:
        ws_result: ConvertedBrushResult = convert_entity_brushes(
            worldspawn.brushes,
            scale=scale,
            texture_sizes=texture_sizes,
            phong=ws_phong,
            phong_angle=ws_phong_angle,
        )
        for tri in ws_result.triangles:
            all_tri_dicts.append(_triangle_to_dict(tri))
        all_collision.extend(ws_result.collision_triangles)
        logger.info(
            "Worldspawn: %d render tris, %d collision tris",
            len(ws_result.triangles),
            len(ws_result.collision_triangles),
        )
    _mark_stage("convert_worldspawn_brushes", t0)

    # ── 7. Process brush entities ──────────────────────────────────────
    t0 = time.perf_counter()
    for ent in entities:
        classname = ent.properties.get("classname", "").lower()

        # worldspawn already handled above.
        if classname == "worldspawn":
            continue

        # Point entities (no brushes) are processed separately (spawn, etc.).
        if not ent.brushes:
            continue

        category = _entity_category(classname)

        if category == "skip":
            logger.debug("Skipping trigger entity: %s", classname)
            continue

        # Per-entity phong settings.
        ent_phong = ent.properties.get("_phong", "0").strip() == "1"
        try:
            ent_phong_angle = float(ent.properties.get("_phong_angle", "89"))
        except ValueError:
            ent_phong_angle = 89.0

        result: ConvertedBrushResult = convert_entity_brushes(
            ent.brushes,
            scale=scale,
            texture_sizes=texture_sizes,
            phong=ent_phong,
            phong_angle=ent_phong_angle,
        )

        for tri in result.triangles:
            all_tri_dicts.append(_triangle_to_dict(tri))

        if category == "render_collide":
            all_collision.extend(result.collision_triangles)

        logger.debug(
            "Entity %s (%s): %d render, %d collision",
            classname,
            category,
            len(result.triangles),
            len(result.collision_triangles) if category == "render_collide" else 0,
        )
    _mark_stage("convert_entity_brushes", t0)

    # ── 8. Find spawn point ────────────────────────────────────────────
    t0 = time.perf_counter()
    spawn_pos, spawn_yaw = _find_spawn(entities, scale=scale)
    if spawn_pos is not None:
        logger.info("Spawn point: %s  yaw=%.1f", spawn_pos, spawn_yaw)
    else:
        logger.warning("No spawn point entity found; defaulting to origin")
    _mark_stage("extract_spawn", t0)

    # ── 8b. Parse Half-Life light entities ─────────────────────────────
    _LIGHT_CLASSNAMES = {"light", "light_environment", "light_spot"}
    lights: list[LightEntity] = []

    t0 = time.perf_counter()
    for ent in entities:
        cn = ent.properties.get("classname", "").lower()
        if cn not in _LIGHT_CLASSNAMES:
            continue

        # Origin.
        origin_raw = ent.properties.get("origin", "0 0 0")
        parts = origin_raw.split()
        if len(parts) != 3:
            continue
        try:
            ox = float(parts[0]) * scale
            oy = float(parts[1]) * scale
            oz = float(parts[2]) * scale
        except ValueError:
            continue

        # GoldSrc supports either:
        # - _light: "R G B I"
        # - _color + light (brightness)
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
            try:
                intensity = float(ent.properties.get("light", "200"))
            except ValueError:
                pass

        # Direction (light_environment / light_spot).
        pitch = 0.0
        angles = (0.0, 0.0, 0.0)
        try:
            pitch = float(ent.properties.get("pitch", "0"))
        except ValueError:
            pass
        try:
            a_raw = ent.properties.get("angles", "0 0 0").split()
            if len(a_raw) >= 3:
                angles = (float(a_raw[0]), float(a_raw[1]), float(a_raw[2]))
        except ValueError:
            pass
        if cn == "light_environment" and angles == (0.0, 0.0, 0.0):
            # GoldSrc commonly stores environment yaw in `angle`, not `angles`.
            try:
                yaw = float(ent.properties.get("angle", "0"))
                angles = (0.0, yaw, 0.0)
            except ValueError:
                pass

        inner_cone = 0.0
        outer_cone = 0.0
        if cn == "light_spot":
            try:
                inner_cone = float(ent.properties.get("_cone", "0"))
            except ValueError:
                pass
            try:
                outer_cone = float(ent.properties.get("_cone2", "0"))
            except ValueError:
                pass

        # Attenuation.
        fade = 1.0
        falloff = 0
        style = 0
        try:
            fade = float(ent.properties.get("_fade", "1.0"))
        except ValueError:
            pass
        try:
            falloff = int(ent.properties.get("_falloff", "0"))
        except ValueError:
            pass
        try:
            style = int(ent.properties.get("style", "0"))
        except ValueError:
            pass

        lights.append(LightEntity(
            classname=cn,
            origin=(ox, oy, oz),
            color=(r / 255.0, g / 255.0, b / 255.0),
            brightness=intensity,
            pitch=pitch,
            angles=angles,
            inner_cone=inner_cone,
            outer_cone=outer_cone,
            fade=fade,
            falloff=falloff,
            style=style,
        ))

    if lights:
        logger.info("Parsed %d light entities", len(lights))
    _mark_stage("extract_lights", t0)

    # ── 8c. Parse fog (worldspawn or env_fog) ──────────────────────────
    t0 = time.perf_counter()
    fog: dict | None = None
    for ent in entities:
        cn = ent.properties.get("classname", "").lower()
        if cn == "env_fog":
            start_s = ent.properties.get("fogstart") or ent.properties.get("fog_start")
            end_s = ent.properties.get("fogend") or ent.properties.get("fog_end")
            color_s = ent.properties.get("fogcolor") or ent.properties.get("fog_color") or "128 128 128"
            try:
                start = float(start_s) if start_s else 80.0
                end = float(end_s) if end_s else 200.0
            except (TypeError, ValueError):
                continue
            parts = color_s.split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]) / 255.0, float(parts[1]) / 255.0, float(parts[2]) / 255.0
                    fog = {"enabled": True, "start": start, "end": end, "color": [r, g, b]}
                    break
                except (TypeError, ValueError):
                    pass
    _mark_stage("extract_fog", t0)
    if fog is None:
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
            parts = color_s.split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]) / 255.0, float(parts[1]) / 255.0, float(parts[2]) / 255.0
                    fog = {"enabled": True, "start": start, "end": end, "color": [r, g, b]}
                    break
                except (TypeError, ValueError):
                    pass

    # ── 9. Compute bounds ──────────────────────────────────────────────
    t0 = time.perf_counter()
    bounds_min, bounds_max = _compute_bounds(all_tri_dicts)
    _mark_stage("compute_bounds", t0)

    # ── 10. Resolve material definitions ───────────────────────────────
    t0 = time.perf_counter()
    resolver = MaterialResolver(mat_dirs) if mat_dirs else None

    # Collect all unique material names from the converted triangles.
    unique_materials: set[str] = set()
    for td in all_tri_dicts:
        m = td.get("m")
        if isinstance(m, str):
            unique_materials.add(m)

    resolved_material_defs: dict[str, MaterialDef] = {}
    for mat_name in sorted(unique_materials):
        # tex_materials keys are lowercased (GoldSrc is case-insensitive).
        albedo = tex_materials.get(mat_name.lower())
        if resolver is not None:
            resolved_material_defs[mat_name] = resolver.resolve(
                mat_name, albedo_path=albedo,
            )
        else:
            resolved_material_defs[mat_name] = MaterialDef(
                name=mat_name, albedo_path=albedo,
            )
    _mark_stage("resolve_material_defs", t0)

    # ── 11. Build output ───────────────────────────────────────────────
    logger.info(
        "Conversion complete: %d render tris, %d collision tris, %d materials",
        len(all_tri_dicts),
        len(all_collision),
        len(unique_materials),
    )

    perf_counts = {
        "entities_total": int(len(entities)),
        "brushes_total": int(sum(len(ent.brushes) for ent in entities)),
        "wad_paths_declared": int(len(raw_wad_paths)),
        "wad_files_resolved": int(len(wad_files)),
        "textures_with_albedo": int(len(tex_materials)),
        "textures_with_size": int(len(texture_sizes)),
        "texture_cache_hit": int(1 if texture_cache_status == "hit" else 0),
        "unique_textures_referenced": int(len(all_tex_names)),
        "render_triangles": int(len(all_tri_dicts)),
        "collision_triangles": int(len(all_collision)),
        "lights_total": int(len(lights)),
        "materials_total": int(len(unique_materials)),
    }
    _mark_stage("total_convert", perf_total_t0)

    return MapConvertResult(
        triangles=all_tri_dicts,
        collision_triangles=all_collision,
        fog=fog,
        spawn_position=spawn_pos,
        spawn_yaw=spawn_yaw,
        map_id=map_id,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        materials=tex_materials,
        material_defs=resolved_material_defs,
        texture_sizes=texture_sizes,
        skyname=skyname,
        lights=lights,
        perf_stages_ms=perf_stages_ms,
        perf_counts=perf_counts,
    )
