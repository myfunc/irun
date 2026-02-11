"""Smoke tests for sync_trenchbroom_profile tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import the sync tool's main functions
_IVAN_ROOT = Path(__file__).resolve().parents[1]  # apps/ivan
_TOOLS = _IVAN_ROOT / "tools"
if str(_TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_TOOLS))

from sync_trenchbroom_profile import build_manifest, generate


def test_build_manifest_structure() -> None:
    """Manifest has required keys and valid structure."""
    assets = _IVAN_ROOT / "assets"
    if not assets.is_dir():
        pytest.skip("assets directory not found")
    manifest = build_manifest(assets_root=assets)
    assert "version" in manifest
    assert manifest["version"] >= 1
    assert "textures" in manifest
    assert "names" in manifest["textures"]
    assert "count" in manifest["textures"]
    assert "wads" in manifest["textures"]
    assert "entities" in manifest
    assert "classnames" in manifest["entities"]
    assert "count" in manifest["entities"]
    assert "maps" in manifest
    assert "sources" in manifest
    assert manifest["textures"]["count"] == len(manifest["textures"]["names"])
    assert manifest["entities"]["count"] == len(manifest["entities"]["classnames"])


def test_generate_dry_run() -> None:
    """Dry run produces manifest without writing files."""
    assets = _IVAN_ROOT / "assets"
    if not assets.is_dir():
        pytest.skip("assets directory not found")
    out = _IVAN_ROOT / "trenchbroom" / "generated"
    report = generate(
        assets_root=assets,
        output_dir=out,
        extract_textures=True,
        dry_run=True,
    )
    assert report.get("dry_run") is True
    assert "manifest" in report
    m = report["manifest"]
    assert "textures" in m
    assert "entities" in m


def test_generate_output_correctness(tmp_path: Path) -> None:
    """Full generation produces valid manifest.json and editor_paths.json."""
    assets = _IVAN_ROOT / "assets"
    if not assets.is_dir():
        pytest.skip("assets directory not found")
    out = tmp_path / "generated"
    report = generate(
        assets_root=assets,
        output_dir=out,
        extract_textures=False,  # Skip WAD extraction for speed; validate structure only
        dry_run=False,
    )
    manifest_path = out / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] >= 1
    assert "textures" in manifest
    assert "entities" in manifest

    editor_paths_path = out / "editor_paths.json"
    assert editor_paths_path.exists()
    editor_paths = json.loads(editor_paths_path.read_text(encoding="utf-8"))
    assert "game_path" in editor_paths
    assert "generated_root" in editor_paths
    assert "fgd_path" in editor_paths
    assert Path(editor_paths["game_path"]) == assets.resolve()
    assert "ivan.fgd" in editor_paths["fgd_path"]
