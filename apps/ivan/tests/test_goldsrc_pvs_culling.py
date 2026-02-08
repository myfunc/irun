from __future__ import annotations


class _StubNode:
    def __init__(self) -> None:
        self.visible = True

    def show(self, *args) -> None:
        assert args == ()
        self.visible = True

    def hide(self, *args) -> None:
        assert args == ()
        self.visible = False


class _StubCamera:
    def __init__(self) -> None:
        self.pos = (-1.0, 0.0, 0.0)

    def getPos(self, _other):
        from panda3d.core import LVector3f

        return LVector3f(*self.pos)


class _StubVis:
    world_first_face = 100
    world_num_faces = 3
    leaves = [
        (-1, 0, 0),  # no VIS
        (0, 0, 0),  # has VIS
    ]

    @property
    def world_face_end(self) -> int:
        return int(self.world_first_face + self.world_num_faces)

    def point_leaf(self, *, x: float, y: float, z: float) -> int:
        return 0 if x < 0.0 else 1

    def visible_world_face_flags_for_leaf(self, leaf_idx: int) -> bytearray:
        # Leaf 0 would normally be "all visible" (no VIS), leaf 1 culls face 100.
        if int(leaf_idx) == 1:
            return bytearray([0, 1, 1])
        return bytearray([1, 1, 1])


def test_pvs_culling_show_hide_unmasked_and_default_off() -> None:
    from ivan.world.scene import WorldScene

    scene = WorldScene()
    scene._vis_goldsrc = _StubVis()  # type: ignore[assignment]
    scene._map_scale = 1.0
    scene._world_root_np = object()
    cam = _StubCamera()
    scene._camera_np = cam

    n0 = _StubNode()
    n1 = _StubNode()
    n2 = _StubNode()
    scene._vis_face_nodes = {100: [n0], 101: [n1], 102: [n2]}

    # Default OFF: tick should not change visibility.
    cam.pos = (1.0, 0.0, 0.0)
    scene.tick(now=0.0)
    assert n0.visible is True
    assert n1.visible is True
    assert n2.visible is True

    # Enable: culling applies (face 100 hidden on leaf 1).
    scene.set_visibility_enabled(True)
    # Allow state to apply (direct call in setter).
    assert n0.visible is False
    assert n1.visible is True
    assert n2.visible is True
