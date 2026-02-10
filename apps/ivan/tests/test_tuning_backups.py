from __future__ import annotations

from pathlib import Path

from ivan.game.tuning_backups import (
    backup_metadata,
    create_tuning_backup,
    list_tuning_backups,
    restore_tuning_backup,
    resolve_tuning_backup,
)


class _FakeHost:
    def __init__(self) -> None:
        self._active_profile_name = "surf_bhop_c2"
        self._profiles: dict[str, dict[str, float | bool]] = {
            "surf_bhop_c2": {
                "max_ground_speed": 6.5,
                "jump_height": 1.2,
                "jump_apex_time": 0.27,
                "autojump_enabled": True,
            },
            "bhop": {"max_ground_speed": 8.0, "jump_height": 1.3, "jump_apex_time": 0.30, "autojump_enabled": True},
        }
        self.applied_profile: str | None = None
        self.applied_snapshot: dict[str, float | bool] | None = None
        self.persist_calls: int = 0

    def _current_tuning_snapshot(self) -> dict[str, float | bool]:
        return dict(self._profiles[self._active_profile_name])

    def _apply_profile(self, profile_name: str) -> None:
        self._active_profile_name = str(profile_name)
        self.applied_profile = str(profile_name)

    def _apply_profile_snapshot(self, values: dict[str, float | bool], *, persist: bool) -> None:
        _ = persist
        self.applied_snapshot = dict(values)

    def _persist_profiles_state(self) -> None:
        self.persist_calls += 1


def test_tuning_backup_create_list_and_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    host = _FakeHost()

    path = create_tuning_backup(host, label="Route A", reason="manual-test")
    assert path.exists()

    rows = list_tuning_backups(limit=5)
    assert rows
    assert rows[0].name == path.name

    md = backup_metadata(path)
    assert md["active_profile_name"] == "surf_bhop_c2"
    assert int(md["field_count"]) >= 4


def test_tuning_backup_restore_latest_and_named(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IRUN_IVAN_STATE_DIR", str(tmp_path / "state"))
    host = _FakeHost()

    p1 = create_tuning_backup(host, label="baseline", reason="test")
    assert p1.exists()

    host._active_profile_name = "bhop"
    restored_latest = restore_tuning_backup(host)
    assert restored_latest.exists()
    assert host.applied_profile == "surf_bhop_c2"
    assert isinstance(host.applied_snapshot, dict)
    assert float(host.applied_snapshot.get("max_ground_speed", 0.0)) == 6.5
    assert host.persist_calls == 1
    assert float(host._profiles["surf_bhop_c2"]["max_ground_speed"]) == 6.5

    resolved = resolve_tuning_backup(restored_latest.name)
    assert resolved.resolve() == restored_latest.resolve()
