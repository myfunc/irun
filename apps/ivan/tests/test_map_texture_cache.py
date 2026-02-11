from __future__ import annotations

from pathlib import Path

from ivan.maps.map_converter import (
    _build_wad_fingerprints,
    _clear_texture_cache_dir,
    _load_texture_cache_manifest,
    _manifest_matches_wads,
    _restore_cached_textures,
    _save_texture_cache_manifest,
)


def _touch(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_texture_cache_manifest_hit_and_invalidation(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    wad = tmp_path / "source.wad"
    _touch(wad, b"wad-v1")

    fp_v1 = _build_wad_fingerprints([wad])
    _save_texture_cache_manifest(
        cache_dir=cache_dir,
        wad_fingerprints=fp_v1,
        texture_sizes={"brick": (64, 64), "metal": (128, 128)},
    )
    _touch(cache_dir / "brick.png", b"x")
    _touch(cache_dir / "metal.png", b"y")

    manifest = _load_texture_cache_manifest(cache_dir)
    assert _manifest_matches_wads(manifest=manifest, wad_fingerprints=fp_v1)
    restored = _restore_cached_textures(cache_dir=cache_dir, manifest=manifest)
    assert restored is not None
    mats, sizes = restored
    assert set(mats.keys()) == {"brick", "metal"}
    assert sizes["brick"] == (64, 64)
    assert sizes["metal"] == (128, 128)

    _touch(wad, b"wad-v2")  # checksum changed -> manifest mismatch.
    fp_v2 = _build_wad_fingerprints([wad])
    assert not _manifest_matches_wads(manifest=manifest, wad_fingerprints=fp_v2)


def test_texture_cache_clear_removes_manifest_and_pngs(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _touch(cache_dir / ".wad_texture_cache_manifest.json", b"{}")
    _touch(cache_dir / "a.png", b"x")
    _touch(cache_dir / "b.png", b"y")

    _clear_texture_cache_dir(cache_dir)

    assert not (cache_dir / ".wad_texture_cache_manifest.json").exists()
    assert not (cache_dir / "a.png").exists()
    assert not (cache_dir / "b.png").exists()
