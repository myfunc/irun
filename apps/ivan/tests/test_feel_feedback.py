from __future__ import annotations

from ivan.game.feel_feedback import apply_adjustments, suggest_adjustments
from ivan.physics.tuning import PhysicsTuning


def test_suggest_adjustments_reacts_to_fast_and_accel_feedback() -> None:
    tuning = PhysicsTuning(
        max_ground_speed=10.0,
        air_speed_mult=1.2,
        run_t90=0.20,
        air_gain_t90=0.20,
        surf_accel=50.0,
    )

    adjustments = suggest_adjustments(
        feedback_text="feels too fast and acceleration is too fast",
        tuning=tuning,
        latest_summary=None,
    )

    changed = {a.field: a for a in adjustments}
    assert "max_ground_speed" in changed
    assert "run_t90" in changed
    assert "air_gain_t90" in changed
    assert changed["max_ground_speed"].after < changed["max_ground_speed"].before
    assert changed["run_t90"].after > changed["run_t90"].before


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


def test_suggest_adjustments_recognizes_curved_wallrun_and_false_ground_phrasing() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
        step_height=0.55,
        ground_snap_dist=0.056,
    )
    text = "curved wallruns dont work and i can walk along bottom ledge where there is no ground"

    adjustments = suggest_adjustments(
        feedback_text=text,
        tuning=tuning,
        latest_summary=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_approach_dot"].after < by_field["wallrun_min_approach_dot"].before
    assert by_field["wallrun_min_parallel_dot"].after < by_field["wallrun_min_parallel_dot"].before
    assert by_field["ground_snap_dist"].after < by_field["ground_snap_dist"].before
    assert by_field["step_height"].after < by_field["step_height"].before


def test_suggest_adjustments_recognizes_wallrun_not_working_phrase() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )

    adjustments = suggest_adjustments(
        feedback_text="wallrun doesnt work really",
        tuning=tuning,
        latest_summary=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_entry_speed_mult"].after < by_field["wallrun_min_entry_speed_mult"].before


def test_suggest_adjustments_recognizes_wallrun_not_engaging_phrase() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )

    adjustments = suggest_adjustments(
        feedback_text="wallrun is not engaging, i fall of the wall",
        tuning=tuning,
        latest_summary=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_entry_speed_mult"].after < by_field["wallrun_min_entry_speed_mult"].before
