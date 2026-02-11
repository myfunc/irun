from __future__ import annotations

import json
from pathlib import Path
from contextlib import nullcontext

from panda3d.core import LVector3f

from ivan.app_config import MAP_PROFILE_DEV_FAST
from ivan.world.loading_report import (
    LOAD_STAGE_GEOMETRY_BUILD_ATTACH,
    LOAD_STAGE_MAP_PARSE_IMPORT,
    LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE,
    LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD,
)
from ivan.world.lightstyles import lightstyle_pattern_is_animated
from ivan.world.scene_layers.contracts import SceneLayerContract

DEFAULT_SKYBOX_PRESET = "default_horizon"


def _stage_timer(scene: SceneLayerContract, stage_name: str):
    fn = getattr(scene, "_time_load_stage", None)
    if callable(fn):
        return fn(stage_name)
    return nullcontext()


def _normalize_skyname(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    skyname = raw.strip()
    return skyname or None


def _resolve_entry_kind(map_ref: Path) -> str:
    if map_ref.suffix.lower() == ".map":
        return "direct-map"
    marker = map_ref.parent / ".irunmap-extracted.json"
    if marker.exists():
        return "packed-irunmap"
    parts = {p.lower() for p in map_ref.parts}
    if "imported" in parts:
        return "imported-map-json"
    return "map-json"


def _apply_skybox_baseline(
    scene: SceneLayerContract,
    *,
    loader,
    camera,
    map_skyname: str | None,
) -> None:
    requested = map_skyname if map_skyname else DEFAULT_SKYBOX_PRESET
    active, source = scene._setup_skybox(
        loader=loader,
        camera=camera,
        skyname=requested,
        fallback_skyname=DEFAULT_SKYBOX_PRESET,
    )
    scene._active_skyname = active
    if map_skyname:
        scene._sky_source = source if source == "map-skyname" else "map-skyname->default-preset"
    elif source == "default-skyname":
        scene._sky_source = "default-skyname"
    else:
        scene._sky_source = "default-preset"


def try_load_external_map(scene: SceneLayerContract, *, cfg, map_json: Path, loader, render, camera) -> bool:
    """Load `.map`/`map.json`/`.irunmap` into scene runtime state."""
    map_json = scene._resolve_map_bundle_path(map_json)
    if not map_json:
        return False
    scene._runtime_entry_kind = _resolve_entry_kind(map_json)

    # .map files use a separate loading path (TrenchBroom workflow, no lightmaps).
    if map_json.suffix.lower() == ".map":
        return scene._try_load_map_file(cfg=cfg, map_file=map_json, loader=loader, render=render, camera=camera)

    with _stage_timer(scene, LOAD_STAGE_MAP_PARSE_IMPORT):
        try:
            payload = json.loads(map_json.read_text(encoding="utf-8"))
        except Exception:
            return False
    scene._map_json_path = Path(map_json)
    scene._map_payload = dict(payload) if isinstance(payload, dict) else None

    triangles = payload.get("triangles")
    if not isinstance(triangles, list) or not triangles:
        return False

    bounds = payload.get("bounds")
    if isinstance(bounds, dict):
        bmin = bounds.get("min")
        if isinstance(bmin, list) and len(bmin) == 3:
            try:
                min_z = float(bmin[2])
                # Keep a small margin below the lowest geometry.
                scene.kill_z = min_z - 5.0
            except Exception:
                pass

    # Derive a stable map id for node naming/debug.
    map_id = payload.get("map_id")
    if isinstance(map_id, str) and map_id.strip():
        scene._map_id = map_id.strip()
    else:
        scene._map_id = map_json.stem

    course = payload.get("course")
    scene._course = dict(course) if isinstance(course, dict) else None

    spawn = payload.get("spawn", {})
    spawn_pos = spawn.get("position")
    if isinstance(spawn_pos, list) and len(spawn_pos) == 3:
        scene.spawn_point = LVector3f(float(spawn_pos[0]), float(spawn_pos[1]), float(spawn_pos[2]) + 1.2)
    spawn_yaw = spawn.get("yaw")
    if isinstance(spawn_yaw, (int, float)):
        scene.spawn_yaw = float(spawn_yaw)

    with _stage_timer(scene, LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
        scene._material_texture_index = None
        scene._material_texture_root = scene._resolve_material_root(map_json=map_json, payload=payload)
    try:
        s = float(payload.get("scale") or 1.0)
        scene._map_scale = s if s > 0.0 else 1.0
    except Exception:
        scene._map_scale = 1.0
    mm = payload.get("materials_meta")
    scene._materials_meta = mm if isinstance(mm, dict) else None
    scene._lightmap_faces = scene._resolve_lightmaps(map_json=map_json, payload=payload)
    payload_lights = scene._lights_from_payload(payload=payload)
    scene._lightstyles, scene._lightstyle_mode = scene._resolve_lightstyles(
        payload=payload, cfg=getattr(cfg, "lighting", None)
    )
    scene._lightstyle_last_frame = None
    scene._lightstyle_animated_styles = {
        int(style) for style, pat in scene._lightstyles.items() if lightstyle_pattern_is_animated(str(pat))
    }
    scene._lightmap_nodes = []
    with _stage_timer(scene, LOAD_STAGE_VISIBILITY_CACHE_LOAD_BUILD):
        scene._vis_goldsrc = scene._resolve_visibility(cfg=cfg, map_json=map_json, payload=payload)
    scene._vis_face_nodes = {}
    scene._vis_current_leaf = None
    scene._vis_enabled = False

    collision_override = payload.get("collision_triangles")

    # Format v1: triangles is list[list[float]] (positions only)
    # Format v2: triangles is list[dict] with positions, normals, UVs, vertex colors, and material.
    if isinstance(triangles[0], dict):
        pos_tris: list[list[float]] = []
        for t in triangles:
            p = t.get("p")
            if isinstance(p, list) and len(p) == 9:
                pos_tris.append([float(x) for x in p])
        if not pos_tris:
            return False
        # Collision can be filtered at import time (e.g. exclude triggers).
        if isinstance(collision_override, list) and collision_override and isinstance(collision_override[0], list):
            coll: list[list[float]] = []
            for t in collision_override:
                if isinstance(t, list) and len(t) == 9:
                    coll.append([float(x) for x in t])
            scene.triangles = coll or pos_tris
        else:
            scene.triangles = pos_tris
        # Dev-fast: use runtime lighting when baked lightmaps absent (fast edit->run without rebake).
        # Prod-baked: always use lightmap path when available.
        # runtime_lighting=True overrides: force runtime path regardless of lightmaps.
        profile = getattr(cfg, "map_profile", "") or "prod-baked"
        force_runtime = getattr(cfg, "runtime_lighting", None) is True
        use_unlit = force_runtime or (
            profile == MAP_PROFILE_DEV_FAST and (scene._lightmap_faces is None or not scene._lightmap_faces)
        )
        scene._runtime_only_lighting = use_unlit
        scene._runtime_path_label = "runtime-lighting" if use_unlit else "baked-lightmaps"
        scene._runtime_path_source = (
            "forced-by-runtime-lighting-flag"
            if force_runtime
            else ("dev-fast-no-lightmaps" if use_unlit else "baked-lightmaps-present")
        )
        with _stage_timer(scene, LOAD_STAGE_GEOMETRY_BUILD_ATTACH):
            if use_unlit:
                scene._attach_triangle_map_geometry_v2_unlit(loader=loader, render=render, triangles=triangles)
                if payload_lights:
                    scene._enhance_map_file_lighting(render, payload_lights)
            else:
                scene._runtime_only_lighting = False
                scene._attach_triangle_map_geometry_v2(loader=loader, render=render, triangles=triangles)
        with _stage_timer(scene, LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
            _apply_skybox_baseline(
                scene,
                loader=loader,
                camera=camera,
                map_skyname=_normalize_skyname(payload.get("skyname")),
            )
    else:
        scene.triangles = triangles
        with _stage_timer(scene, LOAD_STAGE_GEOMETRY_BUILD_ATTACH):
            scene._attach_triangle_map_geometry(render=render, triangles=triangles)
        scene._runtime_only_lighting = True  # format v1 has no lightmaps
        scene._runtime_path_label = "runtime-lighting"
        scene._runtime_path_source = "legacy-format-v1"
        with _stage_timer(scene, LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
            _apply_skybox_baseline(
                scene,
                loader=loader,
                camera=camera,
                map_skyname=_normalize_skyname(payload.get("skyname")),
            )

    scene.triangle_collision_mode = True
    # Visibility is disabled by default (can be toggled via debug).
    return True


def try_load_map_file(scene: SceneLayerContract, *, map_file: Path, loader, render, camera) -> bool:
    """Load source `.map` directly for fast edit->run iteration."""
    from ivan.maps.bundle_io import _default_materials_dirs, _default_wad_search_dirs
    from ivan.maps.map_converter import convert_map_file
    from ivan.state import state_dir

    # Use a persistent texture cache so extracted WAD PNGs survive beyond
    # the convert_map_file() call. Without this the temporary dir is deleted too early.
    tex_cache = state_dir() / "cache" / "map_textures" / map_file.stem
    tex_cache.mkdir(parents=True, exist_ok=True)

    with _stage_timer(scene, LOAD_STAGE_MAP_PARSE_IMPORT):
        try:
            result = convert_map_file(
                map_file,
                scale=0.03,
                wad_search_dirs=_default_wad_search_dirs(map_file),
                materials_dirs=_default_materials_dirs(map_file),
                texture_cache_dir=tex_cache,
            )
        except Exception as e:
            print(f"[IVAN] Failed to load .map file: {e}")
            return False

    if result.spawn_position:
        scene.spawn_point = LVector3f(*result.spawn_position)
        scene.spawn_point.setZ(scene.spawn_point.getZ() + 1.2)
    scene.spawn_yaw = result.spawn_yaw

    scene.kill_z = result.bounds_min[2] - 5.0
    scene._map_id = result.map_id
    # Synthetic payload keeps direct .map behavior aligned with map.json/.irunmap.
    payload: dict[str, object] = {}
    if result.fog:
        payload["fog"] = result.fog
    if result.skyname:
        payload["skyname"] = str(result.skyname)
    scene._map_payload = payload
    scene._runtime_entry_kind = "direct-map"
    scene._map_scale = 0.03

    with _stage_timer(scene, LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
        scene._material_texture_root = None
        scene._material_texture_index = {}
        for tex_name, tex_path in result.materials.items():
            if tex_path and tex_path.exists():
                key = tex_name.replace("\\", "/").casefold()
                scene._material_texture_index[key] = tex_path

    if result.triangles:
        pos_tris: list[list[float]] = []
        for t in result.triangles:
            p = t.get("p")
            if isinstance(p, list) and len(p) == 9:
                pos_tris.append([float(x) for x in p])

        if result.collision_triangles:
            scene.triangles = result.collision_triangles
        else:
            scene.triangles = pos_tris

        with _stage_timer(scene, LOAD_STAGE_GEOMETRY_BUILD_ATTACH):
            scene._attach_triangle_map_geometry_v2_unlit(loader=loader, render=render, triangles=result.triangles)
            scene._runtime_only_lighting = True  # .map files have no baked lightmaps
            scene._runtime_path_label = "runtime-lighting"
            scene._runtime_path_source = "direct-map-no-lightmaps"
            scene.triangle_collision_mode = True
            scene._enhance_map_file_lighting(render, result.lights)
        with _stage_timer(scene, LOAD_STAGE_MATERIAL_SKY_FOG_RESOLVE):
            _apply_skybox_baseline(
                scene,
                loader=loader,
                camera=camera,
                map_skyname=_normalize_skyname(result.skyname),
            )
        return True
    return False

