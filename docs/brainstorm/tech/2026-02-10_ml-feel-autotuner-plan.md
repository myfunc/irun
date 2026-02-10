# ML Feel Autotuner Plan (Route A/B/C)

## Goal
Use route-tagged run captures (`G`) to auto-tune movement + camera invariants without manual slider grinding, while keeping rollback safety first.

## Data Inputs
- Replay summary metrics (`*.summary.json`) per exported run.
- Route-scoped compare outputs (`*.compare-*.json`) and route history context (`*.route-*.history.json`).
- Free-text fields:
  - `run_note`: what happened in the run.
  - `feedback_text`: what should change in feel.
- Current invariant snapshot (active profile) at export time.

## Safety Requirements
- Every auto-apply must create a tuning backup snapshot first.
- Restore must be one-step (`tuning_restore`) and route iteration should continue immediately.
- Parameter changes must stay inside invariant bounds and capped step size per iteration.

## Tuning Model (Proposed)
1. Intent extraction:
   - Parse `feedback_text` into intents (speed, acceleration, landing harshness, camera comfort, etc.).
   - Convert intent into objective weights and hard constraints.
2. Metric scoring:
   - Score candidate configs per route against objective:
     - movement continuity (landing speed retention, flicker)
     - control quality (jump success, accel response)
     - camera comfort (jerk proxies)
3. Optimizer:
   - Start with constrained Bayesian optimization over invariant space.
   - Keep trust region small around current config (local search) to avoid jarring jumps.
4. Acceptance gate:
   - Candidate is accepted only if weighted score improves and no guardrail metric regresses beyond threshold.
5. Apply + evaluate:
   - Apply candidate, run A/B/C captures, compare to previous + baseline, repeat.

## Why This Fits Current Architecture
- Current system already stores route history + baseline context.
- Invariant-based tuning space is compact and bounded.
- Replay export/compare pipeline is deterministic enough for iterative optimization.
- Backup/restore hooks already exist for safe experimentation.

## Next Implementation Slice
- Add `autotune_suggest` command:
  - input: route tag + optional text prompt
  - output: candidate invariant deltas + rationale + expected metric impact
- Add `autotune_apply` command:
  - auto-backup -> apply candidate -> persist -> emit compare checklist prompt
- Keep current rule-based `feel_feedback` as fallback mode.
