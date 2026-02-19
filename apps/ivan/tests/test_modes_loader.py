from __future__ import annotations

from ivan.modes.loader import load_mode


def test_load_mode_race_returns_race_mode() -> None:
    """Race is first-class mode; no longer aliased to time_trial."""
    mode = load_mode(mode="race", config=None)
    assert mode.id == "race"
