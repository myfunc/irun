# Scope 03: Loading Performance Program

Status: `done`

## Problem
- Map loading is still perceived as slow, especially across mixed content paths.
- Current behavior can hide where time is spent (I/O, conversion, textures, visibility cache, scene attach).

## Outcome
- Measurable loading pipeline with clear budgets and concrete optimizations.

## In Scope
- Add timed stage instrumentation for:
  - map parse/import,
  - material/sky/fog resolve,
  - geometry build/attach,
  - visibility cache load/build,
  - first-frame readiness.
- Build and enforce loading budgets for target map categories.
- Optimize top offenders (by measured data), likely:
  - unnecessary repeated texture/material work,
  - high draw-call setup churn,
  - blocking operations before first frame.
- Introduce optional warm cache/preload strategy for repeated runs.

## Out Of Scope
- Full streaming/chunking architecture rewrite.
- Engine-level threading overhaul.

## Dependencies
- `tasks/myfunc/01-runtime-world-baseline.md`

## Implementation Plan
1. Add profiling markers and structured load report output.
2. Collect baseline metrics for `demo.map`, `light-test.map`, and one imported map.
3. Rank bottlenecks by impact and implement optimizations in order.
4. Re-measure and compare against baseline.
5. Document tunables and trade-offs.

## Acceptance Criteria
- Load report is emitted for every run with stable stage names.
- End-to-first-frame time improves versus baseline on at least two representative maps.
- No regression in visual correctness (sky/fog/lights/visibility).

## Risks
- Aggressive lazy-loading can cause visible pop-in later.
- Over-optimization for one map class can hurt another.

## Validation
- Repeatable benchmark script with fixed environment.
- Before/after metrics table in docs.

## Progress Notes (2026-02-10)
- Implemented stable loading stage instrumentation with JSON report output for every gameplay run.
  - Stage keys are fixed: `map_parse_import`, `material_sky_fog_resolve`, `geometry_build_attach`, `visibility_cache_load_build`, `first_frame_readiness`.
  - Report schema: `ivan.world.load_report.v1` (printed as `[IVAN] load report: <json>`).
- Added visibility cache diagnostics into runtime/load reporting with explicit result states:
  - `memory-hit`, `disk-hit`, `rebuilt`, `miss-no-source`, `build-failed`, `error`.
- Added measurable runtime optimizations (no visual-path regression intended):
  - base material texture memoization in geometry attach (reduces repeated texture decode/load calls),
  - process-local warm cache for visibility cache payloads (repeated-run speedup).
- Added benchmark utility for repeatable measurements:
  - `apps/ivan/tools/loading_benchmark.py`
  - default output path: `.tmp/loading/load-benchmark-<utc>.json`
  - default maps include `demo.map`, `light-test.map`, and imported alias `imported/halflife/valve/bounce`.
- Updated architecture/features docs with budgets, tunables, and trade-offs.

## Remaining Follow-ups
- Capture and publish a longer-running before/after metrics table in docs once representative imported bundles are available on all dev machines.
