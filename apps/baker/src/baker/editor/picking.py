from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser, NodePath


@dataclass(frozen=True)
class PickHit:
    nodepath: NodePath
    distance: float


class Picker:
    def __init__(self, *, base, camera_np: NodePath, root: NodePath, into_mask: BitMask32) -> None:
        self.base = base
        self.camera_np = camera_np
        self.root = root
        self.into_mask = into_mask

        self.trav = CollisionTraverser("baker.picker")
        self.queue = CollisionHandlerQueue()

        self.ray = CollisionRay()
        self.ray_node = CollisionNode("baker.picker.ray")
        self.ray_node.addSolid(self.ray)
        self.ray_node.setFromCollideMask(into_mask)
        self.ray_node.setIntoCollideMask(BitMask32.allOff())
        self.ray_np = self.camera_np.attachNewNode(self.ray_node)
        self.trav.addCollider(self.ray_np, self.queue)

    def destroy(self) -> None:
        try:
            self.ray_np.removeNode()
        except Exception:
            pass

    def pick(self, *, lens_x: float, lens_y: float) -> PickHit | None:
        """
        lens_x/lens_y are lens coordinates in [-1..1] relative to the camera's display region.
        """

        if getattr(self.base, "camNode", None) is None:
            return None
        try:
            self.ray.setFromLens(self.base.camNode, float(lens_x), float(lens_y))
        except Exception:
            return None

        self.queue.clearEntries()
        try:
            self.trav.traverse(self.root)
        except Exception:
            return None

        if self.queue.getNumEntries() <= 0:
            return None
        self.queue.sortEntries()
        ent = self.queue.getEntry(0)
        np = ent.getIntoNodePath()
        try:
            dist = float(ent.getDistance())
        except Exception:
            dist = 0.0
        return PickHit(nodepath=np, distance=dist)
