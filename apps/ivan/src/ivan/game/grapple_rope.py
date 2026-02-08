from __future__ import annotations

from panda3d.core import (
    Geom,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LVector3f,
    PNMImage,
    Texture,
)


def build_grapple_rope_texture() -> Texture:
    img = PNMImage(8, 128, 4)
    for y in range(128):
        t = 0.35 if (y // 6) % 2 == 0 else 0.55
        for x in range(8):
            shade = t * (0.85 if (x // 2) % 2 == 0 else 1.0)
            img.setXelA(x, y, shade, shade * 0.85, shade * 0.52, 0.95)
    tex = Texture("grapple-rope")
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMRepeat)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def update_grapple_rope_visual(host) -> None:
    host._grapple_rope_node.removeAllGeoms()
    if (
        host.player is None
        or host._mode != "game"
        or host._pause_menu_open
        or host._debug_menu_open
        or host._console_open
        or not host.player.is_grapple_attached()
    ):
        host._grapple_rope_np.hide()
        return

    anchor = host.player.grapple_anchor()
    if anchor is None:
        host._grapple_rope_np.hide()
        return
    end = LVector3f(host.player.pos)
    rope = end - anchor
    length = float(rope.length())
    if length <= 1e-4:
        host._grapple_rope_np.hide()
        return
    rope_dir = rope / length

    center = (anchor + end) * 0.5
    cam_pos = LVector3f(host.camera.getPos(host.render))
    to_cam = cam_pos - center
    side = rope_dir.cross(to_cam)
    if side.lengthSquared() <= 1e-10:
        side = rope_dir.cross(LVector3f(0.0, 0.0, 1.0))
    if side.lengthSquared() <= 1e-10:
        side = rope_dir.cross(LVector3f(1.0, 0.0, 0.0))
    side.normalize()
    half_w = max(0.002, float(host.tuning.grapple_rope_half_width))
    side *= half_w

    p0 = anchor + side
    p1 = anchor - side
    p2 = end - side
    p3 = end + side

    vrep = max(1.0, length * 2.2)
    vdata = GeomVertexData("grapple-rope", GeomVertexFormat.getV3t2(), Geom.UHDynamic)
    vdata.setNumRows(4)
    vw = GeomVertexWriter(vdata, "vertex")
    tw = GeomVertexWriter(vdata, "texcoord")
    for p, uv in ((p0, (0.0, 0.0)), (p1, (1.0, 0.0)), (p2, (1.0, vrep)), (p3, (0.0, vrep))):
        vw.addData3f(p.x, p.y, p.z)
        tw.addData2f(float(uv[0]), float(uv[1]))

    prim = GeomTriangles(Geom.UHStatic)
    prim.addVertices(0, 1, 2)
    prim.addVertices(0, 2, 3)
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    host._grapple_rope_node.addGeom(geom)
    host._grapple_rope_np.show()


__all__ = ["build_grapple_rope_texture", "update_grapple_rope_visual"]

