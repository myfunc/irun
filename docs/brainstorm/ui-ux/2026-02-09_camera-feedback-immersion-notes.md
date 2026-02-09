# Camera Feedback Immersion Notes

## Context
Movement feel is now invariant-driven and decoupled from camera authority. We added camera feedback as a read-only observer so immersion can improve without creating new movement coupling.

## Implemented (Earlier Slice)
- Speed feedback:
  - dynamic FOV response from horizontal speed vs `Vmax`
- Event feedback:
  - landing camera impulse from impact velocity
  - successful bhop pulse (short FOV + pitch cue)
- Tuning controls moved into a dedicated debug `Camera` section (legacy first pass; later replaced by compact invariants):
  - `camera_base_fov`
  - `camera_speed_fov_max_add`
  - `camera_tilt_gain`
  - `camera_event_gain`
  - `camera_feedback_enabled`
- Safety:
  - observer state resets on map start/respawn/network reset to avoid stale camera pops

## Camera Rehaul (Current Execution Plan)
- Subtask owner: Camera workstream (Phase 1 under global feel rehaul).
- Goal: reduce camera tuning clutter the same way movement was decoupled.
- New compact invariant surface:
  - `camera_base_fov`
  - `camera_speed_fov_max_add`
  - `camera_tilt_gain`
  - `camera_event_gain`
  - `camera_feedback_enabled`
- Runtime policy:
  - speed FOV starts only above `Vmax`
  - speed FOV reaches configured max add around `10x Vmax`
  - landing + successful bhop share one event envelope/gain path
- Diagnostics:
  - F2 includes `cam_event`, `quality`, `applied_amp`, `blocked_reason`.
- UI policy:
  - debug numeric controls must show real values/units, not normalized `0..100`.

## Open iteration ideas (next)
- Add lightweight audio hooks for landing success/failure timing cues.
- Add optional speed-edge vignette/material pulse (visual-only, no gameplay authority).
- Add per-event cooldown/debug counters in `F2` to quickly diagnose over-triggering.
- Validate replay route A/B/C with camera-feedback ON vs OFF and compare camera jerk metrics.
