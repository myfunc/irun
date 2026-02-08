from __future__ import annotations

import json
from pathlib import Path

from panda3d.core import (
    AmbientLight,
    CardMaker,
    ColorBlendAttrib,
    CompassEffect,
    DepthOffsetAttrib,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    InternalName,
    LVector3f,
    LVector4f,
    PNMImage,
    Shader,
    Texture,
    TransparencyAttrib,
)

from ivan.common.aabb import AABB
from ivan.paths import app_root as ivan_app_root


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
        self._map_id: str = "scene"
        self._course: dict | None = None
        self._skybox_np = None

    @property
    def map_id(self) -> str:
        return self._map_id

    @property
    def course(self) -> dict | None:
        return self._course

    def build(self, *, cfg, loader, render, camera) -> None:
        self._build_lighting(render)

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

        if not self._lightmap_nodes:
            return
        if self._lightstyle_mode != "animate":
            return
        # Update at 10Hz like Quake/GoldSrc lightstyles.
        frame = int(float(now) * 10.0)
        for np, styles in self._lightmap_nodes:
            scales: list[float] = [0.0, 0.0, 0.0, 0.0]
            for i in range(4):
                s = styles[i] if i < len(styles) else None
                if s is None or int(s) == 255:
                    continue
                scales[i] = self._lightstyle_scale(style=int(s), frame=frame)
            try:
                np.setShaderInput("lm_scales", LVector4f(*scales))
            except Exception:
                # If the node was removed or shader isn't active, ignore.
                pass

    def _build_lighting(self, render) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor(LVector4f(0.30, 0.30, 0.33, 1))
        render.setLight(render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LVector4f(0.95, 0.93, 0.86, 1))
        sun_np = render.attachNewNode(sun)
        sun_np.setHpr(34, -58, 0)
        render.setLight(sun_np)

    @staticmethod
    def _parse_lightstyles(*, payload: dict) -> dict[int, str]:
        """
        Optional GoldSrc/Quake-style lightstyle patterns.

        Format in map.json:
          "lightstyles": { "32": "mmnmmommom..." , ... }
        """

        raw = payload.get("lightstyles")
        if not isinstance(raw, dict):
            return {}
        out: dict[int, str] = {}
        for k, v in raw.items():
            try:
                idx = int(k)
            except Exception:
                continue
            if not isinstance(v, str) or not v.strip():
                continue
            out[int(idx)] = v.strip()
        return out

    @staticmethod
    def _default_goldsrc_lightstyles() -> dict[int, str]:
        # Common Quake/GoldSrc defaults used by many engines/servers.
        # If the server doesn't send any patterns, style 0 still behaves as constant 1.0 ("m").
        return {
            0: "m",
            1: "mmnmmommommnonmmonqnmmo",
            2: "abcdefghijklmnopqrstuvwxyzyxwvutsrqponmlkjihgfedcba",
            3: "mmmmmaaaaammmmmaaaaaabcdefgabcdefg",
            4: "mamamamamama",
            5: "jklmnopqrstuvwxyzyxwvutsrqponmlkjlk",
            6: "nmonqnmomnmomomno",
            7: "mmmaaaabcdefgmmmmaaaammmaamm",
            8: "mmmaaammmaaammmabcdefaaaammmmabcdefmmmaaaa",
            9: "aaaaaaaazzzzzzzz",
            10: "mmamammmmammamamaaamammma",
            11: "abcdefghijklmnopqrrqponmlkjihgfedcba",
        }

    @classmethod
    def _resolve_lightstyles(cls, *, payload: dict, cfg: dict | None) -> tuple[dict[int, str], str]:
        """
        Decide which lightstyle patterns to use for this run.

        Precedence:
        - cfg.preset (picked from the menu or run.json):
          - original: use map.json lightstyles (if any), fallback to defaults
          - server_defaults: use engine/server defaults
          - static: no animation (all active styles treated as 1.0)
        - cfg.overrides: explicit style->pattern overrides
        """

        preset = "original"
        overrides: dict[int, str] = {}
        if isinstance(cfg, dict):
            p = cfg.get("preset")
            if isinstance(p, str) and p.strip():
                preset = p.strip()
            ov = cfg.get("overrides")
            if isinstance(ov, dict):
                for k, v in ov.items():
                    try:
                        si = int(k)
                    except Exception:
                        continue
                    if isinstance(v, str) and v.strip():
                        overrides[int(si)] = v.strip()

        mode = "animate"
        if preset == "static":
            mode = "static"

        defaults = cls._default_goldsrc_lightstyles()
        from_map = cls._parse_lightstyles(payload=payload)

        if preset == "server_defaults":
            out = dict(defaults)
        else:
            # "original" (and unknown presets): trust map.json patterns if present.
            out = dict(defaults)
            out.update(from_map)

        out.update(overrides)
        if 0 not in out:
            out[0] = "m"
        return (out, mode)

    def _lightstyle_scale(self, *, style: int, frame: int) -> float:
        # GoldSrc/Quake convention:
        # - pattern is a string of chars 'a'..'z'
        # - each char maps to a brightness scale where 'm' is 1.0
        # - server updates at ~10Hz
        if style == 0:
            pat = self._lightstyles.get(0) or "m"
        else:
            pat = self._lightstyles.get(int(style))
        if not pat:
            return 1.0
        i = int(frame) % len(pat)
        c = pat[i]
        if not ("a" <= c <= "z"):
            c = c.lower()
        if not ("a" <= c <= "z"):
            return 1.0
        return max(0.0, float(ord(c) - ord("a")) / 12.0)

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

    def _add_block(
        self,
        *,
        loader,
        render,
        pos: tuple[float, float, float],
        half: tuple[float, float, float],
        color,
    ) -> None:
        model = loader.loadModel("models/box")
        model.reparentTo(render)
        model.setPos(*pos)
        model.setScale(*half)
        model.setColor(*color)

        p = LVector3f(*pos)
        h = LVector3f(*half)
        self.aabbs.append(AABB(minimum=p - h, maximum=p + h))

    def _try_load_external_map(self, *, cfg, map_json: Path, loader, render, camera) -> bool:
        map_json = self._resolve_map_bundle_path(map_json)
        if not map_json:
            return False

        try:
            payload = json.loads(map_json.read_text(encoding="utf-8"))
        except Exception:
            return False

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
        mm = payload.get("materials_meta")
        self._materials_meta = mm if isinstance(mm, dict) else None
        self._lightmap_faces = self._resolve_lightmaps(map_json=map_json, payload=payload)
        self._lightstyles, self._lightstyle_mode = self._resolve_lightstyles(
            payload=payload, cfg=getattr(cfg, "lighting", None)
        )
        self._lightmap_nodes = []

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
            self._attach_triangle_map_geometry_v2(loader=loader, render=render, triangles=triangles)
            skyname = payload.get("skyname")
            if isinstance(skyname, str) and skyname.strip():
                self._setup_skybox(loader=loader, camera=camera, skyname=skyname.strip())
        else:
            self.triangles = triangles
            self._attach_triangle_map_geometry(render=render, triangles=triangles)

        self.triangle_collision_mode = True
        return True

    @staticmethod
    def _resolve_map_bundle_path(map_json: Path) -> Path | None:
        """
        Resolve a map bundle path.

        Supported inputs:
        - absolute path to map.json
        - relative path to map.json (resolved from cwd, then from apps/ivan/assets/)
        - alias directory under apps/ivan/assets/, e.g. imported/halflife/valve/bounce (implies <alias>/map.json)
        """

        candidates: list[Path] = []
        if map_json.is_absolute():
            candidates.append(map_json)
        else:
            # 1) cwd-relative (CLI usage)
            candidates.append((Path.cwd() / map_json).resolve())
            # 2) assets-relative alias/path
            assets_root = ivan_app_root() / "assets"
            candidates.append((assets_root / map_json).resolve())

        expanded: list[Path] = []
        for c in candidates:
            expanded.append(c)
            # Allow passing a directory alias.
            if c.suffix.lower() != ".json":
                expanded.append(c / "map.json")

        for c in expanded:
            if c.exists() and c.is_file():
                return c
        return None

    def _attach_triangle_map_geometry(self, *, render, triangles: list[list[float]]) -> None:
        # Generated Dust2 asset currently includes positions only (no UV/material data).
        # For visibility we generate world-space UVs and apply a debug checker texture.
        vdata = GeomVertexData(f"{self._map_id}-map", GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vertex_writer = GeomVertexWriter(vdata, "vertex")
        normal_writer = GeomVertexWriter(vdata, "normal")
        uv_writer = GeomVertexWriter(vdata, "texcoord")
        prim = GeomTriangles(Geom.UHStatic)

        uv_scale = 0.20
        for tri in triangles:
            if len(tri) != 9:
                continue

            p0 = LVector3f(tri[0], tri[1], tri[2])
            p1 = LVector3f(tri[3], tri[4], tri[5])
            p2 = LVector3f(tri[6], tri[7], tri[8])

            edge1 = p1 - p0
            edge2 = p2 - p0
            normal = edge1.cross(edge2)
            if normal.lengthSquared() <= 1e-10:
                continue
            normal.normalize()

            base_idx = vdata.getNumRows()
            vertex_writer.addData3f(p0)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p0.x * uv_scale, p0.y * uv_scale)
            vertex_writer.addData3f(p1)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p1.x * uv_scale, p1.y * uv_scale)
            vertex_writer.addData3f(p2)
            normal_writer.addData3f(normal)
            uv_writer.addData2f(p2.x * uv_scale, p2.y * uv_scale)
            prim.addVertices(base_idx, base_idx + 1, base_idx + 2)

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        geom_node = GeomNode(f"{self._map_id}-map-geom")
        geom_node.addGeom(geom)

        map_np = render.attachNewNode(geom_node)
        map_np.setColor(0.73, 0.67, 0.53, 1)
        map_np.setTwoSided(False)
        map_np.setTexture(self._make_debug_checker_texture(), 1)

    @staticmethod
    def _build_material_texture_index(root: Path) -> dict[str, Path]:
        index: dict[str, Path] = {}
        if not root.exists():
            return index
        for p in root.rglob("*.png"):
            rel = p.relative_to(root)
            key = str(rel.with_suffix("")).replace("\\", "/").casefold()
            index[key] = p
        return index

    def _resolve_material_texture_path(self, *, material_name: str) -> Path | None:
        if not self._material_texture_root:
            return None
        if self._material_texture_index is None:
            self._material_texture_index = self._build_material_texture_index(self._material_texture_root)
        base = None
        if self._materials_meta and isinstance(self._materials_meta.get(material_name), dict):
            base = self._materials_meta.get(material_name, {}).get("base_texture")
        if isinstance(base, str) and base.strip():
            key = base.replace("\\", "/").casefold()
        else:
            key = material_name.replace("\\", "/").casefold()
        return self._material_texture_index.get(key)

    @staticmethod
    def _vformat_v3n3c4t2t2() -> GeomVertexFormat:
        # Two UV sets: texcoord (base) and texcoord.1 (lightmap).
        cached = getattr(WorldScene, "_VF_V3N3C4T2T2", None)
        if isinstance(cached, GeomVertexFormat):
            return cached
        arr = GeomVertexArrayFormat()
        arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
        arr.addColumn(InternalName.getNormal(), 3, Geom.NT_float32, Geom.C_normal)
        arr.addColumn(InternalName.getColor(), 4, Geom.NT_float32, Geom.C_color)
        arr.addColumn(InternalName.getTexcoord(), 2, Geom.NT_float32, Geom.C_texcoord)
        arr.addColumn(InternalName.getTexcoordName("1"), 2, Geom.NT_float32, Geom.C_texcoord)
        fmt = GeomVertexFormat()
        fmt.addArray(arr)
        fmt = GeomVertexFormat.registerFormat(fmt)
        setattr(WorldScene, "_VF_V3N3C4T2T2", fmt)
        return fmt

    @staticmethod
    def _make_solid_texture(*, name: str, rgba: tuple[float, float, float, float]) -> Texture:
        img = PNMImage(1, 1)
        img.setXelA(0, 0, float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
        tex = Texture(name)
        tex.load(img)
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        tex.setMinfilter(Texture.FT_nearest)
        tex.setMagfilter(Texture.FT_nearest)
        return tex

    @staticmethod
    def _lightmap_shader() -> Shader:
        cached = getattr(WorldScene, "_LIGHTMAP_SHADER", None)
        if isinstance(cached, Shader):
            return cached

        vshader = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec2 p3d_MultiTexCoord1;
out vec2 v_uv0;
out vec2 v_uv1;
void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  v_uv0 = p3d_MultiTexCoord0;
  v_uv1 = p3d_MultiTexCoord1;
}
"""

        fshader = """
#version 130
uniform sampler2D base_tex;
uniform sampler2D lm_tex0;
uniform sampler2D lm_tex1;
uniform sampler2D lm_tex2;
uniform sampler2D lm_tex3;
uniform vec4 lm_scales;
uniform int alpha_test;
in vec2 v_uv0;
in vec2 v_uv1;
out vec4 fragColor;
void main() {
  vec4 base = texture(base_tex, v_uv0);
  if (alpha_test != 0 && base.a < 0.5) discard;
  vec3 lm = vec3(0.0);
  lm += lm_scales.x * texture(lm_tex0, v_uv1).rgb;
  lm += lm_scales.y * texture(lm_tex1, v_uv1).rgb;
  lm += lm_scales.z * texture(lm_tex2, v_uv1).rgb;
  lm += lm_scales.w * texture(lm_tex3, v_uv1).rgb;
  fragColor = vec4(base.rgb * lm, base.a);
}
"""

        sh = Shader.make(Shader.SL_GLSL, vertex=vshader, fragment=fshader)
        setattr(WorldScene, "_LIGHTMAP_SHADER", sh)
        return sh

    def _attach_triangle_map_geometry_v2(self, *, loader, render, triangles: list[dict]) -> None:
        # Build render geometry with materials + baked lighting (lightmaps, when present).
        # Group by (material, lightmap id) so each draw call can bind the correct lightmap texture.
        tris_by_key: dict[tuple[str, int | None], list[dict]] = {}
        for t in triangles:
            m = t.get("m")
            if not isinstance(m, str):
                continue
            lmi = t.get("lmi")
            lmi_int = int(lmi) if isinstance(lmi, int) else None
            tris_by_key.setdefault((m, lmi_int), []).append(t)

        # Shader resources for baked lightmaps.
        white = getattr(WorldScene, "_TEX_WHITE", None)
        black = getattr(WorldScene, "_TEX_BLACK", None)
        if not isinstance(white, Texture):
            white = self._make_solid_texture(name="lm-white", rgba=(1.0, 1.0, 1.0, 1.0))
            setattr(WorldScene, "_TEX_WHITE", white)
        if not isinstance(black, Texture):
            black = self._make_solid_texture(name="lm-black", rgba=(0.0, 0.0, 0.0, 1.0))
            setattr(WorldScene, "_TEX_BLACK", black)
        sh = self._lightmap_shader()

        for (mat_name, lmi), tris in tris_by_key.items():
            vdata = GeomVertexData(
                f"{self._map_id}-map-{mat_name}-{lmi}", self._vformat_v3n3c4t2t2(), Geom.UHStatic
            )
            vw = GeomVertexWriter(vdata, "vertex")
            nw = GeomVertexWriter(vdata, "normal")
            cw = GeomVertexWriter(vdata, "color")
            tw0 = GeomVertexWriter(vdata, "texcoord")
            tw1 = GeomVertexWriter(vdata, "texcoord.1")
            prim = GeomTriangles(Geom.UHStatic)

            for tri in tris:
                p = tri.get("p")
                n = tri.get("n")
                uv = tri.get("uv")
                lm = tri.get("lm")
                c = tri.get("c")
                if not (isinstance(p, list) and len(p) == 9):
                    continue
                if not (isinstance(n, list) and len(n) == 9):
                    continue
                if not (isinstance(uv, list) and len(uv) == 6):
                    continue
                if not (isinstance(lm, list) and len(lm) == 6):
                    lm = [0.0] * 6
                if not (isinstance(c, list) and len(c) == 12):
                    continue

                base = vdata.getNumRows()
                for vi in range(3):
                    px, py, pz = float(p[vi * 3 + 0]), float(p[vi * 3 + 1]), float(p[vi * 3 + 2])
                    nx, ny, nz = float(n[vi * 3 + 0]), float(n[vi * 3 + 1]), float(n[vi * 3 + 2])
                    tu, tv = float(uv[vi * 2 + 0]), float(uv[vi * 2 + 1])
                    lu, lv = float(lm[vi * 2 + 0]), float(lm[vi * 2 + 1])
                    cr, cg, cb, ca = (
                        float(c[vi * 4 + 0]),
                        float(c[vi * 4 + 1]),
                        float(c[vi * 4 + 2]),
                        float(c[vi * 4 + 3]),
                    )
                    vw.addData3f(px, py, pz)
                    nw.addData3f(nx, ny, nz)
                    tw0.addData2f(tu, tv)
                    tw1.addData2f(lu, lv)
                    cw.addData4f(cr, cg, cb, ca)
                prim.addVertices(base, base + 1, base + 2)

            geom = Geom(vdata)
            geom.addPrimitive(prim)
            geom_node = GeomNode(f"{self._map_id}-geom-{mat_name}")
            geom_node.addGeom(geom)
            np = render.attachNewNode(geom_node)
            np.setTwoSided(False)
            # Imported BSP geometry should be lit by baked lighting, not by the game's ambient/sun lights.
            np.setLightOff(1)

            meta = self._materials_meta.get(mat_name, {}) if self._materials_meta else {}

            # GoldSrc/Xash3D masked textures use "{" prefix (colorkeyed/1-bit transparency).
            # Enable binary transparency so the alpha channel from imported PNGs is respected.
            if mat_name.startswith("{"):
                np.setTransparency(TransparencyAttrib.M_binary)
                # Help avoid z-fighting and colorkey edge artifacts compared to GoldSrc's
                # alpha-tested + nearest-filtered masked textures.
                # Panda3D 1.10 uses DepthOffsetAttrib for depth bias.
                try:
                    np.setAttrib(DepthOffsetAttrib.make(1))
                except Exception:
                    pass
            else:
                if isinstance(meta, dict):
                    if meta.get("nocull"):
                        np.setTwoSided(True)
                    alpha = meta.get("alpha")
                    if isinstance(alpha, (int, float)) and float(alpha) < 1.0:
                        np.setColorScale(1, 1, 1, float(alpha))
                    if meta.get("alphatest"):
                        np.setTransparency(TransparencyAttrib.M_binary)
                    elif meta.get("translucent") or (isinstance(alpha, (int, float)) and float(alpha) < 1.0):
                        np.setTransparency(TransparencyAttrib.M_alpha)
                        np.setBin("transparent", 0)
                        np.setDepthWrite(False)
                    if meta.get("additive"):
                        np.setTransparency(TransparencyAttrib.M_alpha)
                        np.setAttrib(
                            ColorBlendAttrib.make(
                                ColorBlendAttrib.M_add,
                                ColorBlendAttrib.O_incoming_alpha,
                                ColorBlendAttrib.O_one,
                            )
                        )

            tex: Texture | None = None
            tex_path = self._resolve_material_texture_path(material_name=mat_name)
            if tex_path and tex_path.exists():
                tex = loader.loadTexture(str(tex_path))
                if tex is not None:
                    tex.setWrapU(Texture.WM_repeat)
                    tex.setWrapV(Texture.WM_repeat)
                    if mat_name.startswith("{"):
                        tex.setMinfilter(Texture.FT_nearest)
                        tex.setMagfilter(Texture.FT_nearest)
                    np.setTexture(tex, 1)
            else:
                tex = self._make_debug_checker_texture()
                np.setTexture(tex, 1)

            # Apply baked lightmaps (Source: single; GoldSrc: up to 4 styles).
            lm_entry = self._lightmap_faces.get(lmi) if (lmi is not None and self._lightmap_faces) else None
            if isinstance(lm_entry, dict):
                # Paths list is always length 4 (None for missing).
                paths = lm_entry.get("paths")
                styles = lm_entry.get("styles")
                if not (isinstance(paths, list) and len(paths) == 4):
                    paths = [None, None, None, None]
                if not (isinstance(styles, list) and len(styles) == 4):
                    styles = [0, None, None, None]

                lm_texs: list[Texture] = [black, black, black, black]
                lm_scales = [0.0, 0.0, 0.0, 0.0]
                for i in range(4):
                    p = paths[i]
                    if isinstance(p, Path) and p.exists():
                        t = loader.loadTexture(str(p))
                        if t is not None:
                            t.setWrapU(Texture.WM_clamp)
                            t.setWrapV(Texture.WM_clamp)
                            t.setMinfilter(Texture.FT_linear)
                            t.setMagfilter(Texture.FT_linear)
                            lm_texs[i] = t
                    # Style scaling: for now treat present styles as constant 1.0.
                    if styles[i] is not None and styles[i] != 255:
                        lm_scales[i] = 1.0

                np.setShader(sh, 1)
                np.setShaderInput("base_tex", tex if tex is not None else white)
                np.setShaderInput("lm_tex0", lm_texs[0])
                np.setShaderInput("lm_tex1", lm_texs[1])
                np.setShaderInput("lm_tex2", lm_texs[2])
                np.setShaderInput("lm_tex3", lm_texs[3])
                np.setShaderInput("lm_scales", LVector4f(*lm_scales))

                # Respect alpha-cutout materials via discard in shader (improves masked edges).
                alpha_test = 1 if (mat_name.startswith("{") or (isinstance(meta, dict) and meta.get("alphatest"))) else 0
                np.setShaderInput("alpha_test", int(alpha_test))

                # Vertex colors from bsp_tool are a best-effort tint; with baked lightmaps bound,
                # keep the result stable by ignoring per-vertex colors.
                np.setColorOff(1)
                try:
                    self._lightmap_nodes.append((np, [int(x) if isinstance(x, int) else None for x in styles]))
                except Exception:
                    pass

    def _setup_skybox(self, *, loader, camera, skyname: str) -> None:
        # Source convention: materials/skybox/<skyname><face>.vtf -> we converted to PNG.
        if self._skybox_np is not None:
            self._skybox_np.removeNode()
            self._skybox_np = None

        faces = {
            "ft": ("ft", (0, 200, 0), (180, 0, 0)),
            "bk": ("bk", (0, -200, 0), (0, 0, 0)),
            "lf": ("lf", (-200, 0, 0), (90, 0, 0)),
            "rt": ("rt", (200, 0, 0), (-90, 0, 0)),
            "up": ("up", (0, 0, 200), (180, -90, 0)),
            "dn": ("dn", (0, 0, -200), (180, 90, 0)),
        }

        if not self._material_texture_root:
            return
        if self._material_texture_index is None:
            self._material_texture_index = self._build_material_texture_index(self._material_texture_root)

        def find_face(face_suffix: str) -> Path | None:
            # Try a few casing variants; the on-disk files are often mixed-case.
            candidates = [
                f"skybox/{skyname}{face_suffix}",
                f"skybox/{skyname.lower()}{face_suffix}",
                f"skybox/{skyname.upper()}{face_suffix}",
                f"skybox/{skyname.capitalize()}{face_suffix}",
            ]
            for c in candidates:
                p = self._material_texture_index.get(c.casefold())
                if p:
                    return p
            return None

        # Follow camera position but keep world orientation, like Source/GoldSrc.
        root = camera.getParent().attachNewNode("skybox-root")
        try:
            root.setEffect(CompassEffect.make(camera, CompassEffect.P_pos))
        except Exception:
            pass
        root.setBin("background", 0)
        root.setDepthWrite(False)
        root.setDepthTest(False)
        root.setLightOff(1)

        size = 200.0
        for _, (suffix, pos, hpr) in faces.items():
            tex_path = find_face(suffix)
            if not tex_path:
                continue
            cm = CardMaker(f"sky-{suffix}")
            cm.setFrame(-size, size, -size, size)
            card = root.attachNewNode(cm.generate())
            card.setPos(*pos)
            card.setHpr(*hpr)
            tex = loader.loadTexture(str(tex_path))
            if tex is not None:
                tex.setWrapU(Texture.WM_clamp)
                tex.setWrapV(Texture.WM_clamp)
                card.setTexture(tex, 1)

        self._skybox_np = root

    @staticmethod
    def _resolve_material_root(*, map_json: Path, payload: dict) -> Path | None:
        materials = payload.get("materials")
        if not isinstance(materials, dict):
            return None
        converted_root = materials.get("converted_root")
        if not isinstance(converted_root, str) or not converted_root.strip():
            return None

        raw = Path(converted_root)
        # Prefer paths relative to the map bundle directory.
        if not raw.is_absolute():
            cand = (map_json.parent / raw).resolve()
            if cand.exists():
                return cand
        # Back-compat: older bundles store app-root relative paths.
        app_root = ivan_app_root()
        cand = (app_root / raw).resolve()
        if cand.exists():
            return cand
        # Last resort: treat as cwd-relative.
        cand = (Path.cwd() / raw).resolve()
        if cand.exists():
            return cand
        return None

    @staticmethod
    def _resolve_lightmaps(*, map_json: Path, payload: dict) -> dict[int, dict] | None:
        lm = payload.get("lightmaps")
        if not isinstance(lm, dict):
            return None
        faces = lm.get("faces")
        if not isinstance(faces, dict) or not faces:
            return None

        def resolve_path(v: str) -> Path | None:
            raw = Path(v)
            if raw.is_absolute() and raw.exists():
                return raw
            cand = (map_json.parent / raw).resolve()
            if cand.exists():
                return cand
            app_root = ivan_app_root()
            cand = (app_root / raw).resolve()
            if cand.exists():
                return cand
            cand = (Path.cwd() / raw).resolve()
            if cand.exists():
                return cand
            return None

        out: dict[int, dict] = {}
        for k, v in faces.items():
            try:
                idx = int(k)
            except Exception:
                continue
            # Source v2 bundles: faces[idx] = "<path>"
            if isinstance(v, str) and v.strip():
                p = resolve_path(v.strip())
                if p:
                    out[idx] = {"paths": [p, None, None, None], "styles": [0, None, None, None]}
                continue
            # GoldSrc bundles: faces[idx] = {"paths":[...], "styles":[...]}
            if isinstance(v, dict):
                paths = v.get("paths")
                styles = v.get("styles")
                if not (isinstance(paths, list) and len(paths) == 4):
                    continue
                if not (isinstance(styles, list) and len(styles) == 4):
                    styles = [0, None, None, None]
                resolved: list[Path | None] = [None, None, None, None]
                for i in range(4):
                    pv = paths[i]
                    if isinstance(pv, str) and pv.strip():
                        resolved[i] = resolve_path(pv.strip())
                out[idx] = {"paths": resolved, "styles": list(styles)}
        return out or None

    @staticmethod
    def _make_debug_checker_texture() -> Texture:
        img = PNMImage(256, 256)
        # Simple high-contrast checker + grid, so collision/scale issues are visible.
        for y in range(256):
            for x in range(256):
                cx = (x // 32) % 2
                cy = (y // 32) % 2
                base = 0.82 if (cx ^ cy) else 0.25
                if x % 32 == 0 or y % 32 == 0:
                    img.setXel(x, y, 1.0, 0.15, 0.15)
                else:
                    img.setXel(x, y, base, base, base)

        tex = Texture("debug-checker")
        tex.load(img)
        tex.setWrapU(Texture.WM_repeat)
        tex.setWrapV(Texture.WM_repeat)
        tex.setMinfilter(Texture.FT_linear_mipmap_linear)
        tex.setMagfilter(Texture.FT_linear)
        tex.generateRamMipmapImages()
        return tex
