from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunMetadata:
    """
    Optional metadata stored next to a map bundle to control how the game should run that map.

    File: <bundle>/run.json
    """

    mode: str = "free_run"
    mode_config: dict | None = None
    spawn_override: dict | None = None  # {"position":[x,y,z], "yaw":deg}


def load_run_metadata(*, bundle_root: Path) -> RunMetadata:
    p = bundle_root / "run.json"
    if not p.exists() or not p.is_file():
        return RunMetadata()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return RunMetadata()
    if not isinstance(payload, dict):
        return RunMetadata()

    mode = payload.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        mode = "free_run"
    mode = mode.strip()

    mode_config = payload.get("config")
    if not isinstance(mode_config, dict):
        mode_config = None

    spawn = payload.get("spawn")
    if not isinstance(spawn, dict):
        spawn = None

    return RunMetadata(mode=mode, mode_config=mode_config, spawn_override=spawn)

