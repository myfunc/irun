from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ivan.console.autotune_bindings import autotune_apply
from ivan.game.autotune import evaluate_route_guardrails, load_route_context, suggest_invariant_adjustments
from ivan.game.feel_feedback import TuningAdjustment
from ivan.physics.tuning import PhysicsTuning


def _write_summary(path: Path, *, route_tag: str, exported_at_unix: float, metrics: dict | None = None) -> Path:
    payload = {
        "export_metadata": {
            "route_tag": route_tag,
            "exported_at_unix": float(exported_at_unix),
        },
        "metrics": metrics or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def test_load_route_context_falls_back_to_latest_route_summary(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_summary(out_dir / "a_old.summary.json", route_tag="A", exported_at_unix=1.0)
    latest = _write_summary(out_dir / "a_new.summary.json", route_tag="A", exported_at_unix=2.0)
    _write_summary(out_dir / "b_only.summary.json", route_tag="B", exported_at_unix=3.0)

    monkeypatch.setattr(
        "ivan.game.autotune.compare_latest_route_exports",
        lambda route_tag, out_dir=None: (_ for _ in ()).throw(ValueError("compare missing")),
    )

    context = load_route_context(route_tag="a", out_dir=out_dir)

    assert context.route_tag == "A"
    assert context.latest_summary_path == latest.resolve()
    assert context.comparison_path is None
    assert context.history_path is None
    assert "using latest route summary only" in context.note


def test_suggest_invariant_adjustments_uses_history_and_stays_invariant_only() -> None:
    tuning = PhysicsTuning(
        max_ground_speed=6.0,
        run_t90=0.24,
        ground_stop_t90=0.22,
        air_speed_mult=1.7,
        air_gain_t90=0.24,
    )
    history_payload = {
        "metrics": {
            "metrics": {
                "horizontal_speed_avg": {
                    "rank": 4,
                    "prior_count": 7,
                }
            }
        }
    }

    adjustments = suggest_invariant_adjustments(
        feedback_text="too slow",
        tuning=tuning,
        latest_summary=None,
        history_payload=history_payload,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert "max_ground_speed" in by_field
    assert "air_speed_mult" in by_field
    assert "surf_accel" not in by_field
    assert "metric: speed rank below prior median" in by_field["max_ground_speed"].reason
    assert float(by_field["max_ground_speed"].after) > float(by_field["max_ground_speed"].before)
    assert float(by_field["max_ground_speed"].after) <= float(by_field["max_ground_speed"].before) * 1.05 + 1e-9


def test_suggest_invariant_adjustments_handles_wallrun_aggressive_feedback() -> None:
    tuning = PhysicsTuning(
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )
    adjustments = suggest_invariant_adjustments(
        feedback_text="wallrun too aggressive and triggers too easily",
        tuning=tuning,
        latest_summary=None,
        history_payload=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_min_entry_speed_mult"].after > by_field["wallrun_min_entry_speed_mult"].before
    assert by_field["wallrun_min_approach_dot"].after > by_field["wallrun_min_approach_dot"].before
    assert by_field["wallrun_min_parallel_dot"].after > by_field["wallrun_min_parallel_dot"].before


def test_suggest_invariant_adjustments_handles_curved_wallrun_feedback() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )
    adjustments = suggest_invariant_adjustments(
        feedback_text="curved wallrun doesnt work",
        tuning=tuning,
        latest_summary=None,
        history_payload=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_approach_dot"].after < by_field["wallrun_min_approach_dot"].before
    assert by_field["wallrun_min_parallel_dot"].after < by_field["wallrun_min_parallel_dot"].before


def test_suggest_invariant_adjustments_handles_wallrun_not_working_phrase() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )
    adjustments = suggest_invariant_adjustments(
        feedback_text="wallrun doesnt work really",
        tuning=tuning,
        latest_summary=None,
        history_payload=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_entry_speed_mult"].after < by_field["wallrun_min_entry_speed_mult"].before


def test_suggest_invariant_adjustments_handles_wallrun_not_engaging_phrase() -> None:
    tuning = PhysicsTuning(
        wallrun_sink_t90=0.22,
        wallrun_min_entry_speed_mult=0.45,
        wallrun_min_approach_dot=0.08,
        wallrun_min_parallel_dot=0.30,
    )
    adjustments = suggest_invariant_adjustments(
        feedback_text="wallrun is not engaging, i fall of the wall",
        tuning=tuning,
        latest_summary=None,
        history_payload=None,
    )

    by_field = {adj.field: adj for adj in adjustments}
    assert by_field["wallrun_sink_t90"].after > by_field["wallrun_sink_t90"].before
    assert by_field["wallrun_min_entry_speed_mult"].after < by_field["wallrun_min_entry_speed_mult"].before


def test_evaluate_route_guardrails_returns_route_score_and_checks(tmp_path: Path, monkeypatch) -> None:
    latest = _write_summary(
        tmp_path / "latest.summary.json",
        route_tag="A",
        exported_at_unix=3.0,
        metrics={
            "jump_takeoff": {"success_rate": 0.88},
            "horizontal_speed_avg": 145.0,
            "landing_speed_loss_avg": 0.62,
            "ground_flicker_per_min": 9.0,
            "camera_lin_jerk_avg": 85.0,
            "camera_ang_jerk_avg": 520.0,
        },
    )
    reference = _write_summary(
        tmp_path / "reference.summary.json",
        route_tag="A",
        exported_at_unix=2.0,
        metrics={
            "jump_takeoff": {"success_rate": 0.82},
            "horizontal_speed_avg": 132.0,
            "landing_speed_loss_avg": 0.84,
            "ground_flicker_per_min": 11.0,
            "camera_lin_jerk_avg": 93.0,
            "camera_ang_jerk_avg": 590.0,
        },
    )
    comparison = tmp_path / "cmp.json"
    history = tmp_path / "hist.json"

    monkeypatch.setattr(
        "ivan.game.autotune.compare_latest_route_exports",
        lambda route_tag, out_dir=None: SimpleNamespace(
            latest_export=SimpleNamespace(summary_path=latest),
            reference_export=SimpleNamespace(summary_path=reference),
            improved_count=5,
            regressed_count=0,
            equal_count=1,
            comparison_path=comparison,
            history_path=history,
        ),
    )

    result = evaluate_route_guardrails(route_tag="A", out_dir=tmp_path)

    assert result.route_tag == "A"
    assert result.passed is True
    assert result.score > 0.0
    assert result.comparison_path == comparison.resolve()
    assert result.history_path == history.resolve()
    assert len(result.checks) == 5
    assert all(check.passed for check in result.checks)


def test_autotune_apply_creates_backup_before_updates(monkeypatch) -> None:
    class _Runner:
        def __init__(self) -> None:
            self.tuning = PhysicsTuning(max_ground_speed=6.0)
            self.events: list[str] = []

        def _on_tuning_change(self, field: str) -> None:
            self.events.append(f"change:{field}")

    runner = _Runner()
    context = SimpleNamespace(
        route_tag="A",
        note="route compare ready (+3/-1/=2)",
        latest_summary_path=None,
        comparison_path=None,
        history_path=None,
    )
    adjustments = [
        TuningAdjustment(
            field="max_ground_speed",
            before=6.0,
            after=6.3,
            reason="intent: raise top speed",
        )
    ]
    backup = Path("/tmp/autotune-backup.json")

    monkeypatch.setattr(
        "ivan.console.autotune_bindings.autotune_suggest",
        lambda runner, route_tag, feedback_text, out_dir=None: (context, adjustments),
    )

    def _backup(*args, **kwargs):
        _ = args, kwargs
        runner.events.append("backup")
        return backup

    monkeypatch.setattr("ivan.console.autotune_bindings.create_tuning_backup", _backup)

    out_context, out_adjustments, out_backup = autotune_apply(
        runner=runner,
        route_tag="A",
        feedback_text="too slow",
        out_dir=None,
    )

    assert out_context is context
    assert out_adjustments == adjustments
    assert out_backup == backup
    assert runner.events[0] == "backup"
    assert runner.events[1] == "change:max_ground_speed"
    assert runner.tuning.max_ground_speed == 6.3
