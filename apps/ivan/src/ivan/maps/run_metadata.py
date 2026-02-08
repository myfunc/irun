from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ivan.maps.bundle_io import run_json_path_for_bundle_ref


@dataclass(frozen=True)
class RunMetadata:
    """
    Optional metadata stored next to a map bundle to control how the game should run that map.

    File: <bundle>/run.json
    """

    mode: str = "free_run"
    mode_config: dict | None = None
    spawn_override: dict | None = None  # {"position":[x,y,z], "yaw":deg}
    lighting: dict | None = None  # {"preset": str, "overrides": {style(str): pattern(str)}}


def load_run_metadata(*, bundle_ref: Path) -> RunMetadata:
    """
    Load per-bundle runtime metadata.

    Storage:
    - directory bundle: <bundle>/run.json
    - packed bundle (.irunmap): <bundle>.run.json (sidecar)
    """

    p = run_json_path_for_bundle_ref(bundle_ref)
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

    lighting = payload.get("lighting")
    if not isinstance(lighting, dict):
        lighting = None

    return RunMetadata(mode=mode, mode_config=mode_config, spawn_override=spawn, lighting=lighting)


def set_run_metadata_lighting(*, bundle_ref: Path, lighting: dict | None) -> None:
    """
    Persist a lighting preset for this bundle in <bundle>/run.json.

    This is intended to be set from the main menu after the user tries a preset.
    """

    p = run_json_path_for_bundle_ref(bundle_ref)
    payload: dict = {}
    if p.exists():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(old, dict):
                payload = dict(old)
        except Exception:
            payload = {}

    if lighting is None:
        payload.pop("lighting", None)
    else:
        payload["lighting"] = dict(lighting)

    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
