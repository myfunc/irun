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
- Replay telemetry export tooling:
  - per-run CSV tick dump
  - per-run JSON summary metrics
  - latest-replay export trigger (CLI + in-game console command)
  - latest-vs-previous comparator utility with metric and tuning deltas
  - in-game Feel Session panel for export/compare/feedback actions

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
- Baseline checklist document:
  - `docs/gameplay-baseline-checklist.md`

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
- [x] Add replay telemetry export + comparator tooling.
- [ ] Capture initial baseline run metrics for Route A/B/C.
- [ ] Open follow-up tasks for Phase 1 and Phase 2 implementation slices.

## Current Progress (2026-02-09)
Completed now:
- Replay reliability/input-safety pass:
  - Replay playback is now hard-locked from live gameplay/menu input contamination.
  - During replay, only `R` exits playback and returns to normal respawned play.
  - Replay stop path resets playback and input accumulators consistently.
- Replay observability pass:
  - Demo frame format upgraded (`format_version=3`) with backward-compatible loading of v1/v2 demos.
  - Each recorded tick now stores telemetry useful for feel analysis:
    - position/eye height
    - velocity and horizontal/total speed
    - camera yaw/pitch
    - grounded/crouched/grapple/noclip state
    - per-tick command snapshot (jump/crouch/grapple/noclip/move/look/raw held keys)
  - Replay telemetry summary now includes:
    - landing speed loss/retention metrics
    - camera linear/angular jerk metrics
    - recorded tuning snapshot in exported summary payload
- Replay analytics workflow pass:
  - Added replay comparator utility (auto-export latest+previous and emit delta JSON).
  - Added in-game Feel Session tab (ESC menu) to:
    - export latest replay telemetry
    - compare latest vs previous run
    - apply free-text feedback driven tuning adjustments
- Replay UX pass:
  - Added replay-only input HUD (UI kit based) showing:
    - movement cluster (left/right + forward/back)
    - dedicated jump section
    - dedicated crouch section
    - dedicated mouse-direction section (+ raw dx/dy)

Validation completed:
- Replay format/telemetry/comparison tests pass (`test_replay_demo.py`, `test_replay_telemetry_export.py`, `test_replay_compare.py`).
- Runtime smoke runs pass in menu boot and map boot paths.

## Invariant Motion Refactor Progress (2026-02-09)
Status: `IN PROGRESS` (core invariants active, authority hardening still staged)

Completed in this slice:
- Added a dedicated movement package: `apps/ivan/src/ivan/physics/motion/`
  - `MotionConfig` now holds one object with designer invariants + derived constants.
  - Added derivation formulas for jump/run/dash constants.
- Added new tuning invariants (debug/profile/persistence compatible):
  - `run_t90`, `ground_stop_t90`
  - `jump_apex_time`
  - `air_speed_mult`, `air_gain_t90`
  - `wallrun_sink_t90`
  - `dash_distance`, `dash_duration`
  - `coyote_time`
- Wired `PlayerController` to consume `MotionSolver` for:
  - ground run response (derived model)
  - ground coasting damping derived from stop timing invariant
  - gravity application
  - jump takeoff speed derivation
  - coyote-time jump consume path
- Removed legacy direct run/gravity tuning fields from active tuning schema.

Completed in follow-up slice:
- Added initial dash mode integration:
  - input command path includes `dash_pressed` (record/replay + network packet wiring).
  - dash parameters are invariant-driven (`dash_distance`, `dash_duration` -> derived speed).
  - dash collision supports sweep/cast path (`dash_sweep_enabled`) with runtime fallback path.
- Added deterministic feel harness bootstrap (`--feel-harness`):
  - flat, slope approximation, step, wall, ledge, and moving platform fixtures.
  - runtime harness toggles exposed in debug UI for subsystem isolation.
- Expanded on-screen diagnostics + rolling logs:
  - frame p95, sim step count, state, velocity/accel, contacts, floor/wall normals, leniency windows.
  - `F10` JSON dump of rolling (2-5s) diagnostics buffer.
  - deterministic state hashing in HUD (`F2`) and trace dump (`F11`).
- Added regression tests for:
  - invariant derivation formulas (`test_motion_config.py`)
  - coyote window behavior and dash sweep stopping conditions.
- Reduced debug tuning menu to a compact invariant-first control set:
  - removed redundant direct-scalar sliders from runtime tuning surface.
  - surf debug section is now toggle-only (`surf_enabled`) with no surf scalar sliders.
  - invariant mode is now default-on and default profiles are migrated to invariant timing fields.
  - debug panel internals were split into `debug_ui.py` + `debug_ui_schema.py` to keep file ownership scoped and avoid oversized UI modules.
- Fixed Vmax authority regression:
  - ground friction now damps only coasting (no movement input), so changing `max_ground_speed` reliably changes terminal ground speed under held input.
- Fixed bunnyhop landing/takeoff carry regression:
  - normal grounded run shaping converges horizontal speed toward `Vmax` again (prevents persistent overspeed running).
  - grounded jump-consume tick now bypasses ground run + coasting damping to preserve successful hop timing momentum.
  - `autojump_enabled` is restored in the compact debug surface.
- Wallrun UX pass:
  - `wallrun_enabled` is restored in the compact debug surface for live iteration.
  - camera now applies slight roll tilt away from the wall while wallrun is active (read-only observer effect).
  - wallrun jump now biases launch direction toward camera forward heading while retaining wall peel-away behavior.
  - wallrun descent now uses invariant timing (`wallrun_sink_t90`) via solver response instead of per-feature velocity clamps.
- Camera animation responsiveness pass:
  - introduced `camera_tilt_observer.py` as a read-only camera animation layer.
  - wallrun roll transition now smooths with a snappy response curve (reduces one-frame roll snap/jank).
  - wallrun roll now starts returning to neutral immediately on wallrun exit/jump, avoiding delayed recentering.
  - added gentle movement-relative tilt targets (strafe roll + backpedal pitch) to improve perceived responsiveness.
- Air-gain decoupling pass:
  - removed direct air gain scalars from active tuning (`max_air_speed`, `jump_accel`, `air_control`, `air_counter_strafe_brake`).
  - introduced two core invariants:
    - `air_speed_mult` -> derived `air_speed = Vmax * air_speed_mult`
    - `air_gain_t90` -> derived `air_accel = 0.9 / air_gain_t90`
  - this keeps bhop gain behavior coupled to one speed-scale axis and one timing axis, with no hidden overlap sliders.
- Unified command ingestion via motion intent:
  - both client sim tick and authoritative server tick now call `PlayerController.step_with_intent(...)`.
  - jump/dash/crouch/wish direction are routed through one intent contract before solver/collision.
- Split oversized controller file into ownership modules (all under 500 LOC):
  - orchestration (`player_controller.py`)
  - actions (`player_controller_actions.py`)
  - surf/air/wall probes (`player_controller_surf.py`)
  - collision/sweep/step-slide (`player_controller_collision.py`)
- Integrated read-only observer layers:
  - `camera_observer.py` handles camera shell smoothing from solved motion only.
  - `animation_observer.py` applies optional visual bob/root-motion offsets without mutating movement state.
- Replay determinism validation now runs during playback:
  - recorded telemetry includes per-tick deterministic state hash.
  - playback compares expected vs simulated hash and reports mismatch counts on exit.

Still pending:
- Motion authority hardening (state machine + solver priorities) to enforce “non-solver velocity writes only for explicit impulses” contract.
- Harden dash state behavior and add dedicated dash mode telemetry thresholds.
- Optional CLI/automation wrapper for determinism verification across repeated replay runs.

## Why This Helps Future Phases
- Phase 0 baselining: replay telemetry gives us a stable per-tick data source to compare tuning passes, not just subjective feel.
- Phase 1 camera work: camera-angle and input data in demos lets us quantify camera response quality against identical inputs.
- Phase 2 movement stability: grounded transitions + speed data in demos makes step/slope/landing regressions measurable and reviewable.
- Phase 3 polish: replay HUD and telemetry reduce iteration cost by making route-level behavior visible during every test run.

## Next Steps (Execution Order)
1. Capture initial baseline datasets (3 runs per route) using `docs/gameplay-baseline-checklist.md`.
2. Start Phase 1 camera pipeline pass behind explicit tuning params.

## Rehaul Board Snapshot
- Overall status: `Phase 0 active`, `Phase 1 ready-to-start after baselines`.
- What is complete:
  - feel-metrics overlay in gameplay (`F2`)
  - replay data expansion (v3 frames with movement/camera/state telemetry + raw held inputs)
  - replay input lock + deterministic playback safety improvements
  - replay input HUD for visual command verification during playback
  - replay telemetry export summaries with landing/camera metrics
  - replay comparator utility (latest vs previous deltas)
  - in-game Feel Session export/compare/feedback loop
- What is next:
  - baseline capture pack for Route A/B/C (3 runs each)
  - camera smoothing/FOV response slice with measurable before/after
- Why this sequence matters:
  - we now have objective data and deterministic replays before camera/movement retuning
  - every future tuning slice can be validated against the same recorded inputs
  - regression detection is now practical for both movement and camera feel
