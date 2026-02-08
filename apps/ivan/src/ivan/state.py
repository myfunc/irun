from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from ivan.paths import app_root as ivan_app_root


@dataclass(frozen=True)
class IvanState:
    last_map_json: str | None = None
    last_game_root: str | None = None
    last_mod: str | None = None
    tuning_overrides: dict[str, float | bool] = field(default_factory=dict)


def state_dir() -> Path:
    """
    Directory for small persistent user state.

    Override for tests/dev via `IRUN_IVAN_STATE_DIR`.
    """

    override = os.environ.get("IRUN_IVAN_STATE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".irun" / "ivan"


def state_path() -> Path:
    return state_dir() / "state.json"


def load_state() -> IvanState:
    p = state_path()
    if not p.exists():
        return IvanState()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return IvanState()

    if not isinstance(payload, dict):
        return IvanState()
    lm = payload.get("last_map_json")
    gr = payload.get("last_game_root")
    mod = payload.get("last_mod")
    raw_tuning = payload.get("tuning_overrides")
    tuning_overrides: dict[str, float | bool] = {}
    if isinstance(raw_tuning, dict):
        for key, value in raw_tuning.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if isinstance(value, bool):
                tuning_overrides[key] = value
                continue
            if isinstance(value, (int, float)):
                tuning_overrides[key] = float(value)
    return IvanState(
        last_map_json=str(lm) if isinstance(lm, str) and lm.strip() else None,
        last_game_root=str(gr) if isinstance(gr, str) and gr.strip() else None,
        last_mod=str(mod) if isinstance(mod, str) and mod.strip() else None,
        tuning_overrides=tuning_overrides,
    )


def save_state(state: IvanState) -> None:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = state_path()
    # Use a unique tmp name to avoid cross-process races (e.g. parallel smoke runs).
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    tmp.write_text(
        json.dumps(
            {
                "last_map_json": state.last_map_json,
                "last_game_root": state.last_game_root,
                "last_mod": state.last_mod,
                "tuning_overrides": state.tuning_overrides,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)


def update_state(
    *,
    last_map_json: str | None = None,
    last_game_root: str | None = None,
    last_mod: str | None = None,
    tuning_overrides: dict[str, float | bool] | None = None,
) -> None:
    s = load_state()
    merged_tuning = dict(s.tuning_overrides)
    if tuning_overrides is not None:
        merged_tuning.update(tuning_overrides)
    save_state(
        IvanState(
            last_map_json=last_map_json if last_map_json is not None else s.last_map_json,
            last_game_root=last_game_root if last_game_root is not None else s.last_game_root,
            last_mod=last_mod if last_mod is not None else s.last_mod,
            tuning_overrides=merged_tuning,
        )
    )


def resolve_map_json(map_json: str) -> Path | None:
    """
    Resolve a runnable map JSON path similarly to `WorldScene` resolution rules.

    Supported:
    - absolute path to `map.json` (or `*_map.json`)
    - relative path (cwd first, then apps/ivan/assets/)
    - assets alias directory, e.g. `imported/halflife/valve/bounce` (implies `<alias>/map.json`)
    """

    p = Path(map_json)
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append((Path.cwd() / p).resolve())
        candidates.append((ivan_app_root() / "assets" / p).resolve())

    expanded: list[Path] = []
    for c in candidates:
        expanded.append(c)
        if c.suffix.lower() != ".json":
            expanded.append(c / "map.json")

    for c in expanded:
        if c.exists() and c.is_file():
            return c
    return None
