# IVAN Demo Handoff (Chat Summary)

## Context
User requested a playable first-person 3D runner demo in `apps/ivan` with:
- Flow-first movement (easy to learn, hard to master)
- Bhop/strafe acceleration feel (no guided movement)
- Mostly soft-fail gameplay (time loss), occasional hard reset
- Wall jump required; wallrun/vault/grapple toggleable for demo
- Real-time debug/admin tuning menu (sliders + numeric inputs)
- Basic playable map, then Dust2 Largo integration

## Key Product Decisions
- Camera: first-person.
- Core mechanics for demo: sprint, jump, air control, wall jump.
- Advanced mechanics:
  - Wallrun: toggleable prototype behavior.
  - Grapple: toggleable mock impulse behavior.
  - Vault: toggle only (no full behavior yet).
- Skill expression target: routing/pathing/timing + momentum control.
- Counter-strafe requirement: opposite strafe in air should strongly bleed speed.
- Debug UX requirement:
  - Debug menu tied to `Esc`.
  - If cursor active -> debug menu visible.
  - If cursor locked -> debug menu hidden.
- Permanent HUD requirement: top-center speed in integer units.

## Implemented Results

### New app
Created a new app scaffold at:
- `apps/ivan/pyproject.toml`
- `apps/ivan/src/ivan/__init__.py`
- `apps/ivan/src/ivan/__main__.py`
- `apps/ivan/src/ivan/game.py`
- `apps/ivan/tests/test_import.py`
- `apps/ivan/README.md`

### Movement + gameplay
Implemented in `apps/ivan/src/ivan/game.py`:
- First-person mouse look + keyboard movement.
- Ground/air acceleration model with bhop/strafe-friendly behavior.
- Jump, coyote time, jump buffer (toggleable).
- Wall jump.
- Air counter-strafe hard brake parameter (`air_counter_strafe_brake`).
- Respawn handling.

### Debug/admin menu
Implemented:
- Runtime-editable movement parameters.
- Numeric entries + sliders.
- Bool settings exposed via custom flat toggle buttons (ON/OFF text).
- Debug visibility tied to `Esc` pointer mode.

### HUD
Implemented:
- Always-visible speed readout at top center.
- Horizontal speed displayed as integer (`Speed: <int> u/s`).

### Dust2 pipeline
User requested exact map usage from:
- `https://github.com/rolivencia/de_dust2_largo`

Implemented:
- Repo cloned to `apps/ivan/assets/maps/de_dust2_largo`.
- Conversion script added:
  - `apps/ivan/tools/build_dust2_assets.py`
- Generated asset produced:
  - `apps/ivan/assets/generated/de_dust2_largo_map.json`
  - Current output: 3434 triangles.
- Runtime integration:
  - Game attempts to load generated Dust2 asset first.
  - If present/valid, builds render geometry + collision polygons from the same triangle data.
  - Falls back to sample/graybox scene if generated asset is missing/invalid.
- Added `bsp_tool` as dev dependency in `apps/ivan/pyproject.toml`.

## Global docs updated
- `README.md`
- `docs/README.md`
- `docs/project.md`
- `docs/features.md`
- `docs/architecture.md`
- `docs/roadmap.md`

## Current Known Risks / Gaps
- Dust2 rendering is geometry-only (single tint), not full Source material/texturing parity.
- Collision is derived from BSP face triangles; this is closer to geometry parity but still not a full Source-physics emulation.
- Need in-engine playtest pass to validate:
  - Spawn reliability
  - No fall-through on all traversable paths
  - Wall jump consistency on Dust2 walls
- Debug panel readability improved from earlier state but still needs visual polish.

## Commands for next agent

### Run game
```bash
cd apps/ivan
source .venv/bin/activate
python3 -m ivan
```

### Rebuild Dust2 generated asset
```bash
cd apps/ivan
python3 tools/build_dust2_assets.py \
  --input assets/maps/de_dust2_largo/csgo/dist/de_dust2_largo.bsp \
  --output assets/generated/de_dust2_largo_map.json \
  --scale 0.03
```

## Suggested immediate follow-up
1. In-game validation pass on Dust2 pathing/collision.
2. Fix any remaining bad collision zones with diagnostics (triangle normals/contact debug).
3. Improve Dust2 visual quality (texture/material import pipeline).
4. Add proper grapple/wallrun implementations behind existing toggles.
