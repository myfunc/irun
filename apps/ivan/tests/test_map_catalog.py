from __future__ import annotations

from pathlib import Path

from ivan.maps.catalog import detect_goldsrc_like_mods, find_runnable_bundles, list_goldsrc_like_maps
from ivan.paths import app_root as ivan_app_root


def test_find_runnable_bundles_includes_imported_bundles_when_present() -> None:
    app_root = ivan_app_root()
    bundles = find_runnable_bundles(app_root=app_root)
    labels = {b.label for b in bundles}

    # Repo usually ships Bounce. If it is removed, this test will guide updating expectations.
    bounce = app_root / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
    if bounce.exists():
        assert "imported/halflife/valve/bounce" in labels


def test_detect_goldsrc_like_mods_and_map_listing(tmp_path: Path) -> None:
    root = tmp_path / "Half-Life"
    valve = root / "valve" / "maps"
    valve.mkdir(parents=True)
    (valve / "crossfire.bsp").write_bytes(b"fake")
    (valve / "datacore.bsp").write_bytes(b"fake")

    cstrike = root / "cstrike" / "maps"
    cstrike.mkdir(parents=True)
    (cstrike / "de_dust2.bsp").write_bytes(b"fake")

    mods = detect_goldsrc_like_mods(game_root=root)
    assert mods == ["cstrike", "valve"]

    maps = list_goldsrc_like_maps(game_root=root, mod="valve")
    assert [m.label for m in maps] == ["crossfire", "datacore"]


def test_detect_goldsrc_like_mods_supports_macos_app_bundle_layout(tmp_path: Path) -> None:
    # Steam on macOS commonly wraps GoldSrc games in an .app bundle.
    root = tmp_path / "Half-Life"
    resources = root / "Half-Life.app" / "Contents" / "Resources"
    valve = resources / "valve" / "maps"
    valve.mkdir(parents=True)
    (valve / "crossfire.bsp").write_bytes(b"fake")

    mods = detect_goldsrc_like_mods(game_root=root)
    assert mods == ["valve"]

    maps = list_goldsrc_like_maps(game_root=root, mod="valve")
    assert [m.label for m in maps] == ["crossfire"]


def test_detect_goldsrc_like_mods_supports_passing_app_bundle_as_root(tmp_path: Path) -> None:
    app = tmp_path / "Half-Life.app"
    resources = app / "Contents" / "Resources"
    cstrike = resources / "cstrike" / "maps"
    cstrike.mkdir(parents=True)
    (cstrike / "de_dust2.bsp").write_bytes(b"fake")

    mods = detect_goldsrc_like_mods(game_root=app)
    assert mods == ["cstrike"]
