from __future__ import annotations

from ivan.modes.loader import load_mode


def test_load_mode_accepts_race_alias() -> None:
    mode = load_mode(mode="race", config=None)
    assert mode.id == "time_trial"
