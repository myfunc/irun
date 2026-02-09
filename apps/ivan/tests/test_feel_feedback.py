from __future__ import annotations

from ivan.game.feel_feedback import apply_adjustments, suggest_adjustments
from ivan.physics.tuning import PhysicsTuning


def test_suggest_adjustments_reacts_to_fast_and_accel_feedback() -> None:
    tuning = PhysicsTuning(
        max_ground_speed=10.0,
        max_air_speed=12.0,
        ground_accel=30.0,
        jump_accel=20.0,
        surf_accel=50.0,
    )

    adjustments = suggest_adjustments(
        feedback_text="feels too fast and acceleration is too fast",
        tuning=tuning,
        latest_summary=None,
    )

    changed = {a.field: a for a in adjustments}
    assert "max_ground_speed" in changed
    assert "ground_accel" in changed
    assert changed["max_ground_speed"].after < changed["max_ground_speed"].before
    assert changed["ground_accel"].after < changed["ground_accel"].before


def test_suggest_adjustments_uses_metrics_for_smoothness_bias() -> None:
    tuning = PhysicsTuning(ground_snap_dist=0.05, step_height=0.40)
    summary = {
        "metrics": {
            "ground_flicker_per_min": 70.0,
            "camera_lin_jerk_avg": 150.0,
            "landing_speed_loss_avg": 1.4,
        }
    }

    adjustments = suggest_adjustments(
        feedback_text="doesnt feel smooth",
        tuning=tuning,
        latest_summary=summary,
    )
    by_field = {a.field: a for a in adjustments}
    assert by_field["ground_snap_dist"].after > by_field["ground_snap_dist"].before
    assert by_field["step_height"].after > by_field["step_height"].before

    apply_adjustments(tuning=tuning, adjustments=adjustments)
    assert tuning.ground_snap_dist > 0.05


def test_suggest_adjustments_requires_feedback_intent() -> None:
    tuning = PhysicsTuning()
    summary = {
        "metrics": {
            "ground_flicker_per_min": 80.0,
            "camera_lin_jerk_avg": 200.0,
            "landing_speed_loss_avg": 2.0,
        }
    }
    adjustments = suggest_adjustments(
        feedback_text="just testing",
        tuning=tuning,
        latest_summary=summary,
    )
    assert adjustments == []
