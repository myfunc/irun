from __future__ import annotations

import os
from pathlib import Path

from ivan.state import IvanState, load_state, resolve_map_json, save_state
from ivan.paths import app_root as ivan_app_root


def test_state_roundtrip(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        assert load_state() == IvanState()
        s = IvanState(last_map_json="imported/halflife/valve/bounce", last_game_root="/x", last_mod="valve")
        save_state(s)
        assert load_state() == s
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_resolve_map_json_accepts_assets_alias_if_present() -> None:
    # This uses repo assets. If Bounce is removed, update the fixture and expectation.
    bounce = ivan_app_root() / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
    p = resolve_map_json("imported/halflife/valve/bounce")
    if bounce.exists():
        assert p is not None
        assert p.resolve() == bounce.resolve()
    else:
        assert p is None
