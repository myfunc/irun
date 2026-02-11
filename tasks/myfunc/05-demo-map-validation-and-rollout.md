# Scope 05: Demo Map Validation and Rollout

Status: `completed (no-go recommendation published)`

## Problem
- The new architecture needs a controlled rollout baseline.
- We need confidence that `demo.map` and legacy imported maps behave consistently.

## Outcome
- A documented validation program proving readiness for default rollout.

## In Scope
- Establish `demo.map` as the primary acceptance map.
- Add a secondary imported-map validation set (at least one legacy map).
- Define rollout gates for:
  - runtime world visuals (sky/fog/lights),
  - launcher/runflow UX,
  - command bus and MCP live operations,
  - loading performance targets.
- Add regression checklist and smoke automation entry points.

## Out Of Scope
- Large content migration campaign for all historical maps.
- Public release packaging workflow redesign.

## Dependencies
- `tasks/myfunc/02-launcher-and-runflow-redesign.md`
- `tasks/myfunc/03-loading-performance-program.md`
- `tasks/myfunc/04-console-command-bus-and-mcp-realtime.md`

## Implementation Plan
1. Freeze acceptance scenarios and target metrics.
2. Build repeatable test script for `demo.map`.
3. Run cross-path checks (runtime source-map path, packed/baked artifact paths, imported map).
4. Record failures and patch in focused follow-ups.
5. Produce rollout recommendation document.

## Acceptance Criteria
- `demo.map` passes visual, UX, MCP, and performance checks.
- Legacy imported map passes fallback behavior checks.
- Known issues list exists with severity and owners.
- Clear go/no-go recommendation published.

## Risks
- Legacy map variance may require per-map compatibility exceptions.
- UX acceptance can fail despite technical correctness.

## Validation
- Manual QA checklist plus scripted smoke path.
- Attach timing and frame-time reports to final scope note.

## Progress Notes (2026-02-10)
- Added Scope 05 rollout automation entry point: `apps/ivan/tools/scope05_rollout_validation.py`.
  - Establishes `demo.map` as acceptance baseline.
  - Builds baked demo artifact for cross-path checks: `.tmp/scope05/demo/demo-scope05.irunmap`.
  - Validates cross-path smoke sequence:
    - runtime source-map launch path (`demo.map`),
    - generated baked `.irunmap` runtime path,
    - imported map path (auto-picks first available imported candidate).
  - Runs launcher/runflow and command-bus regression tests and emits gate verdict JSON.
- Added Scope 05 QA rollout document: `docs/qa/demo-map-rollout-scope05.md`.
  - Defines rollout gates (runtime visuals, launcher UX, command bus/MCP, performance).
  - Adds regression checklist and repeatable smoke/test entry points.
  - Captures known issues with severity + owners.
  - Publishes go/no-go recommendation and release exit criteria.
- Validation evidence produced under `.tmp/scope05/`:
  - `.tmp/scope05/scope05-validation-20260210T145836Z.json`
  - `.tmp/scope05/demo/demo-scope05.irunmap`
- Current recommendation: **NO-GO**.
  - Runtime/UX/command-contract gates pass.
  - Loading performance gate fails on all current acceptance paths and blocks rollout.
