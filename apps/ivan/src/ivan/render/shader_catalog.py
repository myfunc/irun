from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from panda3d.core import Filename, Shader

from ivan.paths import app_root as ivan_app_root

# Stable shader ids used by runtime code.
SHADER_WORLD_LIGHTMAP_GLSL120 = "world.lightmap.glsl120"


@dataclass(frozen=True)
class ShaderProgramDef:
    shader_id: str
    vertex_relpath: Path
    fragment_relpath: Path
    description: str


_SHADERS: dict[str, ShaderProgramDef] = {
    SHADER_WORLD_LIGHTMAP_GLSL120: ShaderProgramDef(
        shader_id=SHADER_WORLD_LIGHTMAP_GLSL120,
        vertex_relpath=Path("world/lightmap_120.vert"),
        fragment_relpath=Path("world/lightmap_120.frag"),
        description="Baked lightmap shader for world geometry (GLSL 1.20).",
    ),
}

_CACHE: dict[str, Shader] = {}


def shaders_root() -> Path:
    """Return the canonical repository path where GLSL files live."""
    return ivan_app_root() / "assets" / "shaders"


def shader_catalog() -> dict[str, ShaderProgramDef]:
    """Return a copy of the shader registry."""
    return dict(_SHADERS)


def load_shader(shader_id: str) -> Shader:
    """
    Load a shader from the centralized shader catalog.

    The result is cached by `shader_id` to avoid repeated disk reads.
    """
    cached = _CACHE.get(shader_id)
    if isinstance(cached, Shader):
        return cached

    spec = _SHADERS.get(shader_id)
    if spec is None:
        raise ValueError(f"Unknown shader id: {shader_id}")

    root = shaders_root()
    vert = (root / spec.vertex_relpath).resolve()
    frag = (root / spec.fragment_relpath).resolve()
    if not vert.is_file():
        raise FileNotFoundError(f"Vertex shader not found: {vert}")
    if not frag.is_file():
        raise FileNotFoundError(f"Fragment shader not found: {frag}")

    shader = Shader.load(
        Shader.SL_GLSL,
        Filename.fromOsSpecific(str(vert)),
        Filename.fromOsSpecific(str(frag)),
    )
    _CACHE[shader_id] = shader
    return shader

