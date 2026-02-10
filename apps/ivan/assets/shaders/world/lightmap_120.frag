#version 120

uniform sampler2D base_tex;
uniform sampler2D lm_tex0;
uniform sampler2D lm_tex1;
uniform sampler2D lm_tex2;
uniform sampler2D lm_tex3;
uniform vec4 lm_scales;
uniform int alpha_test;

varying vec2 v_uv0;
varying vec2 v_uv1;

void main() {
  vec4 base = texture2D(base_tex, v_uv0);
  if (alpha_test != 0 && base.a < 0.5) discard;

  float lm_w = lm_scales.x + lm_scales.y + lm_scales.z + lm_scales.w;
  vec3 lm = vec3(0.0);
  lm += lm_scales.x * texture2D(lm_tex0, v_uv1).rgb;
  lm += lm_scales.y * texture2D(lm_tex1, v_uv1).rgb;
  lm += lm_scales.z * texture2D(lm_tex2, v_uv1).rgb;
  lm += lm_scales.w * texture2D(lm_tex3, v_uv1).rgb;

  // Fallback for malformed lightstyle metadata: avoid full-black faces.
  if (lm_w <= 0.0001) {
    lm = vec3(1.0);
  }

  gl_FragColor = vec4(base.rgb * lm, base.a);
}

