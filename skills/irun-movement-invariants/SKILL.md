---
name: irun-movement-invariants
description: Build and refactor IVAN movement/physics features using a minimal invariant-first tuning surface with derived constants and clear solver authority. Use for any movement, jump, slide, collision, camera-feel, or control-pipeline change.
---

# IVAN Movement Invariants Skill

## Goal
Keep movement feel stable under tuning changes by exposing only a small set of decoupled invariants and deriving all dependent constants.

## Non-negotiable rules
- Use invariant-facing parameters, not raw speed/accel/gravity knobs.
- Derive physics constants from invariants in solver/config code.
- Keep solver authority single-source: features should not write `vel` directly except explicit impulses.
- Preserve carried momentum only on successful hop transitions: bypass ground run/friction on consumed ground-jump ticks, but keep normal grounded run convergence toward `Vmax`.
- Camera and animation layers are read-only observers of solved motion.
- Keep debug tuning compact. Add a slider only when it represents a true independent invariant.
- For wallrun UX, prefer read-only camera roll indication and camera-forward-biased wallrun jumps without adding extra scalar clutter.
- Wallrun camera roll should recover toward neutral immediately when wallrun ends (including wallrun jump), while keeping the transition smooth and snappy.
- When adding/refactoring movement features, remove redundant legacy scalars from active tuning and route behavior through existing invariants wherever possible.
- Slide policy:
  - hold-based activation (`Shift` held means active slide)
  - no artificial entry speed boost
  - keyboard strafe should not directly steer slide (camera-yaw steering only)
  - slide slowdown should be controlled by one independent invariant (`slide_stop_t90`)

## Preferred movement invariants
- `max_ground_speed` (Vmax)
- `run_t90`
- `ground_stop_t90`
- `air_speed_mult`
- `air_gain_t90`
- `wallrun_sink_t90`
- `jump_height`
- `jump_apex_time`
- `slide_stop_t90`
- `jump_buffer_time`
- `coyote_time`

## Derivations
- `g = 2 * jump_height / (jump_apex_time^2)`
- `v0 = g * jump_apex_time`
- `run_k = ln(10) / run_t90`
- `ground_damp_k = ln(10) / ground_stop_t90`
- `air_speed = max_ground_speed * air_speed_mult`
- `air_accel = 0.9 / air_gain_t90` (linear Quake-style air acceleration target)
- `slide_damp_k = ln(10) / slide_stop_t90`

## Implementation checklist
1. Put invariants and derived constants in `physics/motion/config.py`.
2. Keep application logic in `physics/motion/solver.py`.
3. Route control input through intent (`MotionIntent`) and one movement entrypoint.
4. Enforce mode priority in solver/controller flow:
   - knockback > slide > run/air
   - gravity always applies unless explicit pause/hitstop
5. Add/maintain replay determinism hashing and HUD visibility.
6. Update docs in same change (`docs/architecture.md`, `docs/features.md`, `docs/gameplay-feel-rehaul.md`, roadmap/ADR as needed).

## Debug-surface policy
- If two sliders affect the same perceptual axis, collapse to one invariant.
- Keep feature-specific tuning hidden unless it is independently controllable and required for current iteration.
- Prefer timing invariants over raw force constants.
- Keep `autojump_enabled` as a compact toggle for bhop-chain validation (toggle, not scalar).

## Validation minimum
- Unit tests for derivations and damping behavior.
- Regression tests for velocity authority (e.g. Vmax changes remain effective).
- Replay determinism path reports hash trace and mismatch counts during playback.
