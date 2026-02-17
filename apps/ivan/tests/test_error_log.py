from __future__ import annotations

from pathlib import Path

from ivan.common.error_log import ErrorLog


def test_error_log_deduplicates_consecutive_same_error() -> None:
    log = ErrorLog(max_items=10)

    try:
        raise ValueError("boom")
    except Exception as e:
        log.log_exception(context="ctx", exc=e)

    try:
        raise ValueError("boom")
    except Exception as e:
        log.log_exception(context="ctx", exc=e)

    items = log.items()
    assert len(items) == 1
    assert items[0].count == 2
    assert "ValueError" in items[0].message


def test_error_log_keeps_tail_only() -> None:
    log = ErrorLog(max_items=3)
    log.log_message(context="c1", message="m1")
    log.log_message(context="c2", message="m2")
    log.log_message(context="c3", message="m3")
    log.log_message(context="c4", message="m4")

    items = log.items()
    assert len(items) == 3
    assert [it.context for it in items] == ["c2", "c3", "c4"]


def test_error_log_persists_critical_entries_to_file(tmp_path: Path) -> None:
    out = tmp_path / "logs" / "critical.log"
    log = ErrorLog(max_items=5, persist_path=out)
    log.log_message(context="net.spawn.invalid", message="Rejected server spawn")

    try:
        raise RuntimeError("boom")
    except Exception as e:
        log.log_exception(context="update.loop", exc=e)

    text = out.read_text(encoding="utf-8")
    assert "net.spawn.invalid" in text
    assert "Rejected server spawn" in text
    assert "RuntimeError: boom" in text
