from __future__ import annotations

from pathlib import Path

from panda3d.core import (
    ColorBlendAttrib,
    CompassEffect,
    DepthOffsetAttrib,
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LVector3f,
    LVector4f,
    PNMImage,
    Shader,
    Texture,
    TransparencyAttrib,
)

from ivan.world.scene_layers.contracts import SceneLayerContract


_MOCK_SKYBOX_VERT = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
out vec3 v_dir;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_dir = normalize(p3d_Vertex.xyz);
}
"""

_MOCK_SKYBOX_FRAG = """
#version 130
uniform samplerCube sky_cube;
in vec3 v_dir;
out vec4 fragColor;
void main() {
    vec3 c = texture(sky_cube, normalize(v_dir)).rgb;
    fragColor = vec4(c, 1.0);
}
"""


def _build_mock_global_cubemap() -> Texture:
    """
    Create a simple global cubemap placeholder.
    This avoids near-card seams and keeps horizon behavior stable.
    """
    tex = Texture("mock-global-cubemap")
    size = 96
    tex.setupCubeMap(size, Texture.T_unsigned_byte, Texture.F_rgba8)

    def _dir_for_cube_face(face: int, u: float, v: float) -> LVector3f:
        if face == 0:  # +X
            d = LVector3f(1.0, -v, -u)
        elif face == 1:  # -X
            d = LVector3f(-1.0, -v, u)
        elif face == 2:  # +Y
            d = LVector3f(u, 1.0, v)
        elif face == 3:  # -Y
            d = LVector3f(u, -1.0, -v)
        elif face == 4:  # +Z
            d = LVector3f(u, -v, 1.0)
        else:  # -Z
            d = LVector3f(-u, -v, -1.0)
        if d.lengthSquared() > 1e-8:
            d.normalize()
        return d

    def _sky_color(direction: LVector3f) -> tuple[float, float, float]:
        # Continuous direction-based gradient (same function for all faces).
        # This removes face seams that looked like "angle-dependent fog".
        t = max(0.0, min(1.0, (float(direction.z) + 1.0) * 0.5))
        sky = (0.52, 0.66, 0.84)
        horizon = (0.73, 0.76, 0.80)
        ground = (0.19, 0.21, 0.24)
        hz = max(0.0, 1.0 - abs(float(direction.z))) * 0.10
        az = float(direction.y) * 0.03
        if t >= 0.55:
            tt = (t - 0.55) / 0.45
            base = (
                horizon[0] + (sky[0] - horizon[0]) * tt,
                horizon[1] + (sky[1] - horizon[1]) * tt,
                horizon[2] + (sky[2] - horizon[2]) * tt,
            )
        else:
            tt = t / 0.55
            base = (
                ground[0] + (horizon[0] - ground[0]) * tt,
                ground[1] + (horizon[1] - ground[1]) * tt,
                ground[2] + (horizon[2] - ground[2]) * tt,
            )
        r = max(0.0, min(1.0, base[0] + hz + az))
        g = max(0.0, min(1.0, base[1] + hz + az * 0.7))
        b = max(0.0, min(1.0, base[2] + hz * 1.1))
        return (r, g, b)

    for face in range(6):
        img = PNMImage(size, size, 4)
        for y in range(size):
            v = ((float(y) + 0.5) / float(size)) * 2.0 - 1.0
            for x in range(size):
                u = ((float(x) + 0.5) / float(size)) * 2.0 - 1.0
                direction = _dir_for_cube_face(face, u, v)
                r, g, b = _sky_color(direction)
                img.setXelA(x, y, r, g, b, 1.0)
        tex.load(img, face, 0)
    tex.setWrapU(Texture.WM_clamp)
    tex.setWrapV(Texture.WM_clamp)
    tex.setMinfilter(Texture.FT_linear)
    tex.setMagfilter(Texture.FT_linear)
    return tex


def attach_triangle_map_geometry(scene: SceneLayerContract, *, render, triangles: list[list[float]]) -> None:
    """Attach legacy position-only geometry (format v1)."""
    # Generated Dust2 asset currently includes positions only (no UV/material data).
    # For visibility we generate world-space UVs and apply a debug checker texture.
    vdata = GeomVertexData(f"{scene._map_id}-map", GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
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
    geom_node = GeomNode(f"{scene._map_id}-map-geom")
    geom_node.addGeom(geom)

    map_np = render.attachNewNode(geom_node)
    map_np.setColor(0.73, 0.67, 0.53, 1)
    map_np.setTwoSided(False)
    map_np.setTexture(scene._make_debug_checker_texture(), 1)


def attach_triangle_map_geometry_v2_unlit(
    scene: SceneLayerContract, *, loader, render, triangles: list[dict]
) -> None:
    """
    Attach v2-format triangle geometry without lightmap shader.
    """
    # Batch by material only (no lightmap IDs) for runtime path.
    tris_by_mat: dict[str, list[dict]] = {}
    for t in triangles:
        m = t.get("m")
        if not isinstance(m, str):
            continue
        tris_by_mat.setdefault(m, []).append(t)
    tex_cache: dict[str, Texture | None] = {}
    missing_cache: set[str] = set()

    for mat_name, tris in tris_by_mat.items():
        vdata = GeomVertexData(
            f"{scene._map_id}-map-{mat_name}", GeomVertexFormat.getV3n3t2(), Geom.UHStatic
        )
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")
        tw = GeomVertexWriter(vdata, "texcoord")
        prim = GeomTriangles(Geom.UHStatic)

        for tri in tris:
            p = tri.get("p")
            n = tri.get("n")
            uv = tri.get("uv")
            if not (isinstance(p, list) and len(p) == 9):
                continue
            if not (isinstance(n, list) and len(n) == 9):
                continue
            if not (isinstance(uv, list) and len(uv) == 6):
                continue

            base = vdata.getNumRows()
            for vi in range(3):
                px, py, pz = float(p[vi * 3]), float(p[vi * 3 + 1]), float(p[vi * 3 + 2])
                nx, ny, nz = float(n[vi * 3]), float(n[vi * 3 + 1]), float(n[vi * 3 + 2])
                tu, tv = float(uv[vi * 2]), float(uv[vi * 2 + 1])
                vw.addData3f(px, py, pz)
                nw.addData3f(nx, ny, nz)
                tw.addData2f(tu, tv)
            prim.addVertices(base, base + 1, base + 2)

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        geom_node = GeomNode(f"{scene._map_id}-geom-{mat_name}")
        geom_node.addGeom(geom)
        np = render.attachNewNode(geom_node)
        np.setTwoSided(False)

        if mat_name.startswith("{"):
            np.setTransparency(TransparencyAttrib.M_binary)
            try:
                np.setAttrib(DepthOffsetAttrib.make(1))
            except Exception:
                pass

        tex: Texture | None = tex_cache.get(mat_name)
        if mat_name in missing_cache:
            tex = None
        if tex is None and mat_name not in missing_cache:
            tex_path = scene._resolve_material_texture_path(material_name=mat_name)
            if tex_path and tex_path.exists():
                tex = loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
                if tex is not None:
                    tex.setWrapU(Texture.WM_repeat)
                    tex.setWrapV(Texture.WM_repeat)
                    if mat_name.startswith("{"):
                        tex.setMinfilter(Texture.FT_nearest)
                        tex.setMagfilter(Texture.FT_nearest)
                tex_cache[mat_name] = tex
            else:
                missing_cache.add(mat_name)
        if tex is not None:
            np.setTexture(tex, 1)
        else:
            np.setTexture(scene._make_debug_checker_texture(), 1)

        # Runtime path: use setShaderAuto so geometry receives scene lights (no baked lightmap).
        np.setShaderAuto()


def attach_triangle_map_geometry_v2(scene: SceneLayerContract, *, loader, render, triangles: list[dict]) -> None:
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
    cls = scene.__class__
    white = getattr(cls, "_TEX_WHITE", None)
    black = getattr(cls, "_TEX_BLACK", None)
    if not isinstance(white, Texture):
        white = scene._make_solid_texture(name="lm-white", rgba=(1.0, 1.0, 1.0, 1.0))
        setattr(cls, "_TEX_WHITE", white)
    if not isinstance(black, Texture):
        black = scene._make_solid_texture(name="lm-black", rgba=(0.0, 0.0, 0.0, 1.0))
        setattr(cls, "_TEX_BLACK", black)
    sh = scene._lightmap_shader()

    # If PVS is active, precompute initial world-face visibility from the spawn point so we can
    # avoid loading thousands of per-face lightmap textures for faces that start hidden.
    scene._vis_initial_world_face_flags = None
    if scene._vis_goldsrc is not None:
        try:
            pos = scene.spawn_point
            leaf = scene._vis_goldsrc.point_leaf(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
            scene._vis_initial_world_face_flags = scene._vis_goldsrc.visible_world_face_flags_for_leaf(int(leaf))
        except Exception:
            scene._vis_initial_world_face_flags = None
    base_tex_cache: dict[str, Texture | None] = {}
    base_tex_missing: set[str] = set()

    for (mat_name, lmi), tris in tris_by_key.items():
        vdata = GeomVertexData(
            f"{scene._map_id}-map-{mat_name}-{lmi}", scene._vformat_v3n3c4t2t2(), Geom.UHStatic
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
        geom_node = GeomNode(f"{scene._map_id}-geom-{mat_name}")
        geom_node.addGeom(geom)
        np = render.attachNewNode(geom_node)
        np.setTwoSided(False)
        # Baked path: lightmaps supply lighting; block runtime lights to avoid double-lighting.
        # Runtime path (v2_unlit) never uses setLightOff so geometry receives scene lights via setShaderAuto.
        np.setLightOff(1)
        if isinstance(lmi, int):
            scene._vis_face_nodes.setdefault(int(lmi), []).append(np)

        meta = scene._materials_meta.get(mat_name, {}) if scene._materials_meta else {}

        # GoldSrc/Xash3D masked textures use "{" prefix (colorkeyed/1-bit transparency).
        # Enable binary transparency so the alpha channel from imported PNGs is respected.
        if mat_name.startswith("{"):
            np.setTransparency(TransparencyAttrib.M_binary)
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

        tex: Texture | None = base_tex_cache.get(mat_name)
        if mat_name in base_tex_missing:
            tex = None
        if tex is None and mat_name not in base_tex_missing:
            tex_path = scene._resolve_material_texture_path(material_name=mat_name)
            if tex_path and tex_path.exists():
                tex = loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
                if tex is not None:
                    tex.setWrapU(Texture.WM_repeat)
                    tex.setWrapV(Texture.WM_repeat)
                    if mat_name.startswith("{"):
                        tex.setMinfilter(Texture.FT_nearest)
                        tex.setMagfilter(Texture.FT_nearest)
                base_tex_cache[mat_name] = tex
            else:
                base_tex_missing.add(mat_name)
        if tex is not None:
            np.setTexture(tex, 1)
        else:
            np.setTexture(scene._make_debug_checker_texture(), 1)

        # Apply baked lightmaps (Source: single; GoldSrc: up to 4 styles).
        lm_entry = scene._lightmap_faces.get(lmi) if (lmi is not None and scene._lightmap_faces) else None
        if isinstance(lm_entry, dict):
            paths = lm_entry.get("paths")
            styles = lm_entry.get("styles")
            if not (isinstance(paths, list) and len(paths) == 4):
                paths = [None, None, None, None]
            if not (isinstance(styles, list) and len(styles) == 4):
                styles = [0, None, None, None]

            lm_texs: list[Texture] = [black, black, black, black]
            lm_scales = [0.0, 0.0, 0.0, 0.0]

            defer = False
            if (
                scene._vis_goldsrc is not None
                and scene._vis_initial_world_face_flags is not None
                and isinstance(lmi, int)
            ):
                w0 = int(scene._vis_goldsrc.world_first_face)
                w1 = int(scene._vis_goldsrc.world_face_end)
                if int(w0) <= int(lmi) < int(w1):
                    defer = not bool(scene._vis_initial_world_face_flags[int(lmi - w0)])

            for i in range(4):
                p = paths[i]
                if (not defer) and isinstance(p, Path) and p.exists():
                    t = loader.loadTexture(Filename.fromOsSpecific(str(p)))
                    if t is not None:
                        t.setWrapU(Texture.WM_clamp)
                        t.setWrapV(Texture.WM_clamp)
                        t.setMinfilter(Texture.FT_linear)
                        t.setMagfilter(Texture.FT_linear)
                        lm_texs[i] = t
                style_i = styles[i]
                if style_i is None:
                    if isinstance(p, Path) and p.exists():
                        lm_scales[i] = 1.0
                elif style_i != 255:
                    lm_scales[i] = 1.0

            np.setShader(sh, 1)
            np.setShaderInput("base_tex", tex if tex is not None else white)
            np.setShaderInput("lm_tex0", lm_texs[0])
            np.setShaderInput("lm_tex1", lm_texs[1])
            np.setShaderInput("lm_tex2", lm_texs[2])
            np.setShaderInput("lm_tex3", lm_texs[3])
            np.setShaderInput("lm_scales", LVector4f(*lm_scales))

            alpha_test = 1 if (mat_name.startswith("{") or (isinstance(meta, dict) and meta.get("alphatest"))) else 0
            np.setShaderInput("alpha_test", int(alpha_test))
            np.setColorOff(1)
            try:
                if scene._lightstyle_mode == "animate":
                    st = [int(x) if isinstance(x, int) else None for x in styles]
                    if any((s is not None and int(s) != 255 and int(s) in scene._lightstyle_animated_styles) for s in st):
                        scene._lightmap_nodes.append((np, st))
            except Exception:
                pass

            if defer and isinstance(lmi, int):
                ent = scene._vis_deferred_lightmaps.get(int(lmi))
                if not isinstance(ent, dict):
                    ent = {"paths": list(paths), "nodepaths": [], "loader": loader}
                    scene._vis_deferred_lightmaps[int(lmi)] = ent
                nps = ent.get("nodepaths")
                if isinstance(nps, list):
                    nps.append(np)


def setup_skybox(
    scene: SceneLayerContract,
    *,
    loader,
    camera,
    skyname: str,
    fallback_skyname: str | None = None,
) -> tuple[str, str]:
    """Attach a global mocked cubemap sky."""
    if scene._skybox_np is not None:
        scene._skybox_np.removeNode()
        scene._skybox_np = None

    requested = str(skyname or "").strip()
    fallback = str(fallback_skyname or "").strip()
    active = requested or fallback or "default_horizon"
    sky_source = "mock-global-cubemap"

    root = camera.getParent().attachNewNode("skybox-root")
    try:
        root.setEffect(CompassEffect.make(camera, CompassEffect.P_pos))
    except Exception:
        pass
    root.setBin("background", 0)
    root.setDepthWrite(False)
    root.setDepthTest(False)
    root.setLightOff(1)
    root.setFogOff(1)

    # Keep the sky far and camera-centered.
    size = 2500.0
    try:
        cam_lens = camera.node().getLens() if hasattr(camera, "node") else None
        if cam_lens is not None and hasattr(cam_lens, "getFar"):
            far_plane = float(cam_lens.getFar())
            if far_plane > 1.0:
                size = max(1200.0, far_plane * 0.7)
    except Exception:
        pass

    sphere = loader.loadModel("models/misc/sphere")
    sphere.reparentTo(root)
    sphere.setScale(size)
    sphere.setTwoSided(True)
    sphere.setLightOff(1)
    sphere.setFogOff(1)
    sphere.setDepthWrite(False)
    sphere.setDepthTest(False)
    sphere.setBin("background", 0)

    cls = scene.__class__
    shader = getattr(cls, "_MOCK_SKYBOX_SHADER", None)
    if not isinstance(shader, Shader):
        shader = Shader.make(Shader.SL_GLSL, _MOCK_SKYBOX_VERT, _MOCK_SKYBOX_FRAG)
        setattr(cls, "_MOCK_SKYBOX_SHADER", shader)
    cubemap = getattr(cls, "_MOCK_SKYBOX_CUBEMAP", None)
    if not isinstance(cubemap, Texture):
        cubemap = _build_mock_global_cubemap()
        setattr(cls, "_MOCK_SKYBOX_CUBEMAP", cubemap)
    sphere.setShader(shader, 1)
    sphere.setShaderInput("sky_cube", cubemap)

    scene._skybox_np = root
    return active, sky_source

