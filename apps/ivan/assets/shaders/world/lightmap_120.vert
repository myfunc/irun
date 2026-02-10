#version 120

uniform mat4 p3d_ModelViewProjectionMatrix;

attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec2 p3d_MultiTexCoord1;

varying vec2 v_uv0;
varying vec2 v_uv1;

void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  v_uv0 = p3d_MultiTexCoord0;
  v_uv1 = p3d_MultiTexCoord1;
}

