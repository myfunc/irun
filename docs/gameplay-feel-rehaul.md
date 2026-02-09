# Gameplay Feel Rehaul Plan

## Goal
Bring IVAN movement/camera feel closer to top-tier movement games (including Bloodthief-style smoothness targets) while preserving IVAN's deterministic tick model and live tuning workflow.

## Success Criteria
- Input feels immediate and predictable:
  - Low perceived delay from key/mouse action to motion response.
  - Consistent jump behavior (buffer/coyote windows perform as configured).
- Movement continuity:
  - Reduced speed loss on common transitions (landing, stair/step, slope handoff).
  - Reduced ground-state flicker on uneven geometry.
- Camera readability and comfort:
  - Lower camera jerk on high-speed movement and reconciliation.
  - Camera motion supports aiming/pathing and does not obscure velocity cues.
- Tooling:
  - Measurable feel metrics available in-game and exportable for tune sessions.
  - Repeatable tune scenarios and acceptance checklist for each pass.

## Constraints
- Keep movement simulation authoritative at fixed `60 Hz`.
- New gameplay parameters must be globally configurable and exposed in debug/admin UI.
- Prefer incremental, reviewable slices; avoid one large rewrite.
- Preserve existing map import/runtime compatibility.

## Workstreams
1. Instrumentation and baselines
2. Camera pipeline rework
3. Ground/air transition and step/slope stability
4. Acceleration/friction/air-control polish
5. QA harness, profile packaging, and rollout

## Agent Execution Model
Use parallel agents with strict ownership boundaries:

- Agent A (Telemetry/QA):
  - Implements runtime feel metrics collection and logging/export.
  - Adds repeatable benchmark scenarios and acceptance scripts.
- Agent B (Camera):
  - Implements render camera shell improvements (smoothing, FOV/tilt policy).
  - Owns camera tuning defaults and profile deltas.
- Agent C (Movement Core):
  - Implements controller stability passes (step/slope/transition logic).
  - Owns friction/accel model refinements and invariants.
- Agent D (Integration/Docs):
  - Merges profiles, updates docs, verifies debug menu exposure.
  - Tracks milestone status, risks, and rollback notes.

## Phase Plan

### Phase 0: Baseline and Instrumentation (Start Here)
Status: `IN PROGRESS`

Deliverables:
- Runtime feel metrics aggregator:
  - jump input -> takeoff success window
  - landing horizontal speed retention/loss
  - ground-state transition flicker count
  - camera jerk signal (linear/angular acceleration proxies)
- F2 overlay shows rolling feel metrics summary.
- Optional text export path for benchmark sessions.

Acceptance:
- Metrics update during normal gameplay.
- No movement behavior changes required in this phase.
- Smoke run remains stable.

### Phase 1: Camera Feel Rehaul
Status: `PENDING`

Deliverables:
- Decoupled camera render shell with critically-damped smoothing policy.
- Speed-aware but bounded camera effects:
  - FOV response curve
  - landing response (micro-tilt/bob)
  - optional strafe lean with strict caps
- Config exposure in debug/admin UI (all new camera params).

Acceptance:
- Reduced camera jerk metric vs Phase 0 baseline on same route.
- No visible camera pop on respawn, pause/unpause, replay start/end.

### Phase 2: Movement Stability Rehaul
Status: `PENDING`

Deliverables:
- Step-up/step-down robustness pass:
  - fewer false-ground/fall toggles
  - stable traversal over stair-like geometry
- Slope transition pass:
  - smoother slope entry/exit with controlled momentum preservation
- Ground/air handoff cleanup:
  - coyote/jump-buffer behavior verified against configured windows

Acceptance:
- Ground flicker metric reduced vs baseline.
- Landing speed retention improves in benchmark routes.

### Phase 3: Accel/Friction Polish
Status: `PENDING`

Deliverables:
- Re-tuned acceleration/friction/air-control interactions with explicit invariants.
- Counter-strafe and surf edge-case cleanup.
- New curated profile:
  - `bloodthief_inspired` (working name)

Acceptance:
- Route consistency and speed retention improved across 3 benchmark maps.
- No major regressions in existing profiles (`surf_bhop_c2`, etc.).

### Phase 4: QA, Rollout, and Guardrails
Status: `PENDING`

Deliverables:
- Benchmark checklist and acceptance matrix in docs.
- Regression tests for critical movement/camera invariants.
- Final profile defaults recommendation and rollback strategy.

Acceptance:
- All milestone checks pass.
- Team agrees on default profile behavior.

## Benchmark Protocol
- Keep one canonical route set:
  - Route A: flat strafe and jump chain
  - Route B: stair/step stress route
  - Route C: slope/surf transition route
- Record at least 3 runs per route per phase.
- Compare:
  - jump success %
  - landing speed loss
  - ground flickers per minute
  - camera jerk (avg/max)

## Risks and Mitigations
- Risk: "Smoother camera" hides simulation problems.
  - Mitigation: always track movement and camera metrics independently.
- Risk: one-off tuning overfits a single map.
  - Mitigation: benchmark on multiple route types before merge.
- Risk: parameter explosion in debug menu.
  - Mitigation: group settings into camera/movement bundles and keep defaults curated.

## Execution Checklist (Immediate)
- [x] Create this plan document.
- [x] Implement Phase 0 feel metrics aggregator.
- [x] Surface metrics in F2 overlay.
- [ ] Capture initial baseline run metrics for Route A/B/C.
- [ ] Open follow-up tasks for Phase 1 and Phase 2 implementation slices.
