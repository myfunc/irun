from __future__ import annotations

from pathlib import Path


def test_find_compiled_bsp_prefers_recent_maps_output(tmp_path: Path) -> None:
    from ivan.maps.goldsrc_compile import find_compiled_bsp

    map_path = tmp_path / "tb_demo.map"
    map_path.write_text("// tb", encoding="utf-8")
    game_root = tmp_path / "valve"
    (game_root / "maps").mkdir(parents=True, exist_ok=True)

    local_bsp = map_path.with_suffix(".bsp")
    local_bsp.write_bytes(b"old")
    maps_bsp = game_root / "maps" / "tb_demo.bsp"
    maps_bsp.write_bytes(b"new")

    started = float(local_bsp.stat().st_mtime) + 0.5
    out = find_compiled_bsp(
        map_path=map_path,
        game_root=game_root,
        override_bsp_path=None,
        started_at=started,
    )
    assert out == maps_bsp.resolve()


def test_resolve_compile_tool_prefers_explicit_path(tmp_path: Path) -> None:
    from ivan.maps.goldsrc_compile import resolve_compile_tool

    explicit = tmp_path / "hlcsg"
    explicit.write_text("#!/bin/sh\n", encoding="utf-8")
    out = resolve_compile_tool(
        tool="hlcsg",
        explicit=explicit,
        compile_bin=None,
        game_root=None,
    )
    assert out == explicit.resolve()
