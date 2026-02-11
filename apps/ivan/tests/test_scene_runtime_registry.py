from __future__ import annotations

from types import SimpleNamespace

from ivan.console.scene_runtime import SceneRuntimeRegistry


class _Vec3:
    def __init__(self, x=0.0, y=0.0, z=0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, other):
        return _Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return _Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scale):
        return _Vec3(self.x * float(scale), self.y * float(scale), self.z * float(scale))

    def lengthSquared(self) -> float:
        return float(self.x * self.x + self.y * self.y + self.z * self.z)


class _PathCollection:
    def __init__(self, items):
        self._items = list(items)

    def getNumPaths(self) -> int:
        return len(self._items)

    def getPath(self, i: int):
        return self._items[i]


class _TagCollection:
    def __init__(self, tags):
        self._tags = list(tags)

    def getNumTags(self) -> int:
        return len(self._tags)

    def getTag(self, i: int):
        return self._tags[i]


class _Node:
    _next = 10

    def __init__(self, name: str, parent=None) -> None:
        self._name = str(name)
        self._parent = parent
        self._children = []
        self._removed = False
        self._key = _Node._next
        _Node._next += 1
        self._pos = _Vec3(0.0, 0.0, 0.0)
        self._hpr = _Vec3(0.0, 0.0, 0.0)
        self._scale = _Vec3(1.0, 1.0, 1.0)
        self._tags = {}
        if parent is not None:
            parent._children.append(self)

    def getKey(self):
        return self._key

    def getName(self):
        return self._name

    def setName(self, name: str):
        self._name = str(name)

    def node(self):
        return self

    def getParent(self):
        if self._parent is None:
            return SimpleNamespace(isEmpty=lambda: True, getName=lambda: "")
        return self._parent

    def isEmpty(self):
        return False

    def getChildren(self):
        return _PathCollection(self._children)

    def attachNewNode(self, name: str):
        return _Node(name, parent=self)

    def reparentTo(self, parent):
        self.wrtReparentTo(parent)

    def wrtReparentTo(self, parent):
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)
        self._parent = parent
        parent._children.append(self)

    def removeNode(self):
        self._removed = True
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)
        self._parent = None

    def setPos(self, *args):
        if len(args) == 4:
            _, x, y, z = args
        else:
            x, y, z = args
        self._pos = _Vec3(x, y, z)

    def getPos(self):
        return _Vec3(self._pos.x, self._pos.y, self._pos.z)

    def setHpr(self, *args):
        if len(args) == 4:
            _, h, p, r = args
        else:
            h, p, r = args
        self._hpr = _Vec3(h, p, r)

    def getHpr(self):
        return _Vec3(self._hpr.x, self._hpr.y, self._hpr.z)

    def setScale(self, x, y=None, z=None):
        if y is None or z is None:
            y = x
            z = x
        self._scale = _Vec3(x, y, z)

    def getScale(self):
        return _Vec3(self._scale.x, self._scale.y, self._scale.z)

    def setTag(self, key: str, value: str) -> None:
        self._tags[str(key)] = str(value)

    def getTagKeys(self):
        return _TagCollection(list(self._tags.keys()))

    def getTag(self, key: str):
        return self._tags.get(str(key), "")


class _Loader:
    def loadModel(self, _name: str):
        return _Node("loaded-model")


def test_scene_runtime_list_select_transform_group_and_delete() -> None:
    root = _Node("world-root")
    a = _Node("crate_a", parent=root)
    b = _Node("crate_b", parent=root)
    a.setTag("editable", "1")
    runner = SimpleNamespace(world_root=root, loader=_Loader())
    runtime = SceneRuntimeRegistry(runner=runner)

    listed = runtime.list_objects(name="crate", page=1, page_size=10)
    assert listed["total"] >= 2

    sel = runtime.select_object(target=str(a.getKey()))
    assert str(sel["id"]) == str(a.getKey())

    moved = runtime.transform_object(target=str(a.getKey()), mode="move", x=1.0, y=2.0, z=3.0, relative=False)
    assert moved["pos"] == [1.0, 2.0, 3.0]

    grouped = runtime.group_objects(group_id="g1", targets=[str(a.getKey()), str(b.getKey())])
    assert grouped["moved"] == 2
    gm = runtime.group_transform(group_id="g1", mode="move", x=5.0, y=0.0, z=0.0, relative=False)
    assert gm["group_id"] == "g1"

    ungrouped = runtime.ungroup(group_id="g1")
    assert ungrouped["moved"] == 2

    deleted = runtime.delete_object(target=str(a.getKey()))
    assert str(deleted["deleted_id"]) == str(a.getKey())


def test_scene_runtime_player_look_target_reports_hit() -> None:
    class _Hit:
        def hasHit(self):
            return True

        def getHitPos(self):
            return _Vec3(0.0, 2.0, 0.0)

        def getHitFraction(self):
            return 0.5

        def getNode(self):
            return SimpleNamespace(getName=lambda: "hit-node")

    class _Collision:
        def ray_closest(self, _a, _b):
            return _Hit()

    camera = SimpleNamespace(getPos=lambda _render: _Vec3(0.0, 0.0, 0.0))
    runner = SimpleNamespace(
        world_root=_Node("world-root"),
        collision=_Collision(),
        camera=camera,
        render=object(),
        _view_direction=lambda: _Vec3(0.0, 1.0, 0.0),
    )
    runtime = SceneRuntimeRegistry(runner=runner)
    hit = runtime.player_look_target(distance=10.0)
    assert hit["hit"] is True
    assert hit["hit_node"] == "hit-node"

