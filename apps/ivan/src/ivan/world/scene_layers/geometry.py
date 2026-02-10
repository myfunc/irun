from __future__ import annotations

from pathlib import Path

from panda3d.core import (
    CardMaker,
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
    Texture,
    TransparencyAttrib,
)


def attach_triangle_map_geometry(scene, *, render, triangles: list[list[float]]) -> None:
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


def attach_triangle_map_geometry_v2_unlit(scene, *, loader, render, triangles: list[dict]) -> None:
    """
    Attach v2-format triangle geometry without lightmap shader.
    """
    tris_by_mat: dict[str, list[dict]] = {}
    for t in triangles:
        m = t.get("m")
        if not isinstance(m, str):
            continue
        tris_by_mat.setdefault(m, []).append(t)

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

        tex: Texture | None = None
        tex_path = scene._resolve_material_texture_path(material_name=mat_name)
        if tex_path and tex_path.exists():
            tex = loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
            if tex is not None:
                tex.setWrapU(Texture.WM_repeat)
                tex.setWrapV(Texture.WM_repeat)
                if mat_name.startswith("{"):
                    tex.setMinfilter(Texture.FT_nearest)
                    tex.setMagfilter(Texture.FT_nearest)
                np.setTexture(tex, 1)
        else:
            tex = scene._make_debug_checker_texture()
            np.setTexture(tex, 1)


def attach_triangle_map_geometry_v2(scene, *, loader, render, triangles: list[dict]) -> None:
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
        # Imported BSP geometry should be lit by baked lighting, not by the game's ambient/sun lights.
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

        tex: Texture | None = None
        tex_path = scene._resolve_material_texture_path(material_name=mat_name)
        if tex_path and tex_path.exists():
            tex = loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
            if tex is not None:
                tex.setWrapU(Texture.WM_repeat)
                tex.setWrapV(Texture.WM_repeat)
                if mat_name.startswith("{"):
                    tex.setMinfilter(Texture.FT_nearest)
                    tex.setMagfilter(Texture.FT_nearest)
                np.setTexture(tex, 1)
        else:
            tex = scene._make_debug_checker_texture()
            np.setTexture(tex, 1)

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


def setup_skybox(scene, *, loader, camera, skyname: str) -> None:
    # Source convention: materials/skybox/<skyname><face>.vtf -> converted to PNG.
    if scene._skybox_np is not None:
        scene._skybox_np.removeNode()
        scene._skybox_np = None

    faces = {
        "ft": ("ft", (0, 200, 0), (180, 0, 0)),
        "bk": ("bk", (0, -200, 0), (0, 0, 0)),
        "lf": ("lf", (-200, 0, 0), (90, 0, 0)),
        "rt": ("rt", (200, 0, 0), (-90, 0, 0)),
        "up": ("up", (0, 0, 200), (180, -90, 0)),
        "dn": ("dn", (0, 0, -200), (180, 90, 0)),
    }

    if not scene._material_texture_root:
        return
    if scene._material_texture_index is None:
        scene._material_texture_index = scene._build_material_texture_index(scene._material_texture_root)

    def find_face(face_suffix: str) -> Path | None:
        candidates = [
            f"skybox/{skyname}{face_suffix}",
            f"skybox/{skyname.lower()}{face_suffix}",
            f"skybox/{skyname.upper()}{face_suffix}",
            f"skybox/{skyname.capitalize()}{face_suffix}",
        ]
        for c in candidates:
            p = scene._material_texture_index.get(c.casefold())
            if p:
                return p
        return None

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
        tex = loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
        if tex is not None:
            tex.setWrapU(Texture.WM_clamp)
            tex.setWrapV(Texture.WM_clamp)
            card.setTexture(tex, 1)

    scene._skybox_np = root

