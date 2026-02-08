from __future__ import annotations

from dataclasses import dataclass
import itertools

from panda3d.core import BitMask32, CollisionNode, CollisionSphere, LVector3f, NodePath, PointLight
from panda3d.core import LineSegs


_id_gen = itertools.count(1)


EDITOR_PICK_MASK = BitMask32.bit(3)


@dataclass
class EditorObject:
    id: int
    kind: str
    name: str
    root: NodePath

    # Optional typed payloads.
    light_np: NodePath | None = None
    marker_np: NodePath | None = None
    collide_np: NodePath | None = None

    intensity: float = 3.0
    color: tuple[float, float, float] = (1.0, 0.95, 0.85)
    radius: float = 6.0

    def pos(self, *, rel_to: NodePath) -> LVector3f:
        return self.root.getPos(rel_to)

    def set_pos(self, *, rel_to: NodePath, pos: LVector3f) -> None:
        self.root.setPos(rel_to, pos)


def _build_cross(*, size: float = 0.22) -> NodePath:
    ls = LineSegs("editor-cross")
    ls.setThickness(2.0)
    # X red
    ls.setColor(1.0, 0.25, 0.25, 1.0)
    ls.moveTo(-size, 0, 0)
    ls.drawTo(+size, 0, 0)
    # Y green
    ls.setColor(0.25, 1.0, 0.35, 1.0)
    ls.moveTo(0, -size, 0)
    ls.drawTo(0, +size, 0)
    # Z blue
    ls.setColor(0.35, 0.55, 1.0, 1.0)
    ls.moveTo(0, 0, -size)
    ls.drawTo(0, 0, +size)
    return NodePath(ls.create())


def create_point_light(
    *,
    parent: NodePath,
    name: str = "Point Light",
    pos: LVector3f,
    intensity: float = 3.0,
    color: tuple[float, float, float] = (1.0, 0.95, 0.85),
    radius: float = 6.0,
) -> EditorObject:
    obj_id = int(next(_id_gen))
    root = parent.attachNewNode(f"editor.obj.{obj_id}")
    root.setPos(pos)
    root.setPythonTag("editor_object_id", int(obj_id))

    # Visual marker.
    marker = _build_cross(size=0.22)
    marker.reparentTo(root)
    marker.setBin("fixed", 40)
    marker.setDepthTest(False)
    marker.setDepthWrite(False)

    # Collision for picking.
    cn = CollisionNode(f"editor.pick.{obj_id}")
    cn.addSolid(CollisionSphere(0, 0, 0, 0.35))
    cn.setIntoCollideMask(EDITOR_PICK_MASK)
    collide_np = root.attachNewNode(cn)
    collide_np.setPythonTag("editor_object_id", int(obj_id))

    # A real Panda light (for now, just for preview; radius is metadata for future baking).
    pl = PointLight(f"editor.light.{obj_id}")
    # Panda3D expects RGBA; intensity is applied as a multiplier.
    r, g, b = (float(color[0]), float(color[1]), float(color[2]))
    pl.setColor((r * float(intensity), g * float(intensity), b * float(intensity), 1.0))
    light_np = root.attachNewNode(pl)
    try:
        parent.setLight(light_np)
    except Exception:
        pass

    return EditorObject(
        id=obj_id,
        kind="point_light",
        name=str(name),
        root=root,
        light_np=light_np,
        marker_np=marker,
        collide_np=collide_np,
        intensity=float(intensity),
        color=(r, g, b),
        radius=float(radius),
    )


def update_point_light_preview(obj: EditorObject) -> None:
    if obj.kind != "point_light":
        return
    if obj.light_np is None:
        return
    try:
        light = obj.light_np.node()
    except Exception:
        return
    try:
        r, g, b = obj.color
        intensity = float(obj.intensity)
        light.setColor((float(r) * intensity, float(g) * intensity, float(b) * intensity, 1.0))
    except Exception:
        return
