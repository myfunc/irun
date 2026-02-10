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
- External level editor: TrenchBroom — **implemented**: direct `.map` loading (Valve 220), brush CSG, WAD textures, Phong normals, material defs, hybrid lighting, quick-test script with file watcher, bake + pack pipelines (game config + FGD shipped in `apps/ivan/trenchbroom/`)
- Map pipeline profiles — **implemented**: dev-fast (skip vis/light, no compression) vs prod-baked (full quality); runtime `--map-profile` auto/dev-fast/prod-baked; profile-aware fog and visibility defaults
- Time trial: local timing + local personal best storage (replays/portal later)

## Paused
Items temporarily on hold pending further analysis:
- ~~Baker app~~: map viewer + import manager + lighting bake tool — paused; external editor (TrenchBroom) replaces the editing/preview role.
- ~~Map format v3~~: entities + triggers + lights + baked chunking — **unpaused**; TrenchBroom integration is complete so map format v3 can proceed. See `docs/brainstorm/tech/2026-02-08_map-format-v3-entities-chunking.md`.

## Milestone 3: Gameplay Feel Rehaul
- Phase 0: instrumentation and baseline capture (jump success, landing loss, ground flicker, camera jerk)
  - Baseline tooling now includes replay telemetry export (CSV + JSON summary), latest-vs-previous comparator utility, and checklist doc (`docs/gameplay-baseline-checklist.md`)
  - In-game Feel Session panel + `G` quick-capture popup wire save/export/compare/feedback actions for faster iteration loops
  - Route compares are now route-scoped and preserve route baseline/history context for multi-run A/B/C tuning
  - Safety rail landed: any auto-apply feedback tweak now snapshots tuning backup first; rollback is available via console (`tuning_restore`) and from `G` popup (`Revert Last`)
- Phase 1: camera pipeline smoothing and readability pass (**in progress**)
  - read-only camera feedback slice landed and rehauled to compact invariants:
    - `camera_base_fov`
    - `camera_speed_fov_max_add`
    - `camera_tilt_gain`
    - `camera_event_gain`
    - `camera_feedback_enabled`
  - debug tuning now uses real-unit slider/entry values instead of normalized `0..100` values
- Phase 2: movement transition stability pass (stairs/slope/ground-air handoff)
- Phase 3: acceleration/friction polish + profile packaging
- Acceptance gates and execution board tracked in `docs/gameplay-feel-rehaul.md`

### Movement Refactor Integration Order (Active)
- 1) Ground-only invariant run wiring (`MotionConfig` + derived run model): **completed (staged)**
- 2) Jump derivation (`H_jump`, `T_apex`) replacing direct jump-speed tuning: **completed (staged)**
- 3) Air control through motion solver authority: **completed (staged)**
- 3a) Air-gain invariant collapse (`air_speed_mult`, `air_gain_t90`) with legacy air scalar removal from active tuning: **completed (staged)**
- 4) Shift powerslide mode replacing dash/crouch (`slide_stop_t90`, hold semantics, low-hull state): **completed (staged)**
- 4a) Velocity authority hardening (non-solver writes routed through explicit velocity interface sources): **completed (staged)**
- 5) Camera read-only integration on top of solved motion: **completed (staged)**
- 6) Animation read-only integration + determinism/HUD validation: **completed (staged)**
- 7) Controller ownership split (intent ingestion + module boundaries): **completed (staged)**
- 8) Wallrun feel pass (tilt direction, camera-biased jump, invariant sink timing): **completed (staged)**
- 9) Reintroduce dash as a separate mode (after baseline/instrumentation pass): **pending**
- 10) Add constrained autotuner loop (feedback + telemetry history -> suggested invariant deltas with rollback guardrails): **pending**
  - implementation plan + approaches are tracked in `docs/feel-ml-autotuner.md`
  - V1 command surface shipped:
    - `autotune_suggest` (route-scoped proposal from compare/history + feedback text)
    - `autotune_apply` (backup-first invariant-only apply)
    - `autotune_eval` (guardrails + weighted route score)
    - `autotune_rollback` (latest/selected backup restore alias)
  - remaining work keeps status pending: automated iterate/replay loop, candidate search strategy upgrades, and acceptance-board automation
