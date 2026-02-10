from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ivan.physics.tuning import PhysicsTuning
from ivan.state import state_dir


def tuning_backup_dir() -> Path:
    d = state_dir() / "tuning_backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(text: str | None, *, fallback: str, limit: int = 42) -> str:
    raw = str(text or "").strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
            continue
        if ch in (" ", "_", "-", "."):
            if not prev_dash:
                out.append("-")
                prev_dash = True
    token = "".join(out).strip("-")
    if not token:
        token = str(fallback)
    return token[: max(1, int(limit))]


def _clean_snapshot(raw: Any) -> dict[str, float | bool]:
    fields = set(PhysicsTuning.__annotations__.keys())
    out: dict[str, float | bool] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key not in fields:
            continue
        if isinstance(value, bool):
            out[str(key)] = bool(value)
        elif isinstance(value, (int, float)):
            out[str(key)] = float(value)
    return out


def _host_snapshot(host) -> dict[str, float | bool]:
    fn = getattr(host, "_current_tuning_snapshot", None)
    if not callable(fn):
        return {}
    try:
        snap = fn()
    except Exception:
        return {}
    return _clean_snapshot(snap)


def create_tuning_backup(host, *, label: str | None = None, reason: str | None = None) -> Path:
    snapshot = _host_snapshot(host)
    if not snapshot:
        raise ValueError("No active tuning snapshot available for backup")
    now = float(time.time())
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
    profile = str(getattr(host, "_active_profile_name", "") or "").strip()
    file_name = (
        f"{stamp}_{_slug(profile, fallback='profile')}_{_slug(label or reason, fallback='snapshot')}.json"
    )
    out_path = (tuning_backup_dir() / file_name).resolve()
    payload: dict[str, Any] = {
        "format_version": 1,
        "created_at_unix": now,
        "created_at_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "active_profile_name": profile or None,
        "label": str(label or "").strip() or None,
        "reason": str(reason or "").strip() or None,
        "tuning_snapshot": snapshot,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return out_path


def list_tuning_backups(*, limit: int = 20) -> list[Path]:
    try:
        files = [p.resolve() for p in tuning_backup_dir().glob("*.json") if p.is_file()]
    except Exception:
        return []
    files.sort(key=lambda p: float(p.stat().st_mtime), reverse=True)
    max_n = max(1, int(limit))
    return files[:max_n]


def _load_backup_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup payload must be a JSON object")
    return payload


def resolve_tuning_backup(backup_ref: str | None = None) -> Path:
    candidates = list_tuning_backups(limit=500)
    if not candidates:
        raise ValueError("No tuning backups found")
    if not backup_ref:
        return candidates[0]

    ref = str(backup_ref).strip()
    if not ref:
        return candidates[0]

    p = Path(ref).expanduser()
    if p.exists() and p.is_file():
        return p.resolve()

    by_name = (tuning_backup_dir() / ref).resolve()
    if by_name.exists() and by_name.is_file():
        return by_name

    if not ref.lower().endswith(".json"):
        with_ext = (tuning_backup_dir() / f"{ref}.json").resolve()
        if with_ext.exists() and with_ext.is_file():
            return with_ext

    needle = ref.lower()
    for pth in candidates:
        if needle in pth.name.lower():
            return pth
    raise ValueError(f'Backup not found for ref "{ref}"')


def restore_tuning_backup(host, *, backup_ref: str | None = None) -> Path:
    path = resolve_tuning_backup(backup_ref)
    payload = _load_backup_payload(path)
    snapshot = _clean_snapshot(payload.get("tuning_snapshot"))
    if not snapshot:
        raise ValueError(f"Backup has no valid tuning snapshot: {path.name}")

    target_profile = payload.get("active_profile_name")
    profiles = getattr(host, "_profiles", None)
    active = str(getattr(host, "_active_profile_name", "") or "")
    if isinstance(target_profile, str) and target_profile and isinstance(profiles, dict) and target_profile in profiles and target_profile != active:
        apply_profile = getattr(host, "_apply_profile", None)
        if callable(apply_profile):
            apply_profile(target_profile)

    apply_snapshot = getattr(host, "_apply_profile_snapshot", None)
    if not callable(apply_snapshot):
        raise ValueError("Host does not expose _apply_profile_snapshot")
    apply_snapshot(dict(snapshot), persist=False)

    profiles = getattr(host, "_profiles", None)
    active = str(getattr(host, "_active_profile_name", "") or "")
    if isinstance(profiles, dict) and active:
        profiles[active] = dict(snapshot)

    persist_fn = getattr(host, "_persist_profiles_state", None)
    if callable(persist_fn):
        persist_fn()
    return path


def backup_metadata(path: Path) -> dict[str, Any]:
    payload = _load_backup_payload(Path(path))
    return {
        "path": str(Path(path).resolve()),
        "created_at_unix": float(payload.get("created_at_unix") or 0.0),
        "active_profile_name": payload.get("active_profile_name"),
        "label": payload.get("label"),
        "reason": payload.get("reason"),
        "field_count": len(_clean_snapshot(payload.get("tuning_snapshot"))),
    }


__all__ = [
    "backup_metadata",
    "create_tuning_backup",
    "list_tuning_backups",
    "resolve_tuning_backup",
    "restore_tuning_backup",
    "tuning_backup_dir",
]
