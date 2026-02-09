# Gameplay Baseline Checklist (Phase 0)

This checklist is used for Gameplay Feel Rehaul Phase 0 baseline capture.

## Scope
- Routes: `A`, `B`, `C`
- Required attempts: `3` recorded runs per route (minimum)
- Data source: replay telemetry export (`CSV` + `JSON summary`)
- Tick model: fixed `60 Hz` only

## Route Definitions
- Route A: flat strafe + bunnyhop chain (low geometry complexity)
- Route B: stair/step stress route (ground transition stability)
- Route C: slope/surf transition route (air/ground and ramp handoff)

## Run Capture Rules
- Use the same map bundle/build for all baseline runs.
- Use one tuning profile for the whole baseline set (record profile name in notes).
- Restart from the same spawn point before each run.
- Do not include warmup attempts in the baseline dataset.

## Required Metrics Per Run
- `jump_takeoff.success_rate`
- `metrics.ground_flicker_per_min`
- `metrics.horizontal_speed_avg`
- `metrics.horizontal_speed_max`
- `metrics.speed_avg`
- `metrics.speed_max`
- `ticks.duration_s`

## Checklist

### Route A (3 runs)
- [ ] A1 replay recorded and saved
- [ ] A1 telemetry exported (CSV + JSON)
- [ ] A2 replay recorded and saved
- [ ] A2 telemetry exported (CSV + JSON)
- [ ] A3 replay recorded and saved
- [ ] A3 telemetry exported (CSV + JSON)

### Route B (3 runs)
- [ ] B1 replay recorded and saved
- [ ] B1 telemetry exported (CSV + JSON)
- [ ] B2 replay recorded and saved
- [ ] B2 telemetry exported (CSV + JSON)
- [ ] B3 replay recorded and saved
- [ ] B3 telemetry exported (CSV + JSON)

### Route C (3 runs)
- [ ] C1 replay recorded and saved
- [ ] C1 telemetry exported (CSV + JSON)
- [ ] C2 replay recorded and saved
- [ ] C2 telemetry exported (CSV + JSON)
- [ ] C3 replay recorded and saved
- [ ] C3 telemetry exported (CSV + JSON)

## Notes Template (per run)
- Route/run id:
- Replay file:
- Exported CSV:
- Exported summary:
- Profile name:
- Map id:
- Comments (mistakes, collisions, obvious anomalies):
