from __future__ import annotations

from panda3d.bullet import (
    BulletBoxShape,
    BulletCapsuleShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, LVector3f, Point3, TransformState

from ivan.common.aabb import AABB


class CollisionWorld:
    """Bullet world used for collision queries (convex sweeps) + static scene bodies."""

    def __init__(
        self,
        *,
        aabbs: list[AABB],
        triangles: list[list[float]] | None,
        triangle_collision_mode: bool,
        player_radius: float,
        player_half_height: float,
        render,
    ) -> None:
        self._bworld = BulletWorld()
        # We integrate gravity ourselves (Quake-style tuning), so keep Bullet gravity neutral.
        self._bworld.setGravity(LVector3f(0, 0, 0))

        self._static_bodies: list[BulletRigidBodyNode] = []
        self._graybox_nodes: list[object] = []
        self._player_sweep_shape = None
        self.update_player_sweep_shape(player_radius=player_radius, player_half_height=player_half_height)

        if triangle_collision_mode and triangles:
            tri_mesh = BulletTriangleMesh()
            for tri in triangles:
                if len(tri) != 9:
                    continue
                p0 = Point3(float(tri[0]), float(tri[1]), float(tri[2]))
                p1 = Point3(float(tri[3]), float(tri[4]), float(tri[5]))
                p2 = Point3(float(tri[6]), float(tri[7]), float(tri[8]))
                tri_mesh.addTriangle(p0, p1, p2, False)

            shape = BulletTriangleMeshShape(tri_mesh, dynamic=False)
            body = BulletRigidBodyNode("static-triangle-mesh")
            body.setMass(0.0)
            body.addShape(shape)
            render.attachNewNode(body)
            self._bworld.attachRigidBody(body)
            self._static_bodies.append(body)
            return

        # Graybox fallback: build static boxes for the blocks we placed.
        for box in aabbs:
            half = (box.maximum - box.minimum) * 0.5
            center = box.minimum + half
            shape = BulletBoxShape(LVector3f(float(half.x), float(half.y), float(half.z)))
            body = BulletRigidBodyNode("graybox-block")
            body.setMass(0.0)
            body.addShape(shape)
            np = render.attachNewNode(body)
            np.setPos(float(center.x), float(center.y), float(center.z))
            self._bworld.attachRigidBody(body)
            self._static_bodies.append(body)
            self._graybox_nodes.append(np)

    def update_player_sweep_shape(self, *, player_radius: float, player_half_height: float) -> None:
        radius = float(player_radius)
        # Bullet capsule height is cylinder height (excluding hemispherical caps).
        cyl_h = max(0.01, float(player_half_height * 2.0 - radius * 2.0))
        self._player_sweep_shape = BulletCapsuleShape(radius, cyl_h, 2)

    def sweep_closest(self, from_pos: LVector3f, to_pos: LVector3f):
        assert self._player_sweep_shape is not None
        return self._bworld.sweepTestClosest(
            self._player_sweep_shape,
            TransformState.makePos(from_pos),
            TransformState.makePos(to_pos),
            BitMask32.allOn(),
            0.0,
        )

    def ray_closest(self, from_pos: LVector3f, to_pos: LVector3f):
        return self._bworld.rayTestClosest(from_pos, to_pos, BitMask32.allOn())

    def update_graybox_block(self, *, index: int, box: AABB) -> None:
        """Update transform for a graybox static body (used by feel-harness moving platform)."""

        i = int(index)
        if i < 0 or i >= len(self._graybox_nodes):
            return
        half = (box.maximum - box.minimum) * 0.5
        center = box.minimum + half
        try:
            self._graybox_nodes[i].setPos(float(center.x), float(center.y), float(center.z))
        except Exception:
            return
