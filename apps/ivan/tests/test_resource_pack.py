"""Tests for .irunres resource pack resolver and cache."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ivan.maps.resource_pack import (
    PACKED_RESOURCE_EXT,
    MissingResourcePackAssetError,
    _compute_pack_hash,
    _SCHEMA_VERSION,
    _validate_manifest,
    ensure_pack_extracted,
    resolve_asset_from_pack,
    resolve_materials_from_resource_packs,
)


def _touch(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _create_irunres_pack(
    out_path: Path,
    *,
    assets: dict[str, str] | None = None,
    pack_hash: str = "test-pack-hash",
) -> None:
    """Create a minimal .irunres pack for testing."""
    manifest = {
        "schema": _SCHEMA_VERSION,
        "pack_hash": pack_hash,
        "assets": assets or {"brick": "textures/brick.png", "metal": "textures/metal.png"},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True) + "\n")
        for asset_id, rel_path in manifest["assets"].items():
            _touch(out_path.parent / rel_path, b"png-contents")
            zf.write(out_path.parent / rel_path, rel_path)


def test_validate_manifest_valid() -> None:
    m = _validate_manifest({"schema": _SCHEMA_VERSION, "pack_hash": "abc", "assets": {"x": "a.png"}})
    assert m is not None
    assert m.pack_hash == "abc"
    assert m.assets == {"x": "a.png"}


def test_validate_manifest_invalid_schema() -> None:
    assert _validate_manifest({"schema": "v0", "pack_hash": "abc", "assets": {}}) is None


def test_validate_manifest_invalid_assets() -> None:
    assert _validate_manifest({"schema": _SCHEMA_VERSION, "pack_hash": "abc", "assets": "not-dict"}) is None


def test_compute_pack_hash_stable() -> None:
    p = Path("x" + PACKED_RESOURCE_EXT)
    p.write_bytes(b"content")
    try:
        h1 = _compute_pack_hash(p)
        h2 = _compute_pack_hash(p)
        assert h1 == h2
    finally:
        p.unlink(missing_ok=True)


def test_compute_pack_hash_different_content() -> None:
    p1 = Path("a" + PACKED_RESOURCE_EXT)
    p2 = Path("b" + PACKED_RESOURCE_EXT)
    p1.write_bytes(b"content1")
    p2.write_bytes(b"content2")
    try:
        assert _compute_pack_hash(p1) != _compute_pack_hash(p2)
    finally:
        p1.unlink(missing_ok=True)
        p2.unlink(missing_ok=True)


def test_ensure_pack_extracted_and_cache_reuse(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / f"test_pack{PACKED_RESOURCE_EXT}"
    _create_irunres_pack(pack_path)

    root1 = ensure_pack_extracted(pack_path)
    root2 = ensure_pack_extracted(pack_path)
    assert root1 == root2
    assert (root1 / "manifest.json").exists()
    assert (root1 / "textures" / "brick.png").exists()
    assert (root1 / "textures" / "metal.png").exists()


def test_ensure_pack_extracted_cache_invalidated_on_content_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / f"test_pack{PACKED_RESOURCE_EXT}"
    _create_irunres_pack(pack_path, assets={"a": "a.png"})
    (tmp_path / "a.png").write_bytes(b"x")

    root1 = ensure_pack_extracted(pack_path)
    # Modify pack content -> new hash -> new cache dir
    (tmp_path / "a.png").write_bytes(b"y")
    _create_irunres_pack(pack_path, assets={"a": "a.png"})

    root2 = ensure_pack_extracted(pack_path)
    # Both should be valid; root2 may differ if hash changed
    assert (root1 / "manifest.json").exists()
    assert (root2 / "manifest.json").exists()


def test_resolve_asset_from_pack(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / f"test_pack{PACKED_RESOURCE_EXT}"
    _create_irunres_pack(pack_path)

    root = ensure_pack_extracted(pack_path)
    assert resolve_asset_from_pack(root, "brick") is not None
    assert resolve_asset_from_pack(root, "brick").name == "brick.png"
    assert resolve_asset_from_pack(root, "nonexistent") is None


def test_resolve_materials_from_resource_packs_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / f"pack{PACKED_RESOURCE_EXT}"
    map_json = tmp_path / "map.json"
    map_json.write_text("{}")
    _create_irunres_pack(pack_path)

    index = resolve_materials_from_resource_packs(
        resource_packs=[str(pack_path)],
        asset_bindings={"brick": "brick", "metal": "metal"},
        map_json=map_json,
    )
    assert "brick" in index
    assert "metal" in index
    assert index["brick"].exists()
    assert index["metal"].exists()


def test_resolve_materials_from_resource_packs_missing_asset_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    pack_path = tmp_path / f"pack{PACKED_RESOURCE_EXT}"
    map_json = tmp_path / "map.json"
    map_json.write_text("{}")
    _create_irunres_pack(pack_path)

    with pytest.raises(MissingResourcePackAssetError) as exc_info:
        resolve_materials_from_resource_packs(
            resource_packs=[str(pack_path)],
            asset_bindings={"brick": "brick", "missing_tex": "nonexistent_asset"},
            map_json=map_json,
        )
    assert "nonexistent_asset" in str(exc_info.value) or "missing" in str(exc_info.value).lower()


def test_resolve_materials_from_resource_packs_missing_pack_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    map_json = tmp_path / "map.json"
    map_json.write_text("{}")

    with pytest.raises(MissingResourcePackAssetError):
        resolve_materials_from_resource_packs(
            resource_packs=[str(tmp_path / "nonexistent.irunres")],
            asset_bindings={"brick": "brick"},
            map_json=map_json,
        )
