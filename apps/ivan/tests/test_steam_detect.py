from __future__ import annotations

from pathlib import Path

from ivan.maps.steam import detect_steam_halflife_game_root, parse_libraryfolders_vdf_paths


def test_parse_libraryfolders_vdf_paths_modern_and_legacy() -> None:
    text = r'''
    "libraryfolders"
    {
        "contentstatsid" "123"
        "1"
        {
            "path" "/Volumes/Games/SteamLibrary"
        }
        "2" "D:\\SteamLibrary"
    }
    '''
    paths = parse_libraryfolders_vdf_paths(text)
    assert Path("/Volumes/Games/SteamLibrary") in paths
    assert Path(r"D:\SteamLibrary") in paths


def test_detect_steam_halflife_game_root_from_libraryfolders(tmp_path: Path) -> None:
    # Primary steam root
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)

    # Secondary library referenced from libraryfolders.vdf
    lib = tmp_path / "SteamLibrary"
    (lib / "steamapps" / "common").mkdir(parents=True)

    # Put Half-Life under the secondary library
    hl = lib / "steamapps" / "common" / "Half-Life"
    (hl / "valve" / "maps").mkdir(parents=True)
    (hl / "valve" / "maps" / "crossfire.bsp").write_bytes(b"fake")

    # Write libraryfolders.vdf in the primary steam root.
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    vdf.write_text(
        f'''
        "libraryfolders"
        {{
            "1"
            {{
                "path" "{lib.as_posix()}"
            }}
        }}
        ''',
        encoding="utf-8",
    )

    detected = detect_steam_halflife_game_root(steam_roots=[steam])
    assert detected is not None
    # Should resolve to a directory that directly contains mod folders (valve/).
    assert (detected / "valve" / "maps" / "crossfire.bsp").exists()

