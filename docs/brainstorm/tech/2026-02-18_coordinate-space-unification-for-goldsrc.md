# Coordinate Space Unification For GoldSrc (2026-02-18)

## User Goal
- Verify why newly added systems in `apps/ivan` inherit an "inside-out / mirrored by default" behavior.
- Identify whether the issue is conceptual (wrong global convention) or local (single-module bug).

## User Motivation
- New features should behave correctly without adding per-feature axis hacks.
- The current setup creates recurring regressions where each new system appears to be born in a flipped space.
- The user wants confidence that the project has one canonical coordinate contract.

## Current Direction
- Treat this as a coordinate-contract mismatch, not a marker/race-specific defect.
- Standardize the GoldSrc runtime contract to one convention everywhere:
  - world/map geometry import,
  - visibility leaf lookup,
  - server relevance (PVS),
  - gameplay marker placement/readback.
- Prefer fixing shared conversion points over adding local compensations in feature code.

## Open Questions / Risks
- Existing cached visibility data and map assumptions may have been validated under mixed conventions; unification can expose latent map-side mismatches.
- Several tests currently exercise mostly `X`-only scenarios and may miss `Y`-axis regressions.
- Viewmodel import-specific mirror settings (for OBJ assets) can visually mask or imitate world-space issues and confuse debugging.
- If migration is partial, regressions will reappear as soon as new systems depend on PVS/relevance paths.

## Timestamped Notes
- **2026-02-18T00:00Z**: Observed contradictory contracts in codebase:
  - Docs/import path state "no axis mirror, scale only" for GoldSrc world geometry.
  - Visibility/relevance paths still apply `-Y` for world->BSP conversion.
- **2026-02-18T00:00Z**: Found internal inconsistency inside visibility flow:
  - Initial leaf determination and runtime leaf determination are not using the same coordinate mapping.
- **2026-02-18T00:00Z**: Preliminary conclusion:
  - The problem is systemic contract drift (mixed conventions), not race-marker logic itself.
- **2026-02-18T00:00Z**: Proposed implementation sequence:
  1. Define and document single canonical world->BSP mapping.
  2. Apply mapping consistently in visibility and server relevance.
  3. Add regression tests with non-zero `Y` values for PVS and relevance.
  4. Re-run map/race sanity checks and confirm no local compensations remain required.

