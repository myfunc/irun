from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ivan.world.scene_layers.lighting import apply_fog
from ivan.world.scene_layers import lighting as lighting_layer
from ivan.world.scene_layers.loading import _apply_skybox_baseline, _resolve_entry_kind


class _FogRenderStub:
    def __init__(self) -> None:
        self.fog_node = None
        self.fog_cleared = False

    def attachNewNode(self, node):  # noqa: N802 - Panda naming parity
        return node

    def setFog(self, node):  # noqa: N802 - Panda naming parity
        self.fog_node = node
        self.fog_cleared = False

    def clearFog(self):  # noqa: N802 - Panda naming parity
        self.fog_node = None
        self.fog_cleared = True


class _SceneFogStub:
    def __init__(self, map_payload: dict | None) -> None:
        self._map_payload = map_payload
        self._fog_source = "unset"
        self._fog_enabled = False
        self._fog_range = (0.0, 0.0)
        self._fog_color = (0.0, 0.0, 0.0)


def test_apply_fog_map_override_beats_run_profile() -> None:
    scene = _SceneFogStub(
        map_payload={
            "fog": {
                "enabled": True,
                "start": 12.0,
                "end": 34.0,
                "color": [0.1, 0.2, 0.3],
            }
        }
    )
    cfg = SimpleNamespace(fog={"enabled": False, "start": 999.0, "end": 1000.0})
    render = _FogRenderStub()

    apply_fog(scene, cfg=cfg, render=render)

    assert scene._fog_source == "map-override"
    assert scene._fog_enabled is True
    assert scene._fog_range == (12.0, 34.0)
    assert scene._fog_color == (0.1, 0.2, 0.3)
    assert render.fog_node is not None


def test_apply_fog_uses_engine_default_when_unset() -> None:
    scene = _SceneFogStub(map_payload={})
    cfg = SimpleNamespace(fog=None)
    render = _FogRenderStub()

    apply_fog(scene, cfg=cfg, render=render)

    assert scene._fog_source == "engine-default"
    assert scene._fog_enabled is True
    assert scene._fog_range == (40.0, 220.0)
    assert render.fog_node is not None


class _SceneSkyStub:
    def __init__(self) -> None:
        self._active_skyname = ""
        self._sky_source = "unset"
        self.calls: list[tuple[str, str | None]] = []

    def _setup_skybox(self, *, loader, camera, skyname: str, fallback_skyname: str | None = None):
        self.calls.append((skyname, fallback_skyname))
        return ("default_horizon", "default-preset")


def test_apply_skybox_baseline_falls_back_to_default_preset() -> None:
    scene = _SceneSkyStub()
    _apply_skybox_baseline(scene, loader=None, camera=None, map_skyname=None)

    assert scene.calls == [("default_horizon", "default_horizon")]
    assert scene._active_skyname == "default_horizon"
    assert scene._sky_source == "default-preset"


def test_resolve_entry_kind_detects_packed_irunmap_cache(tmp_path: Path) -> None:
    cached = tmp_path / "cache"
    cached.mkdir(parents=True, exist_ok=True)
    (cached / "map.json").write_text("{}", encoding="utf-8")
    (cached / ".irunmap-extracted.json").write_text("{}", encoding="utf-8")

    assert _resolve_entry_kind(cached / "map.json") == "packed-irunmap"


class _NodeStub:
    def __init__(self, node_obj) -> None:
        self.node_obj = node_obj
        self.pos = (0.0, 0.0, 0.0)
        self.hpr = (0.0, 0.0, 0.0)

    def setPos(self, x, y=None, z=None):  # noqa: N802 - Panda naming parity
        if y is None and z is None and hasattr(x, "__iter__"):
            vals = list(x)
            self.pos = (float(vals[0]), float(vals[1]), float(vals[2]))
            return
        self.pos = (float(x), float(y), float(z))

    def setHpr(self, h, p, r):  # noqa: N802 - Panda naming parity
        self.hpr = (float(h), float(p), float(r))

    def node(self):
        return self.node_obj


class _RenderLightStub:
    def __init__(self) -> None:
        self.nodes: list[_NodeStub] = []
        self.lights: list[_NodeStub] = []

    def attachNewNode(self, node_obj):  # noqa: N802 - Panda naming parity
        n = _NodeStub(node_obj)
        self.nodes.append(n)
        return n

    def setLight(self, node):  # noqa: N802 - Panda naming parity
        self.lights.append(node)


def test_light_spot_uses_spotlight_runtime_path(monkeypatch) -> None:
    class _LensStub:
        def __init__(self) -> None:
            self.fov = 0.0

        def setFov(self, v):  # noqa: N802
            self.fov = float(v)

    class _SpotStub:
        def __init__(self, _name: str) -> None:
            self.lens = None

        def setColor(self, _c):  # noqa: N802
            return None

        def setLens(self, lens):  # noqa: N802
            self.lens = lens

        def setAttenuation(self, _a):  # noqa: N802
            return None

    monkeypatch.setattr(lighting_layer, "PerspectiveLens", _LensStub)
    monkeypatch.setattr(lighting_layer, "Spotlight", _SpotStub)

    render = _RenderLightStub()
    scene = SimpleNamespace(_ambient_np=None, _sun_np=None, spawn_point=None)
    light_spot = SimpleNamespace(
        classname="light_spot",
        color=(1.0, 0.8, 0.6),
        brightness=255.0,
        fade=1.0,
        origin=(1.0, 2.0, 3.0),
        angles=(0.0, 45.0, 0.0),
        pitch=-20.0,
        outer_cone=30.0,
    )

    lighting_layer.enhance_map_file_lighting(scene, render=render, lights=[light_spot])

    assert len(render.lights) == 1
    node = render.lights[0]
    assert isinstance(node.node_obj, _SpotStub)
    assert isinstance(node.node_obj.lens, _LensStub)
    assert node.node_obj.lens.fov == 60.0
    assert node.hpr == (45.0, -20.0, 0.0)

