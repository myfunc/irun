from __future__ import annotations

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.debug_ui import DebugUI


def test_debug_ui_exposes_every_tuning_field() -> None:
    tuning_fields = set(PhysicsTuning.__annotations__.keys())
    numeric_fields = [name for name, _low, _high in DebugUI.NUMERIC_CONTROLS]
    toggle_fields = list(DebugUI.TOGGLE_CONTROLS)
    covered = set(numeric_fields) | set(toggle_fields)

    assert len(numeric_fields) == len(set(numeric_fields))
    assert len(toggle_fields) == len(set(toggle_fields))
    assert tuning_fields == covered

    grouped = set()
    for _group_name, n_fields, t_fields in DebugUI.GROUPS:
        grouped.update(n_fields)
        grouped.update(t_fields)
    assert tuning_fields <= grouped
