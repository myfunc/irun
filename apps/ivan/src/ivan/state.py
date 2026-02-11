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
    last_net_host: str | None = None
    last_net_port: int | None = None
    tuning_overrides: dict[str, float | bool] = field(default_factory=dict)
    # Local-only time-trial info keyed by map_id.
    time_trials: dict[str, dict] | None = None
    tuning_profiles: dict[str, dict[str, float | bool]] = field(default_factory=dict)
    active_tuning_profile: str | None = None
    # Display / video settings (persisted across sessions).
    fullscreen: bool = False
    window_width: int = 1280
    window_height: int = 720
    # Audio settings.
    master_volume: float = 0.85
    sfx_volume: float = 0.90


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
    lnh = payload.get("last_net_host")
    lnp = payload.get("last_net_port")
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
    tt = payload.get("time_trials")

    tuning_profiles: dict[str, dict[str, float | bool]] = {}
    raw_profiles = payload.get("tuning_profiles")
    if isinstance(raw_profiles, dict):
        for profile_name, profile_vals in raw_profiles.items():
            if not isinstance(profile_name, str) or not profile_name.strip():
                continue
            if not isinstance(profile_vals, dict):
                continue
            cleaned: dict[str, float | bool] = {}
            for key, value in profile_vals.items():
                if not isinstance(key, str) or not key.strip():
                    continue
                if isinstance(value, bool):
                    cleaned[key] = value
                elif isinstance(value, (int, float)):
                    cleaned[key] = float(value)
            tuning_profiles[profile_name] = cleaned

    active_tuning_profile = payload.get("active_tuning_profile")
    active_name = str(active_tuning_profile) if isinstance(active_tuning_profile, str) and active_tuning_profile.strip() else None

    fs = payload.get("fullscreen")
    ww = payload.get("window_width")
    wh = payload.get("window_height")
    mv = payload.get("master_volume")
    sv = payload.get("sfx_volume")

    return IvanState(
        last_map_json=str(lm) if isinstance(lm, str) and lm.strip() else None,
        last_game_root=str(gr) if isinstance(gr, str) and gr.strip() else None,
        last_mod=str(mod) if isinstance(mod, str) and mod.strip() else None,
        last_net_host=str(lnh) if isinstance(lnh, str) and lnh.strip() else None,
        last_net_port=int(lnp) if isinstance(lnp, int) and 1 <= int(lnp) <= 65535 else None,
        tuning_overrides=tuning_overrides,
        time_trials=dict(tt) if isinstance(tt, dict) else None,
        tuning_profiles=tuning_profiles,
        active_tuning_profile=active_name,
        fullscreen=bool(fs) if isinstance(fs, bool) else False,
        window_width=int(ww) if isinstance(ww, int) and 320 <= int(ww) <= 7680 else 1280,
        window_height=int(wh) if isinstance(wh, int) and 240 <= int(wh) <= 4320 else 720,
        master_volume=max(0.0, min(1.0, float(mv))) if isinstance(mv, (int, float)) else 0.85,
        sfx_volume=max(0.0, min(1.0, float(sv))) if isinstance(sv, (int, float)) else 0.90,
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
                "last_net_host": state.last_net_host,
                "last_net_port": int(state.last_net_port) if isinstance(state.last_net_port, int) else None,
                "tuning_overrides": state.tuning_overrides,
                "time_trials": state.time_trials,
                "tuning_profiles": state.tuning_profiles,
                "active_tuning_profile": state.active_tuning_profile,
                "fullscreen": state.fullscreen,
                "window_width": int(state.window_width),
                "window_height": int(state.window_height),
                "master_volume": float(state.master_volume),
                "sfx_volume": float(state.sfx_volume),
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
    last_net_host: str | None = None,
    last_net_port: int | None = None,
    tuning_overrides: dict[str, float | bool] | None = None,
    tuning_profiles: dict[str, dict[str, float | bool]] | None = None,
    active_tuning_profile: str | None = None,
    fullscreen: bool | None = None,
    window_width: int | None = None,
    window_height: int | None = None,
    master_volume: float | None = None,
    sfx_volume: float | None = None,
) -> None:
    s = load_state()
    merged_tuning = dict(s.tuning_overrides)
    if tuning_overrides is not None:
        merged_tuning.update(tuning_overrides)
    merged_profiles = dict(s.tuning_profiles)
    if tuning_profiles is not None:
        merged_profiles = dict(tuning_profiles)
    final_active_profile = active_tuning_profile if active_tuning_profile is not None else s.active_tuning_profile
    save_state(
        IvanState(
            last_map_json=last_map_json if last_map_json is not None else s.last_map_json,
            last_game_root=last_game_root if last_game_root is not None else s.last_game_root,
            last_mod=last_mod if last_mod is not None else s.last_mod,
            last_net_host=last_net_host if last_net_host is not None else s.last_net_host,
            last_net_port=int(last_net_port) if isinstance(last_net_port, int) else s.last_net_port,
            tuning_overrides=merged_tuning,
            time_trials=s.time_trials,
            tuning_profiles=merged_profiles,
            active_tuning_profile=final_active_profile,
            fullscreen=bool(fullscreen) if fullscreen is not None else s.fullscreen,
            window_width=int(window_width) if window_width is not None else s.window_width,
            window_height=int(window_height) if window_height is not None else s.window_height,
            master_volume=(
                max(0.0, min(1.0, float(master_volume)))
                if isinstance(master_volume, (int, float))
                else s.master_volume
            ),
            sfx_volume=(
                max(0.0, min(1.0, float(sfx_volume)))
                if isinstance(sfx_volume, (int, float))
                else s.sfx_volume
            ),
        )
    )


def _tt_maps(state: IvanState) -> dict[str, dict]:
    root = state.time_trials if isinstance(state.time_trials, dict) else {}
    maps = root.get("maps")
    if isinstance(maps, dict):
        return maps
    return {}


def get_time_trial_course_override(*, map_id: str) -> dict | None:
    s = load_state()
    maps = _tt_maps(s)
    entry = maps.get(map_id)
    if not isinstance(entry, dict):
        return None
    course = entry.get("course")
    return dict(course) if isinstance(course, dict) else None


def get_time_trial_pb_seconds(*, map_id: str) -> float | None:
    s = load_state()
    maps = _tt_maps(s)
    entry = maps.get(map_id)
    if not isinstance(entry, dict):
        return None
    pb = entry.get("pb_seconds")
    if isinstance(pb, (int, float)) and pb >= 0:
        return float(pb)
    return None


def set_time_trial_course_override(*, map_id: str, course: dict | None) -> None:
    s = load_state()
    root = dict(s.time_trials) if isinstance(s.time_trials, dict) else {}
    maps = dict(root.get("maps")) if isinstance(root.get("maps"), dict) else {}
    entry = dict(maps.get(map_id)) if isinstance(maps.get(map_id), dict) else {}
    if course is None:
        entry.pop("course", None)
    else:
        entry["course"] = dict(course)
    maps[map_id] = entry
    root["maps"] = maps
    save_state(
        IvanState(
            last_map_json=s.last_map_json,
            last_game_root=s.last_game_root,
            last_mod=s.last_mod,
            tuning_overrides=s.tuning_overrides,
            time_trials=root,
            tuning_profiles=s.tuning_profiles,
            active_tuning_profile=s.active_tuning_profile,
            fullscreen=s.fullscreen,
            window_width=s.window_width,
            window_height=s.window_height,
            master_volume=s.master_volume,
            sfx_volume=s.sfx_volume,
        )
    )


def record_time_trial_run(
    *,
    map_id: str,
    seconds: float,
    finished_at: float | None = None,
    leaderboard_size: int = 20,
) -> tuple[float | None, float, tuple[int, int]]:
    """
    Record a finished run.

    Returns (new_pb_or_none, last_seconds, (rank, total_entries)).
    """

    last = max(0.0, float(seconds))
    s = load_state()
    root = dict(s.time_trials) if isinstance(s.time_trials, dict) else {}
    maps = dict(root.get("maps")) if isinstance(root.get("maps"), dict) else {}
    entry = dict(maps.get(map_id)) if isinstance(maps.get(map_id), dict) else {}

    pb = entry.get("pb_seconds")
    pb_f = float(pb) if isinstance(pb, (int, float)) and pb >= 0 else None

    new_pb: float | None = None
    if pb_f is None or last < pb_f:
        entry["pb_seconds"] = last
        new_pb = last

    entry["last_seconds"] = last

    # Local leaderboard: list of best times (seconds ascending).
    lb = entry.get("leaderboard")
    runs: list[dict] = []
    if isinstance(lb, list):
        for it in lb:
            if isinstance(it, dict) and isinstance(it.get("seconds"), (int, float)):
                sec = float(it["seconds"])
                if sec >= 0:
                    runs.append({"seconds": sec, "finished_at": it.get("finished_at")})
    runs.append({"seconds": last, "finished_at": float(finished_at) if isinstance(finished_at, (int, float)) else None})
    runs.sort(key=lambda r: float(r.get("seconds", 1e18)))
    if leaderboard_size > 0:
        runs = runs[: int(leaderboard_size)]
    entry["leaderboard"] = runs

    # Rank of this run within the kept leaderboard (1-based).
    rank = 1
    for i, it in enumerate(runs):
        try:
            if float(it.get("seconds")) == last:
                rank = i + 1
                break
        except Exception:
            pass
    rank_info = (rank, len(runs))

    maps[map_id] = entry
    root["maps"] = maps
    save_state(
        IvanState(
            last_map_json=s.last_map_json,
            last_game_root=s.last_game_root,
            last_mod=s.last_mod,
            tuning_overrides=s.tuning_overrides,
            time_trials=root,
            tuning_profiles=s.tuning_profiles,
            active_tuning_profile=s.active_tuning_profile,
            fullscreen=s.fullscreen,
            window_width=s.window_width,
            window_height=s.window_height,
            master_volume=s.master_volume,
            sfx_volume=s.sfx_volume,
        )
    )
    return (new_pb, last, rank_info)


def resolve_map_json(map_json: str) -> Path | None:
    """
    Resolve a runnable map JSON path similarly to `WorldScene` resolution rules.

    Supported:
    - absolute path to `map.json` (or `*_map.json`)
    - absolute/relative path to a packed bundle `.irunmap`
    - absolute/relative path to a ``.map`` file (TrenchBroom)
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
        suf = c.suffix.lower()
        if suf not in (".json", ".irunmap", ".map"):
            expanded.append(c / "map.json")
            # Allow passing a suffix-less alias for packed bundles, e.g. imported/.../bounce -> bounce.irunmap
            try:
                expanded.append(c.with_suffix(".irunmap"))
            except Exception:
                pass

    for c in expanded:
        if c.exists() and c.is_file():
            return c
    return None
