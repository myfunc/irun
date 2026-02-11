from __future__ import annotations

from panda3d.core import (
    Geom,
    GeomVertexArrayFormat,
    GeomVertexFormat,
    InternalName,
    PNMImage,
    Shader,
    Texture,
)

from ivan.render.shader_catalog import SHADER_WORLD_LIGHTMAP_GLSL120, load_shader


def vformat_v3n3c4t2t2() -> GeomVertexFormat:
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
    arr.addColumn(InternalName.getNormal(), 3, Geom.NT_float32, Geom.C_normal)
    arr.addColumn(InternalName.getColor(), 4, Geom.NT_float32, Geom.C_color)
    arr.addColumn(InternalName.getTexcoord(), 2, Geom.NT_float32, Geom.C_texcoord)
    arr.addColumn(InternalName.getTexcoordName("1"), 2, Geom.NT_float32, Geom.C_texcoord)
    fmt = GeomVertexFormat()
    fmt.addArray(arr)
    return GeomVertexFormat.registerFormat(fmt)


def make_solid_texture(*, name: str, rgba: tuple[float, float, float, float]) -> Texture:
    img = PNMImage(1, 1)
    img.setXelA(0, 0, float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    tex = Texture(name)
    tex.load(img)
    tex.setWrapU(Texture.WM_clamp)
    tex.setWrapV(Texture.WM_clamp)
    tex.setMinfilter(Texture.FT_nearest)
    tex.setMagfilter(Texture.FT_nearest)
    return tex


def make_debug_checker_texture() -> Texture:
    img = PNMImage(256, 256)
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


def world_lightmap_shader() -> Shader:
    return load_shader(SHADER_WORLD_LIGHTMAP_GLSL120)

