from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEMO_SOURCE_MAP = "assets/maps/demo/demo.map"
DEMO_BAKED_OUTPUT = ".tmp/scope05/demo/demo-scope05.irunmap"
IMPORTED_MAP_CANDIDATES = (
    "imported/halflife/valve/surf_ski_4_2",
    "imported/halflife/cstrike/de_rats_zabka",
    "imported/halflife/valve/bounce",
)
LOAD_REPORT_PREFIX = "[IVAN] load report: "


@dataclass(frozen=True)
class GateTargets:
    demo_source_total_ms: float = 2600.0
    demo_baked_total_ms: float = 2600.0
    imported_total_ms: float = 3200.0


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    # <repo>/apps/ivan/tools/scope05_rollout_validation.py
    return Path(__file__).resolve().parents[3]


def _apps_ivan_root() -> Path:
    return _repo_root() / "apps" / "ivan"


def _tmp_output_path() -> Path:
    return _repo_root() / ".tmp" / "scope05" / f"scope05-validation-{_utc_stamp()}.json"


def _map_ref_exists(map_ref: str) -> bool:
    repo = _repo_root()
    app = _apps_ivan_root()
    p = Path(map_ref)
    if p.is_absolute():
        return p.exists()
    candidates = (
        app / map_ref,
        repo / map_ref,
        app / "assets" / map_ref / "map.json",
        app / "assets" / f"{map_ref}.irunmap",
    )
    return any(c.exists() for c in candidates)


def _tail_lines(text: str, limit: int = 25) -> list[str]:
    return (text or "").splitlines()[-max(1, int(limit)) :]


def _run(*, cmd: list[str], cwd: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": int(proc.returncode),
        "elapsed_ms": float(elapsed_ms),
        "stdout_tail": _tail_lines(proc.stdout),
        "stderr_tail": _tail_lines(proc.stderr),
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def _parse_load_report(stdout: str) -> dict[str, Any] | None:
    for line in (stdout or "").splitlines():
        if not line.startswith(LOAD_REPORT_PREFIX):
            continue
        raw = line[len(LOAD_REPORT_PREFIX) :].strip()
        try:
            obj = json.loads(raw)
        except Exception:
            return {"parse_error": "invalid-json", "raw": raw}
        if isinstance(obj, dict):
            return obj
        return {"parse_error": "non-dict-json", "raw": raw}
    return None


def _ensure_demo_baked(*, python_exe: str, repack: bool) -> dict[str, Any]:
    app = _apps_ivan_root()
    baked = _repo_root() / DEMO_BAKED_OUTPUT
    if baked.exists() and not repack:
        return {"status": "ok-existing", "path": str(baked)}
    baked.parent.mkdir(parents=True, exist_ok=True)
    src = app / DEMO_SOURCE_MAP
    cmd = [
        python_exe,
        "tools/pack_map.py",
        "--map",
        str(src),
        "--output",
        str(baked),
        "--profile",
        "prod-baked",
    ]
    out = _run(cmd=cmd, cwd=app)
    out["path"] = str(baked)
    out["status"] = "ok" if out["returncode"] == 0 and baked.exists() else "failed"
    return out


def _run_smoke_case(*, python_exe: str, map_ref: str, case_id: str) -> dict[str, Any]:
    app = _apps_ivan_root()
    cmd = [
        python_exe,
        "-m",
        "ivan",
        "--smoke",
        "--map",
        map_ref,
        "--map-profile",
        "auto",
    ]
    out = _run(cmd=cmd, cwd=app)
    report = _parse_load_report(str(out.get("stdout", "")))
    runtime = report.get("runtime") if isinstance(report, dict) else None
    visuals_ok = bool(
        isinstance(runtime, dict)
        and str(runtime.get("sky_source", "unresolved")) != "unresolved"
        and str(runtime.get("fog_source", "unresolved")) != "unresolved"
    )
    budget_pass = bool(isinstance(report, dict) and report.get("budget_pass") is True)
    total_ms = (
        float(report.get("total_ms", 0.0))
        if isinstance(report, dict) and isinstance(report.get("total_ms"), (float, int))
        else None
    )
    return {
        "case_id": case_id,
        "map_ref": map_ref,
        "command": out["cmd"],
        "returncode": out["returncode"],
        "elapsed_ms": out["elapsed_ms"],
        "stdout_tail": out["stdout_tail"],
        "stderr_tail": out["stderr_tail"],
        "load_report": report,
        "checks": {
            "process_ok": int(out["returncode"]) == 0,
            "has_load_report": isinstance(report, dict),
            "budget_pass": budget_pass,
            "visual_runtime_ok": visuals_ok,
            "total_ms": total_ms,
        },
    }


def _run_pytest(*, python_exe: str, rel_paths: list[str], group: str) -> dict[str, Any]:
    repo = _repo_root()
    cmd = [python_exe, "-m", "pytest", *rel_paths]
    out = _run(cmd=cmd, cwd=repo)
    return {
        "group": group,
        "command": out["cmd"],
        "returncode": out["returncode"],
        "elapsed_ms": out["elapsed_ms"],
        "stdout_tail": out["stdout_tail"],
        "stderr_tail": out["stderr_tail"],
        "ok": int(out["returncode"]) == 0,
    }


def _pick_imported_map() -> str | None:
    for cand in IMPORTED_MAP_CANDIDATES:
        if _map_ref_exists(cand):
            return cand
    return None


def _evaluate_gates(*, smoke_rows: list[dict[str, Any]], launcher_tests: dict[str, Any], command_tests: dict[str, Any], live_mcp: dict[str, Any], targets: GateTargets) -> dict[str, Any]:
    row_by_id = {str(r.get("case_id")): r for r in smoke_rows}

    def _smoke_ok(case_id: str) -> bool:
        row = row_by_id.get(case_id)
        if not isinstance(row, dict):
            return False
        c = row.get("checks")
        if not isinstance(c, dict):
            return False
        return bool(c.get("process_ok") and c.get("has_load_report"))

    def _visual_ok(case_id: str) -> bool:
        row = row_by_id.get(case_id)
        if not isinstance(row, dict):
            return False
        c = row.get("checks")
        return bool(isinstance(c, dict) and c.get("visual_runtime_ok"))

    def _total_within(case_id: str, target_ms: float) -> bool:
        row = row_by_id.get(case_id)
        if not isinstance(row, dict):
            return False
        c = row.get("checks")
        if not isinstance(c, dict):
            return False
        total = c.get("total_ms")
        return isinstance(total, (int, float)) and float(total) <= float(target_ms)

    all_smoke_present = all(_smoke_ok(cid) for cid in ("demo-source", "demo-baked", "imported-map"))
    visuals_gate = all(_visual_ok(cid) for cid in ("demo-source", "demo-baked", "imported-map"))
    launcher_gate = bool(launcher_tests.get("ok"))
    command_gate = bool(command_tests.get("ok"))
    live_mcp_gate = bool(live_mcp.get("ok")) if live_mcp.get("status") == "executed" else False
    loading_targets_gate = (
        _total_within("demo-source", targets.demo_source_total_ms)
        and _total_within("demo-baked", targets.demo_baked_total_ms)
        and _total_within("imported-map", targets.imported_total_ms)
    )

    go = bool(
        all_smoke_present
        and visuals_gate
        and launcher_gate
        and command_gate
        and loading_targets_gate
    )
    if live_mcp.get("status") == "executed":
        go = bool(go and live_mcp_gate)

    return {
        "runtime_world_visuals": {"pass": bool(visuals_gate), "requires": ["demo-source", "demo-baked", "imported-map"]},
        "launcher_runflow_ux": {"pass": bool(launcher_gate), "pytest_group": launcher_tests.get("group")},
        "command_bus_mcp_live_ops": {
            "pass": bool(command_gate and (live_mcp_gate if live_mcp.get("status") == "executed" else True)),
            "typed_command_tests_pass": bool(command_gate),
            "live_mcp_status": str(live_mcp.get("status")),
            "live_mcp_pass": bool(live_mcp_gate) if live_mcp.get("status") == "executed" else None,
        },
        "loading_performance_targets": {
            "pass": bool(loading_targets_gate),
            "targets_ms": {
                "demo-source": float(targets.demo_source_total_ms),
                "demo-baked": float(targets.demo_baked_total_ms),
                "imported-map": float(targets.imported_total_ms),
            },
        },
        "go_recommendation": "go" if go else "no-go",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Scope 05 rollout validator for demo map and imported-map paths.")
    ap.add_argument("--python", default=sys.executable, help="Python executable used for child commands.")
    ap.add_argument("--output", default=str(_tmp_output_path()), help="Validation report output JSON path.")
    ap.add_argument("--repack-demo", action="store_true", help="Force rebuild of baked demo .irunmap artifact.")
    ap.add_argument(
        "--imported-map",
        default="",
        help="Imported map ref (alias/path). Default: first available candidate in imported assets.",
    )
    ap.add_argument("--mcp-live", action="store_true", help="Run live MCP demo command sequence (requires running IVAN client).")
    ap.add_argument("--mcp-host", default="127.0.0.1")
    ap.add_argument("--mcp-port", type=int, default=7779)
    args = ap.parse_args()

    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    imported_ref = str(args.imported_map).strip() or _pick_imported_map()
    if not imported_ref:
        payload = {
            "schema": "ivan.scope05.validation.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "status": "failed-no-imported-map",
            "message": "No imported map found. Provide --imported-map or add an imported bundle.",
            "candidates_checked": list(IMPORTED_MAP_CANDIDATES),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(str(out_path))
        return 2

    bake_info = _ensure_demo_baked(python_exe=str(args.python), repack=bool(args.repack_demo))
    if str(bake_info.get("status")) not in {"ok", "ok-existing"}:
        payload = {
            "schema": "ivan.scope05.validation.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "status": "failed-pack-demo",
            "bake": bake_info,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(str(out_path))
        return 3

    demo_baked_ref = str(bake_info.get("path"))
    smoke_rows = [
        _run_smoke_case(python_exe=str(args.python), case_id="demo-source", map_ref=DEMO_SOURCE_MAP),
        _run_smoke_case(python_exe=str(args.python), case_id="demo-baked", map_ref=demo_baked_ref),
        _run_smoke_case(python_exe=str(args.python), case_id="imported-map", map_ref=str(imported_ref)),
    ]

    launcher_tests = _run_pytest(
        python_exe=str(args.python),
        group="launcher-runflow-ux",
        rel_paths=[
            "apps/launcher/tests/test_runflow.py",
            "apps/launcher/tests/test_commands.py",
        ],
    )
    command_tests = _run_pytest(
        python_exe=str(args.python),
        group="command-bus-and-mcp-contracts",
        rel_paths=[
            "apps/ivan/tests/test_console_command_bus.py",
            "apps/ivan/tests/test_console_ivan_bindings.py",
            "apps/ivan/tests/test_scene_runtime_registry.py",
        ],
    )

    live_mcp: dict[str, Any]
    if args.mcp_live:
        live = _run(
            cmd=[
                str(args.python),
                "apps/ivan/tools/mcp_scope04_demo.py",
                "--host",
                str(args.mcp_host),
                "--port",
                str(int(args.mcp_port)),
            ],
            cwd=_repo_root(),
        )
        live_mcp = {
            "status": "executed",
            "ok": int(live["returncode"]) == 0,
            "command": live["cmd"],
            "returncode": live["returncode"],
            "elapsed_ms": live["elapsed_ms"],
            "stdout_tail": live["stdout_tail"],
            "stderr_tail": live["stderr_tail"],
        }
    else:
        live_mcp = {
            "status": "skipped",
            "ok": None,
            "reason": "Use --mcp-live with a running IVAN client for realtime control validation.",
        }

    targets = GateTargets()
    gates = _evaluate_gates(
        smoke_rows=smoke_rows,
        launcher_tests=launcher_tests,
        command_tests=command_tests,
        live_mcp=live_mcp,
        targets=targets,
    )

    payload = {
        "schema": "ivan.scope05.validation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "repo_root": str(_repo_root()),
        "python": str(args.python),
        "acceptance_map": DEMO_SOURCE_MAP,
        "imported_map_ref": str(imported_ref),
        "baked_demo_artifact": {
            "path": demo_baked_ref,
            "source_map": DEMO_SOURCE_MAP,
            "profile": "prod-baked",
            "pack_status": bake_info.get("status"),
        },
        "smoke_cross_path": smoke_rows,
        "regression_checks": {
            "launcher": launcher_tests,
            "command_bus_mcp_contracts": command_tests,
            "mcp_live": live_mcp,
        },
        "rollout_gates": gates,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
