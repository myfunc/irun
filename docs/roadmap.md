# Roadmap

## Milestone 0: Project Initialization
- Repo structure, docs scaffolding
- Runnable Ivan prototype

## Milestone 1: Movement Prototype
- Player controller: ground/air, jump tuning, basic collision
- Camera prototype
- Minimal "graybox" test level
- First-person bhop/strafe tuning lane with wall-jump experimentation
- In-game admin panel for live physics iteration

## Milestone 2: Level Loop
- Checkpoints + respawn
- Hazards + collectibles
- Simple UI (timer/collect count)
- UI kit: standardize procedural windows/panels/controls and theme tokens before wiring into runtime UI
  - Near-term: lock down typography + DPI scaling + low-res readability rules, then add focus/keyboard navigation and a scroll container
- Handcrafted, player-generated map workflow and validation tools
- Packed map bundles for distribution and git-friendly imports (`.irunmap`) — **default format for all maps**
- External level editor: TrenchBroom (analysis and integration tracked separately)
- Time trial: local timing + local personal best storage (replays/portal later)

## Paused
Items temporarily on hold pending further analysis:
- ~~Baker app~~: map viewer + import manager + lighting bake tool — paused; external editor (TrenchBroom) replaces the editing/preview role.
- ~~Map format v3~~: entities + triggers + lights + baked chunking — paused; map format direction depends on TrenchBroom integration analysis.

## Milestone 3: Gameplay Feel Rehaul
- Phase 0: instrumentation and baseline capture (jump success, landing loss, ground flicker, camera jerk)
  - Baseline tooling now includes replay telemetry export (CSV + JSON summary), latest-vs-previous comparator utility, and checklist doc (`docs/gameplay-baseline-checklist.md`)
  - In-game Feel Session panel wires export/compare/feedback actions for faster iteration loops
- Phase 1: camera pipeline smoothing and readability pass
- Phase 2: movement transition stability pass (stairs/slope/ground-air handoff)
- Phase 3: acceleration/friction polish + profile packaging
- Acceptance gates and execution board tracked in `docs/gameplay-feel-rehaul.md`

### Movement Refactor Integration Order (Active)
- 1) Ground-only invariant run wiring (`MotionConfig` + derived run model): **completed (staged)**
- 2) Jump derivation (`H_jump`, `T_apex`) replacing direct jump-speed tuning: **completed (staged)**
- 3) Air control through motion solver authority: **completed (staged)**
- 3a) Air-gain invariant collapse (`air_speed_mult`, `air_gain_t90`) with legacy air scalar removal from active tuning: **completed (staged)**
- 4) Dash sweep/cast path + runtime harness toggle: **completed (staged)**
- 5) Camera read-only integration on top of solved motion: **completed (staged)**
- 6) Animation read-only integration + determinism/HUD validation: **completed (staged)**
- 7) Controller ownership split (intent ingestion + module boundaries): **completed (staged)**
- 8) Wallrun feel pass (tilt direction, camera-biased jump, invariant sink timing): **completed (staged)**
