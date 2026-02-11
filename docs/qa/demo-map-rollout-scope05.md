# Demo Map Rollout Validation (Scope 05)

Status: `active (initial evidence captured)`

## Acceptance Baseline
- Primary acceptance map: `apps/ivan/assets/maps/demo/demo.map`.
- Cross-path acceptance artifact for packed path: `.tmp/scope05/demo/demo-scope05.irunmap` (generated from `demo.map` with `pack_map.py --profile prod-baked`).
- Imported-map validation set (at least one required):
  - primary: `imported/halflife/valve/surf_ski_4_2`
  - secondary fallback: `imported/halflife/cstrike/de_rats_zabka`

## Rollout Gates

### Gate A: Runtime World Visuals (sky/fog/lights)
- Required checks:
  - all three smoke paths emit `[IVAN] world runtime` and `[IVAN] load report`.
  - `runtime.sky_source != unresolved`.
  - `runtime.fog_source != unresolved`.
  - direct-map path reports runtime-lighting (`runtime_only_lighting=true` expected for `demo.map` source path).
  - packed path reports runtime-lighting when lightmaps are absent; imported path reports baked-lightmaps when bundle lightmaps are present.
- Current state (2026-02-10): **pass**.

### Gate B: Launcher / Runflow UX
- Required checks:
  - `apps/launcher/tests/test_runflow.py`
  - `apps/launcher/tests/test_commands.py`
- Current state (2026-02-10): **pass**.

### Gate C: Command Bus + MCP Live Operations
- Required checks:
  - typed command bus and runtime bindings:
    - `apps/ivan/tests/test_console_command_bus.py`
    - `apps/ivan/tests/test_console_ivan_bindings.py`
    - `apps/ivan/tests/test_scene_runtime_registry.py`
  - MCP live sequence (when a live IVAN process is running):
    - `python apps/ivan/tools/mcp_scope04_demo.py --host 127.0.0.1 --port 7779`
- Current state (2026-02-10):
  - typed command tests: **pass**
  - MCP live sequence: **not executed in this smoke pass** (manual/live gate still required before rollout approval).

### Gate D: Loading Performance Targets
- Targets are validated by `apps/ivan/tools/scope05_rollout_validation.py`:
  - `demo-source` first-frame <= `2600 ms`
  - `demo-packed` first-frame <= `2600 ms`
  - `imported-map` first-frame <= `3200 ms`
- Current state (2026-02-10): **fail** (see measurements below).

## Regression Checklist
- [x] `demo.map` source path (`Play Map` equivalent) smoke boots and emits runtime + load report.
- [x] packed demo path (`Pack` equivalent) smoke boots and emits runtime + load report.
- [x] imported map path smoke boots and emits runtime + load report.
- [x] launcher runflow tests pass.
- [x] command bus contract tests pass.
- [ ] MCP live command sequence executed against a running client and archived.
- [x] known issues list captured with severity + owner.
- [x] explicit go/no-go recommendation published.

## Smoke Automation Entry Points

### 1) Full Scope 05 validation
Run from repo root:

```bash
apps/ivan/.venv/Scripts/python apps/ivan/tools/scope05_rollout_validation.py
```

Output:
- `.tmp/scope05/scope05-validation-<utc>.json`

What this script does:
- builds `.tmp/scope05/demo/demo-scope05.irunmap` from `demo.map` if needed;
- runs cross-path smoke checks (`demo.map`, packed demo artifact, imported map);
- runs launcher + command-bus regression test groups;
- evaluates rollout gates and emits `go` or `no-go`.

### 2) Optional live MCP check (requires running IVAN client)
```bash
apps/ivan/.venv/Scripts/python apps/ivan/tools/scope05_rollout_validation.py --mcp-live
```

or run only the MCP command sequence:

```bash
apps/ivan/.venv/Scripts/python apps/ivan/tools/mcp_scope04_demo.py --host 127.0.0.1 --port 7779
```

## Latest Evidence (2026-02-10)
- Artifact: `.tmp/scope05/scope05-validation-20260210T145836Z.json`
- Packed demo artifact: `.tmp/scope05/demo/demo-scope05.irunmap`

Measured first-frame load (`total_ms`):
- `demo-source`: `17456.17 ms` (target `2600 ms`) -> fail
- `demo-packed`: `3964.91 ms` (target `2600 ms`) -> fail
- `imported-map` (`surf_ski_4_2`): `8598.38 ms` (target `3200 ms`) -> fail

Supporting regressions:
- launcher tests: `7 passed`
- command-bus tests: `10 passed`

## Known Issues
- **S1 / blocker** - First-frame load exceeds rollout targets on all acceptance paths.
  - Evidence: Scope 05 artifact above (`rollout_gates.loading_performance_targets.pass=false`).
  - Owner: Runtime loading/perf stream (Scope 03 follow-up).
- **S2 / caution** - `net.connect` refusal appears in smoke stderr even in offline validation runs.
  - Evidence: repeated `[ERROR] net.connect: [WinError 10061] ... refused it`.
  - Impact: noisy logs and potential false-positive concern during QA triage.
  - Owner: Runtime networking/bootstrap stream.
- **S2 / release-caution** - MCP live sequence was not executed in this headless smoke pass.
  - Evidence: `rollout_gates.command_bus_mcp_live_ops.live_mcp_status=skipped`.
  - Owner: Tools/MCP integration stream (requires a live interactive validation window).

## Recommendation
- **Current recommendation: NO-GO** for default rollout.
- Exit criteria before switching to go:
  1. loading gate meets thresholds on `demo-source`, `demo-packed`, and one imported map path;
  2. live MCP sequence executed and archived in a follow-up Scope 05 artifact;
  3. no new S1 issues opened by rerun.
