from __future__ import annotations

import json
from pathlib import Path

from ivan.maps.run_metadata import load_run_metadata


def test_load_run_metadata_defaults_when_missing(tmp_path: Path) -> None:
    md = load_run_metadata(bundle_ref=tmp_path)
    assert md.mode == "free_run"
    assert md.mode_config is None
    assert md.spawn_override is None


def test_load_run_metadata_parses_fields(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "mode": "time_trial",
                "config": {"start_aabb": {"min": [0, 0, 0], "max": [1, 1, 1]}},
                "spawn": {"position": [10, 20, 3], "yaw": 90},
            }
        ),
        encoding="utf-8",
    )
    md = load_run_metadata(bundle_ref=tmp_path)
    assert md.mode == "time_trial"
    assert isinstance(md.mode_config, dict)
    assert md.mode_config["start_aabb"]["min"] == [0, 0, 0]
    assert md.spawn_override["position"] == [10, 20, 3]
    assert md.spawn_override["yaw"] == 90
