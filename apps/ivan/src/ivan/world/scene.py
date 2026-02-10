from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from panda3d.core import (
    GeomVertexFormat,
    LVector3f,
    LVector4f,
    Shader,
    Texture,
)

from ivan.app_config import MAP_PROFILE_DEV_FAST
from ivan.common.aabb import AABB
from ivan.world.scene_layers.assets import (
    build_material_texture_index,
    resolve_lightmaps,
    resolve_map_bundle_path,
    resolve_material_root,
    resolve_material_texture_path,
)
from ivan.world.scene_layers.lightstyles import (
    lightstyle_scale,
    resolve_lightstyles,
)
from ivan.world.scene_layers.render_primitives import (
    make_debug_checker_texture,
    make_solid_texture,
    vformat_v3n3c4t2t2,
    world_lightmap_shader,
)
from ivan.world.scene_layers.geometry import (
    attach_triangle_map_geometry,
    attach_triangle_map_geometry_v2,
    attach_triangle_map_geometry_v2_unlit,
    setup_skybox,
)
from ivan.world.lightstyles import lightstyle_pattern_is_animated
from ivan.world.goldsrc_visibility import GoldSrcBspVis
from ivan.world.scene_layers.visibility import (
    best_effort_visibility_leaf,
    ensure_deferred_lightmaps_loaded,
    resolve_visibility,
    tick_visibility,
)
from ivan.world.scene_layers.lighting import (
    apply_fog,
    build_lighting,
    enhance_map_file_lighting,
    lights_from_payload,
)


@dataclass
class _MovingBlock:
    aabb_index: int
    node: object
    base_center: LVector3f
    half: LVector3f
    axis: LVector3f
    amplitude: float
    speed_hz: float
    phase: float


class WorldScene:
    def __init__(self) -> None:
        self.spawn_point = LVector3f(0, 35, 1.9)
        self.spawn_yaw = 0.0
        # Respawn threshold (maps can be far below 0 in Z).
        self.kill_z = -18.0

        self.aabbs: list[AABB] = []
        self.triangles: list[list[float]] | None = None
        self.external_map_loaded = False
        self.triangle_collision_mode = False

        self._material_texture_index: dict[str, Path] | None = None
        self._material_texture_root: Path | None = None
        self._materials_meta: dict[str, dict] | None = None
        # face_idx -> {"paths": [Path|None]*4, "styles": [int|None]*4}
        self._lightmap_faces: dict[int, dict] | None = None
        self._lightstyles: dict[int, str] = {}
        self._lightmap_nodes: list[tuple[object, list[int | None]]] = []
        self._lightstyle_mode: str = "animate"  # animate | static
        self._lightstyle_last_frame: int | None = None
        self._lightstyle_animated_styles: set[int] = set()
        self._map_id: str = "scene"
        self._course: dict | None = None
        # Map bundle world scale (GoldSrc/Source BSPs are typically far larger than our gameplay space).
        # GoldSrc importer convention: world = (x*scale, -y*scale, z*scale).
        self._map_scale: float = 1.0
        self._skybox_np = None
        self._world_root_np = None
        self._camera_np = None

        # Optional GoldSrc PVS visibility culling.
        self._vis_goldsrc: GoldSrcBspVis | None = None
        self._vis_enabled: bool = False
        self._vis_current_leaf: int | None = None
        # face_idx -> [NodePath...]
        self._vis_face_nodes: dict[int, list[object]] = {}
        # face_idx -> {"paths":[Path|None]*4, "styles":[int|None]*4, "nodepaths":[NodePath...]}
        # Used to lazy-load per-face lightmap textures (big GoldSrc maps) when a face becomes visible via PVS.
        self._vis_deferred_lightmaps: dict[int, dict] = {}
        self._vis_initial_world_face_flags: bytearray | None = None
        self._map_json_path: Path | None = None
        self._map_payload: dict | None = None
        self._ambient_np = None
        self._sun_np = None
        self._moving_blocks: list[_MovingBlock] = []
        self._collision_updater = None

    @property
    def map_id(self) -> str:
        return self._map_id

    @property
    def course(self) -> dict | None:
        return self._course

    def set_collision_updater(self, updater) -> None:
        self._collision_updater = updater

    def build(self, *, cfg, loader, render, camera) -> None:
        self._world_root_np = render
        self._camera_np = camera
        self._build_lighting(render)
        self._moving_blocks = []

        if bool(getattr(cfg, "feel_harness", False)):
            self._build_feel_harness_scene(loader=loader, render=render)
            return

        # 1) Explicit map (CLI/config)
        if getattr(cfg, "map_json", None):
            self.external_map_loaded = self._try_load_external_map(
                cfg=cfg,
                map_json=Path(str(cfg.map_json)),
                loader=loader,
                render=render,
                camera=camera,
            )
            if self.external_map_loaded:
                return

        # Official Panda3D sample environment model used in basic tutorial scenes.
        env = loader.loadModel("models/environment")
        env.reparentTo(render)
        env.setScale(0.25)
        env.setPos(-8, 42, 0)
        self._build_graybox_scene(loader=loader, render=render)

    def tick(self, *, now: float) -> None:
        """
        Per-frame hook used by the main update loop.

        Currently used for GoldSrc-style lightstyle animation (if patterns are present in the bundle).
        """

        # 1) Lightstyle animation (10Hz like Quake/GoldSrc).
        if self._lightmap_nodes and self._lightstyle_mode == "animate":
            frame = int(float(now) * 10.0)
            if self._lightstyle_last_frame is None or int(frame) != int(self._lightstyle_last_frame):
                self._lightstyle_last_frame = int(frame)

                # Many maps have thousands of lightmapped surfaces but only a small subset uses
                # animated lightstyles. Keep this update strictly at 10Hz and memoize per-style tuple.
                cached: dict[tuple[int | None, int | None, int | None, int | None], LVector4f] = {}

                for np, styles in self._lightmap_nodes:
                    # Normalize to a stable 4-tuple key.
                    s0 = styles[0] if len(styles) > 0 else None
                    s1 = styles[1] if len(styles) > 1 else None
                    s2 = styles[2] if len(styles) > 2 else None
                    s3 = styles[3] if len(styles) > 3 else None
                    key = (s0, s1, s2, s3)

                    vec = cached.get(key)
                    if vec is None:
                        scales: list[float] = [0.0, 0.0, 0.0, 0.0]
                        for i, s in enumerate(key):
                            if s is None or int(s) == 255:
                                continue
                            scales[i] = self._lightstyle_scale(style=int(s), frame=frame)
                        vec = LVector4f(*scales)
                        cached[key] = vec

                    try:
                        np.setShaderInput("lm_scales", vec)
                    except Exception:
                        # If the node was removed or shader isn't active, ignore.
                        pass

        # 2) Visibility culling (GoldSrc PVS) - only updates when camera leaf changes.
        if self._vis_enabled:
            self._tick_visibility()

        # 3) Deterministic moving-platform updates for feel harness scenarios.
        if self._moving_blocks:
            self._tick_moving_blocks(now=now)

    def set_visibility_enabled(self, enabled: bool) -> None:
        """
        Enable/disable runtime visibility culling.

        Default is OFF because some maps/positions can cause visible popping.
        """

        enabled = bool(enabled)
        if enabled == bool(self._vis_enabled):
            return

        # Lazy-enable: attempt to load/build cache if we didn't resolve it at map load.
        if enabled and self._vis_goldsrc is None and self._map_json_path is not None and isinstance(self._map_payload, dict):
            try:
                class _Cfg:
                    visibility = {"enabled": True, "mode": "goldsrc_pvs", "build_cache": True}

                self._vis_goldsrc = self._resolve_visibility(cfg=_Cfg(), map_json=self._map_json_path, payload=self._map_payload)
            except Exception:
                self._vis_goldsrc = None

        self._vis_enabled = enabled and (self._vis_goldsrc is not None)

        # Reset state so the next tick applies cleanly.
        self._vis_current_leaf = None

        if not self._vis_enabled:
            # Show everything.
            try:
                for nodes in self._vis_face_nodes.values():
                    for np in nodes:
                        np.show()
            except Exception:
                pass
            return

        # Apply immediately to avoid a one-frame "everything visible" flash.
        self._tick_visibility()

    def _tick_visibility(self) -> None:
        tick_visibility(self)

    def _best_effort_visibility_leaf(self, *, pos: LVector3f) -> int | None:
        return best_effort_visibility_leaf(self, pos=pos)

    def _ensure_deferred_lightmaps_loaded(self, *, face_idx: int) -> None:
        ensure_deferred_lightmaps_loaded(self, face_idx=face_idx)

    def _build_lighting(self, render) -> None:
        build_lighting(self, render=render)

    def _apply_fog(self, *, cfg, render) -> None:
        apply_fog(self, cfg=cfg, render=render)

    def _enhance_map_file_lighting(self, render, lights) -> None:
        enhance_map_file_lighting(self, render=render, lights=lights)

    @staticmethod
    def _lights_from_payload(*, payload: dict) -> list:
        return lights_from_payload(payload=payload)

    @staticmethod
    def _resolve_lightstyles(*, payload: dict, cfg: dict | None) -> tuple[dict[int, str], str]:
        # Delegated to a lower-level helper module so `WorldScene` stays orchestration-focused.
        return resolve_lightstyles(payload=payload, cfg=cfg)

    def _lightstyle_scale(self, *, style: int, frame: int) -> float:
        return lightstyle_scale(style=style, frame=frame, styles=self._lightstyles)

    def _build_graybox_scene(self, *, loader, render) -> None:
        # Broad collision-safe floor under the full play area to avoid edge fallthrough perception.
        self._add_block(loader=loader, render=render, pos=(0, 35, -2.0), half=(140, 140, 2.0), color=(0.15, 0.17, 0.2, 1))
        # Visible center platform used as reliable spawn landmark.
        self._add_block(loader=loader, render=render, pos=(0, 35, 0.4), half=(3.5, 3.5, 0.4), color=(0.24, 0.44, 0.60, 1))

        self._add_block(loader=loader, render=render, pos=(-2, 10, 0.8), half=(1.0, 1.0, 0.8), color=(0.35, 0.45, 0.55, 1))
        self._add_block(loader=loader, render=render, pos=(2, 16, 1.1), half=(1.0, 1.0, 1.1), color=(0.35, 0.45, 0.55, 1))
        self._add_block(loader=loader, render=render, pos=(-1.8, 22, 1.3), half=(1.0, 1.0, 1.3), color=(0.35, 0.45, 0.55, 1))

        self._add_block(loader=loader, render=render, pos=(-5.5, 36, 2.8), half=(0.55, 7.0, 2.8), color=(0.2, 0.52, 0.72, 1))
        self._add_block(loader=loader, render=render, pos=(5.5, 47, 2.8), half=(0.55, 7.0, 2.8), color=(0.2, 0.52, 0.72, 1))

        self._add_block(loader=loader, render=render, pos=(0, 57, 0.8), half=(3.8, 2.2, 0.8), color=(0.30, 0.35, 0.4, 1))
        self._add_block(loader=loader, render=render, pos=(0, 66, 2.6), half=(4.0, 4.0, 0.6), color=(0.2, 0.56, 0.36, 1))

        self._add_block(loader=loader, render=render, pos=(8, 56, 1.6), half=(2.5, 8.0, 0.4), color=(0.45, 0.3, 0.18, 1))

    def _build_feel_harness_scene(self, *, loader, render) -> None:
        """Minimal deterministic movement harness: flat/slope/step/wall/ledge/moving platform."""

        self._map_id = "feel_harness"
        self.spawn_point = LVector3f(0.0, 0.0, 1.9)
        self.spawn_yaw = 0.0
        self.kill_z = -20.0

        # Flat ground.
        self._add_block(loader=loader, render=render, pos=(0.0, 10.0, -1.5), half=(28.0, 24.0, 1.5), color=(0.18, 0.2, 0.24, 1.0))
        # Small step.
        self._add_block(loader=loader, render=render, pos=(-5.0, 5.0, 0.25), half=(1.0, 1.0, 0.25), color=(0.26, 0.42, 0.55, 1.0))
        # Wall.
        self._add_block(loader=loader, render=render, pos=(6.0, 6.0, 2.0), half=(0.45, 3.0, 2.0), color=(0.24, 0.48, 0.7, 1.0))
        # Ledge block.
        self._add_block(loader=loader, render=render, pos=(0.0, 18.0, 1.25), half=(3.0, 2.0, 1.25), color=(0.23, 0.45, 0.34, 1.0))
        # Slope approximation via stepped blocks.
        slope_start = -10.0
        for i in range(8):
            h = 0.10 + 0.10 * float(i)
            self._add_block(
                loader=loader,
                render=render,
                pos=(slope_start + float(i) * 1.15, 12.0, h * 0.5),
                half=(0.58, 2.0, h * 0.5),
                color=(0.34, 0.36, 0.4, 1.0),
            )

        # Moving platform: deterministic sinusoid along X axis.
        idx, node = self._add_block(
            loader=loader,
            render=render,
            pos=(0.0, 24.0, 0.5),
            half=(1.8, 1.8, 0.25),
            color=(0.55, 0.32, 0.2, 1.0),
        )
        axis = LVector3f(1.0, 0.0, 0.0)
        axis.normalize()
        self._moving_blocks.append(
            _MovingBlock(
                aabb_index=int(idx),
                node=node,
                base_center=LVector3f(0.0, 24.0, 0.5),
                half=LVector3f(1.8, 1.8, 0.25),
                axis=axis,
                amplitude=2.4,
                speed_hz=0.25,
                phase=0.0,
            )
        )

    def _tick_moving_blocks(self, *, now: float) -> None:
        for b in self._moving_blocks:
            phase = (float(now) * float(b.speed_hz) * math.tau) + float(b.phase)
            offset = float(math.sin(phase)) * float(b.amplitude)
            center = LVector3f(b.base_center + (b.axis * offset))
            try:
                b.node.setPos(center)
            except Exception:
                pass
            box = AABB(minimum=center - b.half, maximum=center + b.half)
            if 0 <= int(b.aabb_index) < len(self.aabbs):
                self.aabbs[int(b.aabb_index)] = box
            if self._collision_updater is not None:
                try:
                    self._collision_updater(index=int(b.aabb_index), box=box)
                except Exception:
                    pass

    def _add_block(
        self,
        *,
        loader,
        render,
        pos: tuple[float, float, float],
        half: tuple[float, float, float],
        color,
    ) -> tuple[int, object]:
        model = loader.loadModel("models/box")
        model.reparentTo(render)
        model.setPos(*pos)
        model.setScale(*half)
        model.setColor(*color)

        p = LVector3f(*pos)
        h = LVector3f(*half)
        self.aabbs.append(AABB(minimum=p - h, maximum=p + h))
        return (len(self.aabbs) - 1, model)

    def _try_load_external_map(self, *, cfg, map_json: Path, loader, render, camera) -> bool:
        map_json = self._resolve_map_bundle_path(map_json)
        if not map_json:
            return False

        # .map files use a separate loading path (TrenchBroom workflow, no lightmaps).
        if map_json.suffix.lower() == ".map":
            return self._try_load_map_file(cfg=cfg, map_file=map_json, loader=loader, render=render, camera=camera)

        try:
            payload = json.loads(map_json.read_text(encoding="utf-8"))
        except Exception:
            return False
        self._map_json_path = Path(map_json)
        self._map_payload = dict(payload) if isinstance(payload, dict) else None

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
                    self.kill_z = min_z - 5.0
                except Exception:
                    pass

        # Derive a stable map id for node naming/debug.
        map_id = payload.get("map_id")
        if isinstance(map_id, str) and map_id.strip():
            self._map_id = map_id.strip()
        else:
            self._map_id = map_json.stem

        course = payload.get("course")
        self._course = dict(course) if isinstance(course, dict) else None

        spawn = payload.get("spawn", {})
        spawn_pos = spawn.get("position")
        if isinstance(spawn_pos, list) and len(spawn_pos) == 3:
            self.spawn_point = LVector3f(float(spawn_pos[0]), float(spawn_pos[1]), float(spawn_pos[2]) + 1.2)
        spawn_yaw = spawn.get("yaw")
        if isinstance(spawn_yaw, (int, float)):
            self.spawn_yaw = float(spawn_yaw)

        self._material_texture_index = None
        self._material_texture_root = self._resolve_material_root(map_json=map_json, payload=payload)
        try:
            s = float(payload.get("scale") or 1.0)
            self._map_scale = s if s > 0.0 else 1.0
        except Exception:
            self._map_scale = 1.0
        mm = payload.get("materials_meta")
        self._materials_meta = mm if isinstance(mm, dict) else None
        self._lightmap_faces = self._resolve_lightmaps(map_json=map_json, payload=payload)
        payload_lights = self._lights_from_payload(payload=payload)
        self._lightstyles, self._lightstyle_mode = self._resolve_lightstyles(
            payload=payload, cfg=getattr(cfg, "lighting", None)
        )
        self._lightstyle_last_frame = None
        self._lightstyle_animated_styles = {
            int(style) for style, pat in self._lightstyles.items() if lightstyle_pattern_is_animated(str(pat))
        }
        self._lightmap_nodes = []
        self._vis_goldsrc = self._resolve_visibility(cfg=cfg, map_json=map_json, payload=payload)
        self._vis_face_nodes = {}
        self._vis_current_leaf = None
        self._vis_enabled = False

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
                self.triangles = coll or pos_tris
            else:
                self.triangles = pos_tris
            # Dev-fast: use unlit when baked lightmaps absent (fast edit->run without rebake).
            # Prod-baked: always use lightmap path when available.
            profile = getattr(cfg, "map_profile", "") or "prod-baked"
            use_unlit = (
                profile == MAP_PROFILE_DEV_FAST
                and (self._lightmap_faces is None or not self._lightmap_faces)
            )
            if use_unlit:
                self._attach_triangle_map_geometry_v2_unlit(loader=loader, render=render, triangles=triangles)
                if payload_lights:
                    self._enhance_map_file_lighting(render, payload_lights)
            else:
                self._attach_triangle_map_geometry_v2(loader=loader, render=render, triangles=triangles)
            skyname = payload.get("skyname")
            if isinstance(skyname, str) and skyname.strip():
                self._setup_skybox(loader=loader, camera=camera, skyname=skyname.strip())
        else:
            self.triangles = triangles
            self._attach_triangle_map_geometry(render=render, triangles=triangles)

        self.triangle_collision_mode = True
        # Visibility is disabled by default (can be toggled via debug).
        return True

    def _try_load_map_file(self, *, cfg, map_file: Path, loader, render, camera) -> bool:
        """Load a .map file directly (TrenchBroom workflow, no lightmaps)."""
        from ivan.maps.map_converter import convert_map_file
        from ivan.maps.bundle_io import _default_wad_search_dirs, _default_materials_dirs
        from ivan.state import state_dir

        # Use a persistent texture cache so extracted WAD PNGs survive beyond
        # the convert_map_file() call.  Without this the TemporaryDirectory
        # is deleted before the renderer can load the textures.
        tex_cache = state_dir() / "cache" / "map_textures" / map_file.stem
        tex_cache.mkdir(parents=True, exist_ok=True)

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

        # Set spawn.
        if result.spawn_position:
            self.spawn_point = LVector3f(*result.spawn_position)
            self.spawn_point.setZ(self.spawn_point.getZ() + 1.2)
        self.spawn_yaw = result.spawn_yaw

        # Set bounds / kill_z.
        self.kill_z = result.bounds_min[2] - 5.0
        self._map_id = result.map_id
        self._map_scale = 0.03

        # Set up material texture index from converter results.
        self._material_texture_root = None
        self._material_texture_index = {}
        for tex_name, tex_path in result.materials.items():
            if tex_path and tex_path.exists():
                key = tex_name.replace("\\", "/").casefold()
                self._material_texture_index[key] = tex_path

        # Use the same rendering path as map.json v2 but without lightmap shader.
        if result.triangles:
            pos_tris: list[list[float]] = []
            for t in result.triangles:
                p = t.get("p")
                if isinstance(p, list) and len(p) == 9:
                    pos_tris.append([float(x) for x in p])

            if result.collision_triangles:
                self.triangles = result.collision_triangles
            else:
                self.triangles = pos_tris

            self._attach_triangle_map_geometry_v2_unlit(loader=loader, render=render, triangles=result.triangles)
            self.triangle_collision_mode = True

            # Enhanced preview lighting: brighter ambient + HL entity lights.
            self._enhance_map_file_lighting(render, result.lights)

            if result.skyname:
                self._setup_skybox(loader=loader, camera=camera, skyname=result.skyname)

            return True
        return False

    def _attach_triangle_map_geometry_v2_unlit(self, *, loader, render, triangles: list[dict]) -> None:
        attach_triangle_map_geometry_v2_unlit(self, loader=loader, render=render, triangles=triangles)

    def _resolve_visibility(self, *, cfg, map_json: Path, payload: dict) -> GoldSrcBspVis | None:
        return resolve_visibility(self, cfg=cfg, map_json=map_json, payload=payload)

    @staticmethod
    def _resolve_map_bundle_path(map_json: Path) -> Path | None:
        return resolve_map_bundle_path(map_json)

    def _attach_triangle_map_geometry(self, *, render, triangles: list[list[float]]) -> None:
        attach_triangle_map_geometry(self, render=render, triangles=triangles)

    @staticmethod
    def _build_material_texture_index(root: Path) -> dict[str, Path]:
        return build_material_texture_index(root)

    def _resolve_material_texture_path(self, *, material_name: str) -> Path | None:
        # When _material_texture_index is pre-populated (e.g. from .map converter),
        # use it directly even if _material_texture_root is None.
        if self._material_texture_index is None:
            if not self._material_texture_root:
                return None
            self._material_texture_index = self._build_material_texture_index(self._material_texture_root)
        elif not self._material_texture_index and not self._material_texture_root:
            return None
        return resolve_material_texture_path(
            material_name=material_name,
            materials_meta=self._materials_meta,
            material_texture_index=self._material_texture_index,
        )

    @staticmethod
    def _vformat_v3n3c4t2t2() -> GeomVertexFormat:
        cached = getattr(WorldScene, "_VF_V3N3C4T2T2", None)
        if isinstance(cached, GeomVertexFormat):
            return cached
        fmt = vformat_v3n3c4t2t2()
        setattr(WorldScene, "_VF_V3N3C4T2T2", fmt)
        return fmt

    @staticmethod
    def _make_solid_texture(*, name: str, rgba: tuple[float, float, float, float]) -> Texture:
        return make_solid_texture(name=name, rgba=rgba)

    @staticmethod
    def _lightmap_shader() -> Shader:
        cached = getattr(WorldScene, "_LIGHTMAP_SHADER", None)
        if isinstance(cached, Shader):
            return cached

        sh = world_lightmap_shader()
        setattr(WorldScene, "_LIGHTMAP_SHADER", sh)
        return sh

    def _attach_triangle_map_geometry_v2(self, *, loader, render, triangles: list[dict]) -> None:
        attach_triangle_map_geometry_v2(self, loader=loader, render=render, triangles=triangles)

    def _setup_skybox(self, *, loader, camera, skyname: str) -> None:
        setup_skybox(self, loader=loader, camera=camera, skyname=skyname)

    @staticmethod
    def _resolve_material_root(*, map_json: Path, payload: dict) -> Path | None:
        return resolve_material_root(map_json=map_json, payload=payload)

    @staticmethod
    def _resolve_lightmaps(*, map_json: Path, payload: dict) -> dict[int, dict] | None:
        return resolve_lightmaps(map_json=map_json, payload=payload)

    @staticmethod
    def _make_debug_checker_texture() -> Texture:
        return make_debug_checker_texture()
