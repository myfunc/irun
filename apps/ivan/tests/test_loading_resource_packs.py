"""Tests for map loading with resource_packs and asset_bindings."""

from __future__ import annotations

import json
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from ivan.maps.resource_pack import _SCHEMA_VERSION
from ivan.world.scene_layers.loading import try_load_external_map


def _create_irunres_pack(out_path: Path, assets: dict[str, str]) -> None:
    manifest = {"schema": _SCHEMA_VERSION, "pack_hash": "test", "assets": assets}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True) + "\n")
        for asset_id, rel_path in assets.items():
            p = out_path.parent / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
            zf.write(p, rel_path)


def _make_scene_stub(*, use_real_resolve_material_root=False):
    """Minimal scene stub for loading tests."""
    from ivan.world.scene import WorldScene

    stub = SimpleNamespace()
    stub._map_convert_report = {}
    stub._resolve_map_bundle_path = lambda p: p if p.exists() else None
    stub._resolve_material_root = (
        (lambda **kw: WorldScene._resolve_material_root(**kw)) if use_real_resolve_material_root else (lambda **kw: None)
    )
    stub._resolve_lightmaps = lambda **kw: None
    stub._lights_from_payload = lambda **kw: []
    stub._resolve_lightstyles = lambda **kw: ({}, "legacy")
    stub._resolve_visibility = lambda **kw: None
    stub._attach_triangle_map_geometry_v2_unlit = lambda **kw: None
    stub._attach_triangle_map_geometry_v2 = lambda **kw: None
    stub._attach_triangle_map_geometry = lambda **kw: None
    stub._setup_skybox = lambda **kw: ("default_horizon", "default-preset")
    stub._enhance_map_file_lighting = lambda **kw: None
    stub._time_load_stage = lambda name: nullcontext()
    return stub


def test_load_map_with_resource_packs_success(tmp_path: Path, monkeypatch) -> None:
    """Map with valid resource_packs and asset_bindings loads successfully."""
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / "pack.irunres"
    _create_irunres_pack(pack_path, {"brick": "textures/brick.png"})
    (tmp_path / "textures" / "brick.png").touch()

    map_json = tmp_path / "map.json"
    payload = {
        "map_id": "test",
        "triangles": [{"m": "brick", "p": [0, 0, 0, 1, 0, 0, 0, 1, 0], "n": [0, 0, 1] * 3, "uv": [0, 0, 1, 0, 0, 1], "c": [1] * 12, "lm": [0] * 6}],
        "resource_packs": [str(pack_path)],
        "asset_bindings": {"brick": "brick"},
    }
    map_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scene = _make_scene_stub()
    cfg = SimpleNamespace(map_profile="dev-fast", lighting=None)
    ok = try_load_external_map(scene, cfg=cfg, map_json=map_json, loader=None, render=None, camera=None)
    assert ok
    assert scene._material_texture_index is not None
    assert "brick" in scene._material_texture_index


def test_load_map_with_resource_packs_missing_asset_fails(tmp_path: Path, monkeypatch) -> None:
    """Map with resource_packs but missing asset fails clearly."""
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / "pack.irunres"
    _create_irunres_pack(pack_path, {"brick": "textures/brick.png"})

    map_json = tmp_path / "map.json"
    payload = {
        "map_id": "test",
        "triangles": [{"m": "missing_tex", "p": [0, 0, 0, 1, 0, 0, 0, 1, 0], "n": [0, 0, 1] * 3, "uv": [0, 0, 1, 0, 0, 1], "c": [1] * 12, "lm": [0] * 6}],
        "resource_packs": [str(pack_path)],
        "asset_bindings": {"missing_tex": "nonexistent_asset"},
    }
    map_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scene = _make_scene_stub()
    cfg = SimpleNamespace(map_profile="dev-fast", lighting=None)
    ok = try_load_external_map(scene, cfg=cfg, map_json=map_json, loader=None, render=None, camera=None)
    assert not ok


def test_load_map_without_resource_packs_uses_material_root(tmp_path: Path) -> None:
    """Map without resource_packs uses materials.converted_root (backward compat)."""
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir(parents=True)
    (materials_dir / "brick.png").write_bytes(b"x")

    map_json = tmp_path / "map.json"
    payload = {
        "map_id": "test",
        "triangles": [{"m": "brick", "p": [0, 0, 0, 1, 0, 0, 0, 1, 0], "n": [0, 0, 1] * 3, "uv": [0, 0, 1, 0, 0, 1], "c": [1] * 12, "lm": [0] * 6}],
        "materials": {"converted_root": "materials"},
    }
    map_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    scene = _make_scene_stub(use_real_resolve_material_root=True)
    cfg = SimpleNamespace(map_profile="dev-fast", lighting=None)
    ok = try_load_external_map(scene, cfg=cfg, map_json=map_json, loader=None, render=None, camera=None)
    assert ok
    assert scene._material_texture_root is not None
    assert scene._material_texture_root.name == "materials"
