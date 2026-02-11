from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MAPS = (
    "assets/maps/demo/demo.map",
    "assets/maps/light-test/light-test.map",
    "imported/halflife/valve/bounce",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_repo_root() -> Path:
    # <repo>/apps/ivan/tools/loading_benchmark.py -> repo root is 3 parents up.
    return Path(__file__).resolve().parents[3]


def _default_output_path() -> Path:
    root = _resolve_repo_root()
    return root / ".tmp" / "loading" / f"load-benchmark-{_utc_stamp()}.json"


def run_case(*, repo_root: Path, python_exe: str, map_ref: str, map_profile: str, repeats: int) -> list[dict]:
    out: list[dict] = []
    for i in range(max(1, int(repeats))):
        cmd = [
            python_exe,
            "-m",
            "ivan",
            "--smoke",
            "--map",
            str(map_ref),
            "--map-profile",
            str(map_profile),
        ]
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root / "apps" / "ivan"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        report = None
        for ln in (proc.stdout or "").splitlines():
            prefix = "[IVAN] load report: "
            if ln.startswith(prefix):
                raw = ln[len(prefix) :].strip()
                try:
                    report = json.loads(raw)
                except Exception:
                    report = {"parse_error": "invalid-json", "raw": raw}
                break
        out.append(
            {
                "map_ref": str(map_ref),
                "repeat_index": int(i),
                "cmd": cmd,
                "returncode": int(proc.returncode),
                "wall_ms": float(elapsed_ms),
                "load_report": report,
                "stdout_tail": (proc.stdout or "").splitlines()[-20:],
                "stderr_tail": (proc.stderr or "").splitlines()[-20:],
            }
        )
    return out


def _map_candidate_paths(*, repo_root: Path, map_ref: str) -> list[Path]:
    p = Path(str(map_ref))
    app_root = repo_root / "apps" / "ivan"
    if p.is_absolute():
        return [p]
    return [
        app_root / p,
        repo_root / p,
        app_root / "assets" / p / "map.json",
        app_root / "assets" / f"{str(p)}.irunmap",
    ]


def _map_available(*, repo_root: Path, map_ref: str) -> bool:
    for p in _map_candidate_paths(repo_root=repo_root, map_ref=map_ref):
        if p.exists():
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run smoke map-load benchmark and collect structured load reports.")
    parser.add_argument(
        "--output",
        default=str(_default_output_path()),
        help="Output JSON path. Defaults to <repo>/.tmp/loading/load-benchmark-<utc>.json",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter).",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        help="Map reference to benchmark. Repeat flag for multiple maps.",
    )
    parser.add_argument(
        "--map-profile",
        default="auto",
        help='Map profile passed to IVAN (default: "auto").',
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=2,
        help="Runs per map (default: 2 to capture cold/warm behavior).",
    )
    args = parser.parse_args()

    repo_root = _resolve_repo_root()
    maps = tuple(args.map) if args.map else DEFAULT_MAPS

    rows: list[dict] = []
    for m in maps:
        if not _map_available(repo_root=repo_root, map_ref=str(m)):
            rows.append(
                {
                    "map_ref": str(m),
                    "repeat_index": 0,
                    "returncode": None,
                    "status": "skipped-missing-map",
                    "load_report": None,
                    "wall_ms": 0.0,
                    "cmd": None,
                    "stdout_tail": [],
                    "stderr_tail": [],
                }
            )
            continue
        rows.extend(
            run_case(
                repo_root=repo_root,
                python_exe=str(args.python),
                map_ref=str(m),
                map_profile=str(args.map_profile),
                repeats=int(args.repeats),
            )
        )

    payload = {
        "schema": "ivan.loading.benchmark.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "repo_root": str(repo_root),
        "python": str(args.python),
        "map_profile": str(args.map_profile),
        "repeats": int(args.repeats),
        "maps": [str(m) for m in maps],
        "runs": rows,
    }
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
