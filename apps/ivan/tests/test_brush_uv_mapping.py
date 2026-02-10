from __future__ import annotations

from ivan.maps.brush_geometry import _compute_uv
from ivan.maps.map_parser import BrushFace, Vec3


def _face_for_uv(*, sx: float = 1.0, sy: float = 1.0) -> BrushFace:
    return BrushFace(
        plane_points=(
            Vec3(0.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 1.0, 0.0),
        ),
        texture="TEST",
        u_axis=Vec3(1.0, 0.0, 0.0),
        u_offset=16.0,
        v_axis=Vec3(0.0, 1.0, 0.0),
        v_offset=8.0,
        rotation=0.0,
        scale_x=float(sx),
        scale_y=float(sy),
    )


def test_compute_uv_offset_is_not_scaled_by_texture_scale() -> None:
    face = _face_for_uv(sx=2.0, sy=4.0)
    # Expected Valve 220:
    # u = ((x / scale_x) + u_offset) / tex_w
    # v = -((y / scale_y) + v_offset) / tex_h
    u, v = _compute_uv((32.0, 32.0, 0.0), face, 64, 64)
    assert u == 0.5
    assert v == -0.25


def test_compute_uv_matches_simple_unscaled_case() -> None:
    face = _face_for_uv(sx=1.0, sy=1.0)
    u, v = _compute_uv((16.0, 24.0, 0.0), face, 64, 64)
    assert u == 0.5
    assert v == -0.5
