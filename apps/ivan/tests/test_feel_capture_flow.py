from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ivan.game import feel_capture_flow as flow
from ivan.game.feel_feedback import TuningAdjustment


class _FakeUI:
    def __init__(self) -> None:
        self.last_status = ""

    def set_status(self, text: str) -> None:
        self.last_status = str(text)


class _FakePauseUI:
    def __init__(self) -> None:
        self.last_status = ""

    def set_feel_status(self, text: str) -> None:
        self.last_status = str(text)

    def clear_feel_feedback(self) -> None:
        pass


class _FakeFeelCaptureUI:
    def __init__(self) -> None:
        self.show_calls = 0
        self.hide_calls = 0
        self.last_status = ""
        self.feedback_cleared = False

    def show(self) -> None:
        self.show_calls += 1

    def hide(self) -> None:
        self.hide_calls += 1

    def set_status(self, text: str) -> None:
        self.last_status = str(text)

    def clear_feedback(self) -> None:
        self.feedback_cleared = True


def test_open_feel_capture_stages_current_run_and_stops_recording(tmp_path: Path) -> None:
    staged = tmp_path / "staged.ivan_demo.json"
    staged.write_text("{}", encoding="utf-8")
    pointer_locks: list[bool] = []
    host = SimpleNamespace(
        _mode="game",
        _playback_active=False,
        _pause_menu_open=False,
        _debug_menu_open=False,
        _replay_browser_open=False,
        _console_open=False,
        _feel_capture_open=False,
        _feel_capture_staged_demo_path=None,
        _active_recording=object(),
        ui=_FakeUI(),
        pause_ui=_FakePauseUI(),
        feel_capture_ui=_FakeFeelCaptureUI(),
        _save_current_demo=lambda: staged,
        _set_pointer_lock=lambda locked: pointer_locks.append(bool(locked)),
    )

    flow.open_feel_capture(host)

    assert host._feel_capture_open is True
    assert isinstance(host._feel_capture_staged_demo_path, Path)
    assert host._feel_capture_staged_demo_path == staged
    assert host._active_recording is None
    assert host.feel_capture_ui.show_calls == 1
    assert pointer_locks and pointer_locks[-1] is False
    assert "run frozen" in host.ui.last_status.lower()


def test_submit_feel_capture_export_prefers_staged_demo_over_live_save(tmp_path: Path, monkeypatch) -> None:
    staged = tmp_path / "staged.ivan_demo.json"
    staged.write_text("{}", encoding="utf-8")
    summary = tmp_path / "summary.json"
    summary.write_text("{}", encoding="utf-8")
    save_calls = {"count": 0}
    started = {"count": 0}
    exported_paths: list[Path] = []

    def _save_current_demo() -> Path | None:
        save_calls["count"] += 1
        return None

    def _start_new_demo_recording() -> None:
        started["count"] += 1
        host._active_recording = object()

    host = SimpleNamespace(
        _mode="game",
        _playback_active=False,
        _pause_menu_open=False,
        _debug_menu_open=False,
        _replay_browser_open=False,
        _console_open=False,
        _feel_capture_open=True,
        _feel_capture_staged_demo_path=staged,
        _active_recording=None,
        ui=_FakeUI(),
        pause_ui=_FakePauseUI(),
        feel_capture_ui=_FakeFeelCaptureUI(),
        _save_current_demo=_save_current_demo,
        _start_new_demo_recording=_start_new_demo_recording,
    )

    def _fake_export(*, replay_path, route_tag, route_name, run_note, feedback_text, comment):
        _ = route_tag, route_name, run_note, feedback_text, comment
        replay_path = Path(replay_path)
        exported_paths.append(replay_path)
        summary.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return SimpleNamespace(summary_path=summary)

    def _fake_compare_latest_route_exports(*, route_tag, latest_summary):
        _ = route_tag, latest_summary
        return SimpleNamespace(improved_count=0, regressed_count=0, equal_count=0, history_run_count=1)

    monkeypatch.setattr(flow, "export_replay_telemetry", _fake_export)
    monkeypatch.setattr(flow, "compare_latest_route_exports", _fake_compare_latest_route_exports)

    flow.submit_feel_capture_export(
        host,
        route_tag="A",
        route_name="",
        run_note="",
        feedback_text="",
        apply_feedback=False,
    )

    assert save_calls["count"] == 0
    assert exported_paths == [staged]
    assert host._feel_capture_staged_demo_path is None
    assert started["count"] == 1
    assert host._active_recording is not None


def test_close_feel_capture_resumes_recording_when_needed() -> None:
    pointer_locks: list[bool] = []
    started = {"count": 0}
    host = SimpleNamespace(
        _mode="game",
        _playback_active=False,
        _pause_menu_open=False,
        _debug_menu_open=False,
        _replay_browser_open=False,
        _console_open=False,
        _feel_capture_open=True,
        _feel_capture_staged_demo_path=Path("/tmp/staged.ivan_demo.json"),
        _active_recording=None,
        ui=_FakeUI(),
        pause_ui=_FakePauseUI(),
        feel_capture_ui=_FakeFeelCaptureUI(),
        _start_new_demo_recording=lambda: started.__setitem__("count", int(started["count"]) + 1),
        _set_pointer_lock=lambda locked: pointer_locks.append(bool(locked)),
    )

    flow.close_feel_capture(host)

    assert host._feel_capture_open is False
    assert host._feel_capture_staged_demo_path is None
    assert host.feel_capture_ui.hide_calls == 1
    assert started["count"] == 1
    assert pointer_locks and pointer_locks[-1] is True


def test_submit_feel_capture_export_apply_uses_run_note_when_feedback_empty(monkeypatch) -> None:
    summary_payload = {"metrics": {}}
    status_ui = _FakeUI()
    host = SimpleNamespace(
        _mode="game",
        _playback_active=False,
        _pause_menu_open=False,
        _debug_menu_open=False,
        _replay_browser_open=False,
        _console_open=False,
        _feel_capture_open=True,
        _feel_capture_staged_demo_path=None,
        _active_recording=object(),
        tuning=SimpleNamespace(max_ground_speed=6.0),
        ui=status_ui,
        pause_ui=_FakePauseUI(),
        feel_capture_ui=_FakeFeelCaptureUI(),
        _save_current_demo=lambda: Path("/tmp/demo.ivan_demo.json"),
        _start_new_demo_recording=lambda: None,
        _on_tuning_change=lambda _field: None,
    )

    monkeypatch.setattr(
        flow,
        "_save_and_export_current_run",
        lambda *_args, **_kwargs: (SimpleNamespace(summary_path=Path("x.summary.json")), summary_payload, "cmp ok"),
    )
    monkeypatch.setattr(
        flow,
        "_suggest_export_apply_adjustments",
        lambda **_kwargs: [
            TuningAdjustment(field="max_ground_speed", before=6.0, after=6.1, reason="test adjustment"),
        ],
    )
    monkeypatch.setattr(flow, "_create_tuning_backup", lambda *_args, **_kwargs: SimpleNamespace(name="bk-test"))

    flow.submit_feel_capture_export(
        host,
        route_tag="A",
        route_name="route",
        run_note="wallrun doesnt work",
        feedback_text="",
        apply_feedback=True,
    )

    assert "applied 1 tweak" in status_ui.last_status.lower()
