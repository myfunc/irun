# ADR 0007: Map Lights and Fog Data Contract

Date: 2026-02-10

## Status

Accepted (implemented).

## Context

Map pipeline parity for runtime lighting and fog authoring was inconsistent:

- `pack_map.py` did not include lights in the map payload; BSP importer did.
- Fog was only configurable via `run.json`; maps could not author fog.
- TrenchBroom FGD lacked `light_spot` and fog entity definitions.
- map.json v2 consumers expected optional, backward-compatible extensions.

## Decision

### 1. Lights in map payload

- **pack_map.py**: Extract `light`, `light_spot`, `light_environment` entities from parsed `.map` and include them in `map.json` under `"lights"` (list of dicts).
- **import_goldsrc_bsp.py**: Already extracted lights; no change.
- **map.json schema**: `lights` is a list of light entities with `classname`, `origin`, `color`, `brightness`, `pitch`, `angles`, `inner_cone`, `outer_cone`, `fade`, `falloff`, `style` (same format as BSP importer).

### 2. Fog in map payload (optional)

- **Optional fields**: `map.json` may include `"fog": {"enabled": bool, "start": float, "end": float, "color": [r,g,b]}`.
- **pack_map.py**: Extract fog from `worldspawn` or `env_fog` entity (GoldSrc convention: `fogstart`, `fogend`, `fogcolor`).
- **import_goldsrc_bsp.py**: Same extraction from BSP entities.
- **map_converter**: Extract fog for direct `.map` loading.
- **Runtime**: When `map.json` has fog, it overrides `run.json`; when absent, fall back to run config or profile defaults.
- **Runtime baseline (Scope 01 follow-up)**: If neither map nor run profile provides fog, runtime applies conservative engine horizon fog defaults.

### 3. TrenchBroom FGD

- Add `light_spot` entity with `_cone`, `_cone2`, `_fade`, `_falloff`, `style`.
- Add `env_fog` point entity with `fogstart`, `fogend`, `fogcolor`.
- Add `_light` (string "R G B I") to `light`, `light_spot`, `light_environment` for GoldSrc-style combined color+intensity.
- Add `fogstart`, `fogend`, `fogcolor` to `worldspawn` for level-global fog authoring.

### 4. Backward compatibility

- Existing map.json v2 consumers that ignore `lights` and `fog` continue to work.
- If `lights` is missing, runtime treats it as empty list.
- If `fog` is missing, runtime uses run.json or profile defaults.

## Consequences

- Consistent lights data across pack and BSP import paths.
- Maps can author fog; runtime merges map fog over run.json.
- TrenchBroom authors can place spotlights and fog entities.
- Runtime `light_spot` now binds to actual spotlight nodes in runtime-lighting paths (cone + orientation), so authored cone lights are inspectable during direct-map iteration.
- No breaking changes for existing bundles.

## Related

- ADR 0004: Packed Map Bundles (.irunmap)
- ADR 0006: Map Pipeline Profiles and Runtime Behavior
- `docs/architecture.md`: Map Pipeline, map.json fields
- `docs/features.md`: Lighting, fog authoring
