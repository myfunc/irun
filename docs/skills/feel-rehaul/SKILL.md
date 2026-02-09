# Feel Rehaul Skill

## Purpose
Keep movement and camera feel systems decoupled, invariant-driven, and easy to tune without retuning unrelated features.

## Core Rules
- Expose designer-facing invariants, derive implementation constants.
- Do not let feature code write velocity directly; route through solver/authority interfaces.
- Keep debug tuning compact; avoid duplicate knobs that affect the same behavior.
- Prefer one slider per concept:
  - timing (`*_t90`, windows)
  - scale (`Vmax`, max add, gain)
  - boolean gate (feature on/off)
- Avoid normalized `0..100` tuning for gameplay values. Show real units.

## Movement-Side Expectations
- Jump is authored via `jump_height` + `jump_apex_time`; derive gravity and takeoff speed.
- Run/stop/air/wallrun/slide behavior is authored via timing and caps, not direct raw accelerations.
- Shared leniency (`grace_period`) should drive jump buffer, coyote, and vault timing windows unless a feature has a strong reason to diverge.

## Camera-Side Expectations
- Camera is read-only observer over solved movement state.
- Keep camera tuning compact:
  - `camera_base_fov`
  - `camera_speed_fov_max_add`
  - `camera_tilt_gain`
  - `camera_event_gain`
  - `camera_feedback_enabled`
- Speed-FOV policy:
  - no effect at or below `Vmax`
  - starts above `Vmax`
  - reaches max add around `10x Vmax`
- Event feedback should share a single envelope/gain path (landing + bhop), not per-event gain clutter unless clearly justified.

## UI/Debug Expectations
- Sliders and numeric entries must show real values with meaningful precision.
- F2 diagnostics should expose camera and movement internals needed for iteration:
  - state, speed, accel, contacts
  - camera FOV target/current, speed ratio/curve factor
  - event quality/amplitude/reject reason

## Documentation Expectations
- Any functional change in feel systems must update:
  - `docs/features.md`
  - `docs/architecture.md`
  - `docs/roadmap.md`
  - `docs/gameplay-feel-rehaul.md`
- Add/update brainstorm notes under `docs/brainstorm/ui-ux/` when exploring feel iterations.
