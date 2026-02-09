from __future__ import annotations

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.debug_ui import DebugUI


def test_debug_ui_exposes_curated_invariant_first_controls() -> None:
    tuning_fields = set(PhysicsTuning.__annotations__.keys())
    numeric_fields = [name for name, _low, _high in DebugUI.NUMERIC_CONTROLS]
    toggle_fields = list(DebugUI.TOGGLE_CONTROLS)
    covered = set(numeric_fields) | set(toggle_fields)

    assert len(numeric_fields) == len(set(numeric_fields))
    assert len(toggle_fields) == len(set(toggle_fields))
    assert covered <= tuning_fields

    # Movement rehaul policy: keep a compact, invariant-first debug surface.
    assert "max_ground_speed" in covered
    assert "run_t90" in covered
    assert "ground_stop_t90" in covered
    assert "air_speed_mult" in covered
    assert "air_gain_t90" in covered
    assert "wallrun_sink_t90" in covered
    assert "jump_height" in covered
    assert "jump_apex_time" in covered
    assert "dash_distance" in covered
    assert "dash_duration" in covered
    assert "coyote_time" in covered
    assert "jump_buffer_time" in covered
    assert "dash_enabled" in covered
    assert "dash_sweep_enabled" in covered
    assert "autojump_enabled" in covered
    assert "wallrun_enabled" in covered
    assert "surf_enabled" in covered
    assert "surf_accel" not in covered
    assert "surf_gravity_scale" not in covered
    assert "mouse_sensitivity" not in covered

    grouped = set()
    for _group_name, n_fields, t_fields in DebugUI.GROUPS:
        grouped.update(n_fields)
        grouped.update(t_fields)
    assert covered == grouped
