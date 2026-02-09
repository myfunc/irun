# ADR 0005: Invariant Motion Config and Solver Authority

## Status
Accepted (initial rollout)

## Context
Movement feel tuning has become over-coupled: changing one scalar (for example max run speed) requires retuning multiple unrelated constants (ground acceleration, jump speed expectations, friction interactions). The existing controller also allows many feature paths to write velocity directly.

This makes movement feel unstable across profiles and hard to diagnose.

## Decision
Introduce an invariant-based motion layer under `ivan.physics.motion`:

- `MotionInvariants`: designer-facing parameters.
- `MotionDerived`: runtime constants computed from invariants.
- `MotionConfig`: single runtime config object containing both.
- `MotionSolver`: one authority for derived run/jump/gravity/ground-damping math.

Initial formulas:

- Jump:
  - `g = 2 * H_jump / (T_apex^2)`
  - `v0 = g * T_apex`
- Run:
  - exponential response from `Vmax + T90`
- Ground slowdown:
  - exponential damping from `T90_stop` (`ground_stop_t90`)
- Air gain/cap:
  - `V_air = Vmax * air_speed_mult`
  - `air_accel = 0.9 / air_gain_t90` (linear Quake-style acceleration target)
- Dash:
  - `V_dash = D_dash / T_dash`
- Wallrun sink:
  - sink target is derived from jump takeoff speed
  - convergence rate is timing-based (`wallrun_sink_t90`)

## Consequences
Positive:

- Tuning becomes stable: invariant edits propagate predictably through derived values.
- Movement constants are explicit and inspectable from one config object.
- Ground/air/jump calculations can be tested independently from collision/world code.

Tradeoffs:

- Existing debug/profile surfaces must expose only the minimal invariant set to avoid tuning surface bloat.
- Legacy profiles need one-time migration from direct scalar fields to invariant timing fields.
- Legacy air gain fields (`max_air_speed`, `jump_accel`, `air_control`, `air_counter_strafe_brake`) are migration-only and removed from active tuning schema.

## Implementation Notes
- New package: `apps/ivan/src/ivan/physics/motion/`.
- `PlayerController` now consumes `MotionSolver` for run/jump/gravity/ground-damping paths.
- Client/server sim loops now route movement commands through `MotionIntent` and `step_with_intent(...)`.
- `PlayerController` has been split into orchestration/actions/surf/collision modules to reduce coupling and keep file ownership boundaries clear.
