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

import logging
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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
) -> tuple[dict[str, Path], dict[str, tuple[int, int]]]:
    """Extract all textures from a list of WAD files.

    Returns
    -------
    materials : dict[str, Path]
        Mapping of texture name (original case) to the written PNG path.
    texture_sizes : dict[str, tuple[int, int]]
        Mapping of texture name to ``(width, height)``.
    """

    goldsrc_wad = _import_goldsrc_wad()

    materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}

    cache_dir.mkdir(parents=True, exist_ok=True)

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

    map_path = Path(map_path).resolve()
    map_dir = map_path.parent
    wad_dirs = [Path(d).resolve() for d in (wad_search_dirs or [])]
    mat_dirs = [Path(d).resolve() for d in (materials_dirs or [])]

    # ── 1. Read and parse ──────────────────────────────────────────────
    logger.info("Parsing map: %s", map_path)
    map_text = map_path.read_text(encoding="utf-8", errors="replace")
    entities = parse_map(map_text)

    if not entities:
        logger.warning("No entities found in %s", map_path)
        return MapConvertResult()

    # ── 2. Find worldspawn ─────────────────────────────────────────────
    worldspawn: MapEntity | None = None
    for ent in entities:
        if ent.properties.get("classname", "").lower() == "worldspawn":
            worldspawn = ent
            break

    if worldspawn is None:
        logger.warning("No worldspawn entity in %s", map_path)
        return MapConvertResult()

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
    if raw_wad_paths:
        wad_files = _resolve_wad_files(
            raw_wad_paths,
            map_dir=map_dir,
            wad_search_dirs=wad_dirs,
        )
        logger.info("Resolved %d of %d WAD files", len(wad_files), len(raw_wad_paths))

    # ── 5. Extract textures from WADs ──────────────────────────────────
    _temp_dir = None
    if texture_cache_dir is None:
        _temp_dir = tempfile.TemporaryDirectory(prefix="ivan_tex_")
        cache_dir = Path(_temp_dir.name)
    else:
        cache_dir = Path(texture_cache_dir).resolve()

    tex_materials: dict[str, Path] = {}
    texture_sizes: dict[str, tuple[int, int]] = {}

    if wad_files:
        tex_materials, texture_sizes = _extract_wad_textures(
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

    # ── 6. Check for missing texture sizes ─────────────────────────────
    #    If a face references a texture not in texture_sizes, UVs default
    #    to (1,1) producing pixel-space coordinates (wrong tiling).
    all_tex_names: set[str] = set()
    for ent in entities:
        for brush in ent.brushes:
            for face in brush.faces:
                if face.texture:
                    all_tex_names.add(face.texture.lower())
    missing = all_tex_names - set(texture_sizes.keys())
    if missing:
        logger.warning(
            "%d textures missing size info (showing first 10): %s  |  texture_sizes has %d entries",
            len(missing), sorted(missing)[:10], len(texture_sizes),
        )
    else:
        logger.info("All %d texture sizes resolved OK", len(all_tex_names))

    # ── 6b. Convert worldspawn brushes ─────────────────────────────────
    all_tri_dicts: list[dict] = []
    all_collision: list[list[float]] = []

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

    # ── 7. Process brush entities ──────────────────────────────────────
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

    # ── 8. Find spawn point ────────────────────────────────────────────
    spawn_pos, spawn_yaw = _find_spawn(entities, scale=scale)
    if spawn_pos is not None:
        logger.info("Spawn point: %s  yaw=%.1f", spawn_pos, spawn_yaw)
    else:
        logger.warning("No spawn point entity found; defaulting to origin")

    # ── 8b. Parse Half-Life light entities ─────────────────────────────
    _LIGHT_CLASSNAMES = {"light", "light_environment", "light_spot"}
    lights: list[LightEntity] = []

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

        # _light "R G B I" (RGB 0-255, I = intensity).
        light_raw = ent.properties.get("_light", "255 255 255 200")
        lp = light_raw.split()
        r, g, b, intensity = 255.0, 255.0, 255.0, 200.0
        try:
            if len(lp) >= 3:
                r, g, b = float(lp[0]), float(lp[1]), float(lp[2])
            if len(lp) >= 4:
                intensity = float(lp[3])
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
            fade=fade,
            falloff=falloff,
            style=style,
        ))

    if lights:
        logger.info("Parsed %d light entities", len(lights))

    # ── 9. Compute bounds ──────────────────────────────────────────────
    bounds_min, bounds_max = _compute_bounds(all_tri_dicts)

    # ── 10. Resolve material definitions ───────────────────────────────
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

    # ── 11. Build output ───────────────────────────────────────────────
    logger.info(
        "Conversion complete: %d render tris, %d collision tris, %d materials",
        len(all_tri_dicts),
        len(all_collision),
        len(unique_materials),
    )

    return MapConvertResult(
        triangles=all_tri_dicts,
        collision_triangles=all_collision,
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
    )
