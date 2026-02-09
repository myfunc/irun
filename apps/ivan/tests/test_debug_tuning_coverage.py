from __future__ import annotations

from pathlib import Path

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
    assert "slide_stop_t90" in covered
    assert "grace_period" in covered
    assert "camera_base_fov" in covered
    assert "camera_speed_fov_max_add" in covered
    assert "camera_tilt_gain" in covered
    assert "camera_event_gain" in covered
    assert "vault_max_ledge_height" in covered
    assert "vault_height_boost" in covered
    assert "vault_forward_boost" in covered
    assert "player_half_height" in covered
    assert "slide_enabled" in covered
    assert "vault_enabled" in covered
    assert "character_scale_lock_enabled" in covered
    assert "autojump_enabled" in covered
    assert "wallrun_enabled" in covered
    assert "camera_feedback_enabled" in covered
    assert "surf_enabled" in covered
    assert "surf_accel" not in covered
    assert "surf_gravity_scale" not in covered
    assert "mouse_sensitivity" not in covered

    grouped = set()
    for _group_name, n_fields, t_fields in DebugUI.GROUPS:
        grouped.update(n_fields)
        grouped.update(t_fields)
    assert covered == grouped


def test_camera_debug_surface_stays_core_and_compact() -> None:
    numeric_fields = [name for name, _low, _high in DebugUI.NUMERIC_CONTROLS]
    toggle_fields = list(DebugUI.TOGGLE_CONTROLS)
    camera_numeric = {name for name in numeric_fields if name.startswith("camera_")}
    camera_toggles = {name for name in toggle_fields if name.startswith("camera_")}

    assert camera_numeric == {
        "camera_base_fov",
        "camera_speed_fov_max_add",
        "camera_tilt_gain",
        "camera_event_gain",
    }
    assert camera_toggles == {"camera_feedback_enabled"}

    camera_group = None
    for group_name, n_fields, t_fields in DebugUI.GROUPS:
        if group_name == "Camera":
            camera_group = (set(n_fields), set(t_fields))
            break
    assert camera_group is not None
    g_num, g_tog = camera_group
    assert camera_numeric == g_num
    assert "camera_feedback_enabled" in g_tog


def test_debug_numeric_controls_are_real_unit_values_not_normalized_percent() -> None:
    debug_ui_path = Path(__file__).resolve().parents[1] / "src" / "ivan" / "ui" / "debug_ui.py"
    src = debug_ui_path.read_text(encoding="utf-8")
    assert "normalized_slider=False" in src
    assert "normalized_entry=False" in src
