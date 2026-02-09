from __future__ import annotations

from types import SimpleNamespace

from ivan.console.core import CommandContext
from ivan.console.ivan_bindings import build_client_console


class _FakeRunner:
    def __init__(self) -> None:
        self.tuning = SimpleNamespace()
        self._runtime_connect_port = 7777

    def _on_connect_server_from_menu(self, host: str, port_text: str) -> None:
        self.connected = (host, port_text)

    def _on_disconnect_server_from_menu(self) -> None:
        self.disconnected = True

    def _on_tuning_change(self, _field: str) -> None:
        return

    def _feel_apply_feedback(self, route_tag: str, text: str) -> None:
        self.feedback_call = (route_tag, text)


def test_console_replay_export_latest_command(monkeypatch) -> None:
    runner = _FakeRunner()
    con = build_client_console(runner)

    called = {"count": 0}

    def _fake_export_latest(*, out_dir=None):
        called["count"] += 1
        return SimpleNamespace(
            source_demo="/tmp/sample.ivan_demo.json",
            csv_path="/tmp/sample.telemetry.csv",
            summary_path="/tmp/sample.summary.json",
            tick_count=120,
            telemetry_tick_count=120,
        )

    monkeypatch.setattr("ivan.console.ivan_bindings.export_latest_replay_telemetry", _fake_export_latest)

    out = con.execute_line(ctx=CommandContext(role="client", origin="test"), line="replay_export_latest")

    assert called["count"] == 1
    assert any("sample.telemetry.csv" in line for line in out)


def test_console_replay_compare_latest_command(monkeypatch) -> None:
    runner = _FakeRunner()
    con = build_client_console(runner)

    def _fake_compare(*, out_dir=None, route_tag=None):
        _ = out_dir, route_tag
        return SimpleNamespace(
            latest_export=SimpleNamespace(source_demo="/tmp/latest.ivan_demo.json"),
            reference_export=SimpleNamespace(source_demo="/tmp/ref.ivan_demo.json"),
            comparison_path="/tmp/compare.json",
            improved_count=3,
            regressed_count=1,
            equal_count=2,
        )

    monkeypatch.setattr("ivan.console.ivan_bindings.compare_latest_replays", _fake_compare)
    out = con.execute_line(ctx=CommandContext(role="client", origin="test"), line="replay_compare_latest")

    assert any("compare.json" in line for line in out)
    assert any("+3" in line for line in out)


def test_console_feel_feedback_command() -> None:
    runner = _FakeRunner()
    con = build_client_console(runner)
    out = con.execute_line(ctx=CommandContext(role="client", origin="test"), line='feel_feedback "too fast" A')
    assert runner.feedback_call == ("A", "too fast")
    assert any("feel_feedback applied" in line for line in out)
