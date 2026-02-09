from __future__ import annotations

from pathlib import Path


def test_find_compiled_bsp_prefers_recent_maps_output(tmp_path: Path) -> None:
    from ivan.maps.source_compile import find_compiled_bsp

    vmf = tmp_path / "mymap.vmf"
    vmf.write_text("x", encoding="utf-8")
    game_root = tmp_path / "game"
    (game_root / "maps").mkdir(parents=True, exist_ok=True)

    local_bsp = vmf.with_suffix(".bsp")
    local_bsp.write_bytes(b"old")
    maps_bsp = game_root / "maps" / "mymap.bsp"
    maps_bsp.write_bytes(b"new")

    # Make sure maps_bsp is considered newer than local_bsp.
    started = float(local_bsp.stat().st_mtime) + 0.5
    out = find_compiled_bsp(
        vmf_path=vmf,
        compile_game_root=game_root,
        override_bsp_path=None,
        started_at=started,
    )
    assert out == maps_bsp.resolve()


def test_create_temp_source_game_root_links_vmf_assets(tmp_path: Path) -> None:
    from ivan.maps.source_compile import create_temp_source_game_root

    vmf_dir = tmp_path / "src_map"
    (vmf_dir / "materials").mkdir(parents=True, exist_ok=True)
    (vmf_dir / "models").mkdir(parents=True, exist_ok=True)
    (vmf_dir / "materials" / "a.vtf").write_bytes(b"123")
    (vmf_dir / "models" / "a.mdl").write_bytes(b"456")

    game_root = create_temp_source_game_root(vmf_dir=vmf_dir, fallback_game_root=None)
    try:
        assert (game_root / "gameinfo.txt").exists()
        assert (game_root / "materials").exists()
        assert (game_root / "models").exists()
        # Whether copied or symlinked, files should be visible from compile root.
        assert (game_root / "materials" / "a.vtf").exists()
        assert (game_root / "models" / "a.mdl").exists()
    finally:
        import shutil

        shutil.rmtree(game_root, ignore_errors=True)


def test_resolve_compile_tool_prefers_explicit_path(tmp_path: Path) -> None:
    from ivan.maps.source_compile import resolve_compile_tool

    explicit = tmp_path / "vbsp_osx"
    explicit.write_text("#!/bin/sh\n", encoding="utf-8")
    out = resolve_compile_tool(
        tool="vbsp",
        explicit=explicit,
        compile_bin=None,
        fallback_game_root=None,
    )
    assert out == explicit.resolve()

