from __future__ import annotations

from dataclasses import dataclass

from direct.filter.FilterManager import FilterManager
from panda3d.core import Shader, Texture


_TONEMAP_SHADER_GLSL120 = {
    "vertex": r"""
#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 v_uv;
void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  v_uv = p3d_MultiTexCoord0;
}
""",
    "fragment": r"""
#version 120
uniform sampler2D src_tex;
uniform int tonemap_mode;  // 1=gamma-only, 2=Reinhard, 3=ACES approx
uniform float exposure;
uniform float gamma;
varying vec2 v_uv;

vec3 tonemap_reinhard(vec3 x) {
  return x / (vec3(1.0) + x);
}

// Narkowicz 2015-ish ACES approximation.
vec3 tonemap_aces_approx(vec3 x) {
  float a = 2.51;
  float b = 0.03;
  float c = 2.43;
  float d = 0.59;
  float e = 0.14;
  vec3 num = x * (a * x + vec3(b));
  vec3 den = x * (c * x + vec3(d)) + vec3(e);
  return clamp(num / den, 0.0, 1.0);
}

vec3 gamma_encode(vec3 x, float g) {
  // Avoid NaNs.
  x = max(x, vec3(0.0));
  return pow(x, vec3(1.0 / max(g, 1e-6)));
}

void main() {
  vec3 color = texture2D(src_tex, v_uv).rgb;
  color *= max(exposure, 0.0);

  if (tonemap_mode == 2) {
    color = tonemap_reinhard(color);
  } else if (tonemap_mode == 3) {
    color = tonemap_aces_approx(color);
  }

  // Mode 1 is "gamma-only"; modes 2/3 also gamma-encode for display.
  color = gamma_encode(color, gamma);
  gl_FragColor = vec4(color, 1.0);
}
""",
}


@dataclass
class TonemapSettings:
    mode: int = 1
    exposure: float = 1.0
    gamma: float = 2.2


class TonemapPass:
    """A tiny post-process pass for view transforms (preview-only).

    This keeps scene shading in (assumed) linear, applying tonemap/gamma only at presentation.
    """

    def __init__(self, *, base) -> None:
        self.base = base
        self.settings = TonemapSettings()

        self._mgr: FilterManager | None = None
        self._src_tex: Texture | None = None
        self._quad = None
        self._shader: Shader | None = None

    def attach(self) -> None:
        if self.base.win is None:
            return
        if self.base.cam is None:
            return

        self._mgr = FilterManager(self.base.win, self.base.cam)
        self._src_tex = Texture()
        self._quad = self._mgr.renderSceneInto(colortex=self._src_tex)

        self._shader = Shader.make(
            Shader.SL_GLSL,
            vertex=_TONEMAP_SHADER_GLSL120["vertex"],
            fragment=_TONEMAP_SHADER_GLSL120["fragment"],
        )

        self._quad.setShader(self._shader)
        self._quad.setShaderInput("src_tex", self._src_tex)
        self._apply_inputs()

    def _apply_inputs(self) -> None:
        if self._quad is None:
            return
        self._quad.setShaderInput("tonemap_mode", int(self.settings.mode))
        self._quad.setShaderInput("exposure", float(self.settings.exposure))
        self._quad.setShaderInput("gamma", float(self.settings.gamma))

    def set_mode(self, mode: int) -> None:
        mode = int(mode)
        if mode not in (1, 2, 3):
            return
        self.settings.mode = mode
        self._apply_inputs()
