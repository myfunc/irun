from __future__ import annotations

from ivan.course.volumes import (
    CylinderVolume,
    cylinder_centered,
    cylinder_from_json,
    cylinder_to_json,
)


def test_cylinder_contains_point_checks_radius_and_height() -> None:
    vol = cylinder_centered(cx=10.0, cy=-2.0, cz=3.0, radius=2.5, half_z=1.5)
    assert vol.contains_point(x=10.0, y=-2.0, z=3.0)
    assert vol.contains_point(x=12.5, y=-2.0, z=3.0)
    assert vol.contains_point(x=10.0, y=-2.0, z=4.5)

    assert not vol.contains_point(x=12.6, y=-2.0, z=3.0)
    assert not vol.contains_point(x=10.0, y=-2.0, z=4.6)


def test_cylinder_json_roundtrip_and_validation() -> None:
    src = CylinderVolume(center_xyz=(1.0, 2.0, 3.0), radius=4.0, half_z=5.0)
    payload = cylinder_to_json(src)
    out = cylinder_from_json(payload)
    assert out == src

    assert cylinder_from_json({"center": [0, 0], "radius": 1.0, "half_z": 1.0}) is None
    assert cylinder_from_json({"center": [0, 0, 0], "radius": "x", "half_z": 1.0}) is None
