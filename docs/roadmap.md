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
- Time trial: local timing + local personal best storage (replays/portal later)

## Paused
Items temporarily on hold pending further analysis:
- ~~Baker app~~: map viewer + import manager + lighting bake tool — paused; external editor (TrenchBroom) replaces the editing/preview role.
- ~~Map format v3~~: entities + triggers + lights + baked chunking — **unpaused**; TrenchBroom integration is complete so map format v3 can proceed. See `docs/brainstorm/tech/2026-02-08_map-format-v3-entities-chunking.md`.
