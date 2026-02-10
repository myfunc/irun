# Feel ML Autotuner Plan

## Objective
Automatically tune movement + camera invariants from route captures (`A/B/C`) and player feedback text, while keeping changes safe and reversible.

## Current Foundation
- Route-scoped replay exports with metrics and history context.
- `feedback_text` and `run_note` captured per export.
- Deterministic replay pipeline and compare outputs.
- Pre-apply tuning backups and one-click restore (`Revert Last` / `tuning_restore`).
- V1 route-scoped autotune console commands:
  - `autotune_suggest <route_tag> <feedback_text> [out_dir]`
  - `autotune_apply <route_tag> <feedback_text> [out_dir]`
  - `autotune_eval <route_tag> [out_dir]`
  - `autotune_rollback [backup_ref]`

## Scope of Parameters (Invariant-Only)
Autotuner may adjust only compact invariants:
- Movement:
  - `max_ground_speed`
  - `run_t90`
  - `ground_stop_t90`
  - `air_speed_mult`
  - `air_gain_t90`
  - `jump_height`
  - `jump_apex_time`
  - `wallrun_sink_t90`
  - `slide_stop_t90`
  - `grace_period`
- Camera:
  - `camera_base_fov`
  - `camera_speed_fov_max_add`
  - `camera_tilt_gain`
  - `camera_event_gain`

Excluded:
- Booleans/toggles as default (feature gating should remain explicit by designer).
- Geometry/hull fields except dedicated tests.
- Noclip utility tuning (`noclip_speed`) from ML loop.

## Input Signals
1. Quantitative:
   - route comparison metrics (`compare` and `history` JSON).
   - rolling per-run metrics (jump success, landing loss, flicker, camera jerk).
2. Qualitative:
   - `feedback_text` (what to change).
   - `run_note` (what happened / context).

## Optimization Strategy
Use a constrained, staged approach:

1. Intent extraction:
   - Parse text into intents (`too fast`, `harsh landing`, `camera twitchy`, etc.).
   - Map intents to weighted objectives and candidate fields.
2. Candidate proposal:
   - Start from current profile.
   - Apply bounded deltas (trust region), e.g. max 2-8% per field per iteration.
3. Scoring:
   - Weighted route score:
     - performance/flow: jump success, speed retention.
     - stability: ground flicker, fail rate.
     - camera comfort: jerk metrics.
4. Guardrails:
   - Reject candidates that regress protected metrics over threshold.
   - Reject candidates violating parameter bounds.
5. Apply flow:
   - Backup -> apply -> persist -> evaluate against newest route baseline/history.
   - Auto-rollback if guardrails fail.

## Model Approaches
Recommended rollout:

1. Phase A (deterministic + explainable):
   - Rule/heuristic proposer + weighted metric scorer.
   - No external ML dependency.
2. Phase B (constrained Bayesian search):
   - Bayesian optimizer over invariant space with trust-region.
   - Uses route metrics as black-box objective.
3. Phase C (optional language-assisted intent):
   - LLM parses free text into intents/weights, but never applies values directly.
   - Numeric deltas still produced by constrained optimizer.

## Implementation Plan
1. `autotune_suggest` (implemented V1):
   - input: `route_tag`, `feedback_text`, optional telemetry export `out_dir`.
   - source data: route-scoped compare + history context (`A/B/C`) with latest fallback summary.
   - output: invariant-only bounded deltas and context artifact paths.
2. `autotune_apply` (implemented V1):
   - calls route-scoped suggest pipeline.
   - always creates tuning backup first (`pre-autotune-apply`) via existing backup system.
   - applies only suggested invariant fields and triggers normal tuning-change hooks.
3. `autotune_eval` (implemented V1):
   - route-scoped guardrail checks + weighted score from latest vs reference compare metrics.
   - reports compare result counts and check-level pass/fail details.
4. `autotune_rollback` convenience command (implemented V1):
   - alias over existing backup restore flow (`tuning_restore` semantics).
   - defaults to latest backup when ref is omitted.
5. Integrate with `G` popup (future enhancement):
   - keep current flow.
   - later add optional `Suggest` action.

## Guardrail Defaults
- Max absolute field delta per apply:
  - timing fields: ±0.02s (or ±8%, whichever is lower)
  - speed/scale fields: ±5%
  - camera gains: ±0.08
- Hard stop conditions:
  - jump success drops > 5% absolute
  - ground flicker rises > 15%
  - camera jerk rises > 20%

## Acceptance Criteria
- Same route input sequence yields measurable score improvements over baseline.
- No repeated regressions on protected metrics.
- Rollback remains instant and reliable.
- Tuning surface remains compact and invariant-first.

## V1 Notes
- V1 is intentionally deterministic/rule-based and does not add external ML dependencies.
- Per-apply trust-region and hard bounds are enforced by invariant-only suggestion logic.
- Apply safety is shared with existing backup UI/console flows, so rollback behavior remains identical across `autotune_apply`, popup `Revert Last`, and `tuning_restore`.
