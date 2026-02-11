# Scope 01: Runtime World Baseline

Status: `done`

Progress notes (2026-02-10):
- Implemented baseline sky/fog resolution across direct `.map`, `map.json`, and packed `.irunmap` entry paths.
- Added runtime diagnostics surfaces for world path, sky source, and fog source.
- Verified `light_spot` runtime-lighting path uses spotlight nodes (cone + orientation) instead of point-light fallback.

## Problem
- New maps work in runtime lighting mode, but behavior across older/imported maps feels inconsistent.
- Users expect a valid skybox and visible fog horizon by default.
- There is confusion that some maps still look like they run through an older render path.

## Outcome
- One predictable world baseline for all map entry points:
  - skybox always resolved (map value or fallback),
  - fog default policy always applied,
  - runtime-lighting intent visible and inspectable at runtime.

## In Scope
- Skybox fallback policy:
  - if map provides `skyname`, use it;
  - otherwise use default skybox preset.
- Ensure skybox lookup works for direct `.map`, packed `.irunmap`, and imported maps.
- Fog baseline policy:
  - map fog override > run profile > engine default;
  - enforce conservative default horizon fog when none provided.
- Runtime renderer diagnostics:
  - add explicit runtime state reporting (active path, fog source, sky source).
- Verify `light_spot` truly renders as spotlight in runtime path where intended.

## Out Of Scope
- New artistic skybox packs.
- Weather/volumetric fog effects.
- Full PBR or deferred pipeline migration.

## Dependencies
- None (foundation scope).

## Implementation Plan
1. Normalize skybox/fog source resolution in map load pipeline.
2. Add default skybox constant and asset fallback contract.
3. Add runtime world diagnostics command(s) and UI line output.
4. Audit imported map path parity against direct map path.
5. Update docs with baseline behavior and override precedence.

## Acceptance Criteria
- Any loaded map has a skybox: map sky or default fallback.
- Any loaded map has predictable fog behavior with clear precedence.
- Runtime diagnostics show which path is active and why.
- Imported legacy maps no longer look "mysteriously different" without explanation.

## Risks
- Default fog may over-hide distant geometry on small arenas.
- Default skybox may clash with map art direction.

## Validation
- Visual checks on `demo.map`, `light-test.map`, and one imported map.
- Compare direct `.map` and `.irunmap` runs for same content.
