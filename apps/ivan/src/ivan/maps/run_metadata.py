from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ivan.maps.bundle_io import run_json_path_for_bundle_ref


@dataclass(frozen=True)
class RunMetadata:
    """
    Optional metadata stored next to a map bundle to control how the game should run that map.

    File: <bundle>/run.json or <map>.run.json for .map files
    """

    mode: str = "free_run"
    mode_config: dict | None = None
    spawn_override: dict | None = None  # {"position":[x,y,z], "yaw":deg}
    lighting: dict | None = None  # {"preset": str, "overrides": {style(str): pattern(str)}}
    visibility: dict | None = None  # {"enabled": bool, "mode": "auto"|"goldsrc_pvs", "build_cache": bool}
    fog: dict | None = None  # {"enabled": bool, "start": float, "end": float, "color": [r,g,b]}


def load_run_metadata(*, bundle_ref: Path | None) -> RunMetadata:
    """
    Load per-bundle runtime metadata.

    Storage:
    - directory bundle: <bundle>/run.json
    - packed bundle (.irunmap): <bundle>.run.json (sidecar)
    - .map file: <map>.run.json (sidecar)
    """

    if bundle_ref is None:
        return RunMetadata()
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

    visibility = payload.get("visibility")
    if not isinstance(visibility, dict):
        visibility = None

    fog = payload.get("fog")
    if not isinstance(fog, dict):
        fog = None

    return RunMetadata(
        mode=mode,
        mode_config=mode_config,
        spawn_override=spawn,
        lighting=lighting,
        visibility=visibility,
        fog=fog,
    )


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


def set_run_metadata_visibility(*, bundle_ref: Path, visibility: dict | None) -> None:
    """
    Persist visibility config for this bundle in <bundle>/run.json.
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

    if visibility is None:
        payload.pop("visibility", None)
    else:
        payload["visibility"] = dict(visibility)

    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
