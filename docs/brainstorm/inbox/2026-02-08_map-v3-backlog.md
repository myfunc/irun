# Map v3 Backlog (Chunking + Entities + Retro Rendering)

Date: 2026-02-08

This is a task backlog for implementing `map.json` format v3 (entities + chunking) without affecting current replay work.

Source spec: `docs/brainstorm/tech/2026-02-08_map-format-v3-entities-chunking.md`.

## Map Format v3
- Define `format_version=3` JSON schema (doc + examples) and document supported entity types.
- Decide typed-entity vs components-first approach for runtime (can support both, but pick a preferred style).
- Add canonical rules for `map_hash` inputs (ADR 0002 follow-up): which files/fields are included and how ordering/normalization is done.

## Runtime: Entity Loading And Dispatch
- Add a runtime entity registry that loads `entities` from `map.json`.
- Implement volume primitives (AABB first) + player overlap checks.
- Implement event dispatch: `on_enter`, `on_exit`, `on_use` calling a whitelist of engine actions.
- Add `course` runtime:
  - start/finish/checkpoint triggers
  - local timer + local PB storage (per `map_id` or `map_hash`)
  - respawn rules (spawn vs last checkpoint)

## Runtime: Lighting From Map
- Parse `light` entities and build Panda3D lights (ambient/directional/point).
- Define fallbacks if no lights exist (keep current default lighting).

## Chunking (Data And Runtime Plumbing)
- Extend loader to accept `baked.type=chunked` with chunk index and per-chunk files.
- v1 policy: load all chunks at map load (no streaming yet), but keep the split to enable streaming later.
- v2 policy (later): stream chunks by player position + hysteresis; detach/attach collision bodies.

## Import Pipelines (Optional Enhancements)
- GoldSrc/Source importers:
  - optionally emit v3 `entities` (spawnpoints, triggers, map exits) based on parsed entity lumps
  - preserve unknown fields under `props.source` for debugging
- Note: today the GoldSrc importer bakes brush models into static render/collision streams. This means "dynamic" map objects
  (e.g., moving platforms, rotating doors, trains) appear as static world geometry in IVAN. Track and address this by:
  - preserving per-brush-model geometry in the bundle, and
  - mapping selected brush entity classnames to v3 entities (`mover`, `button`, etc) instead of baking them into static collision.
- Add a separate "baker" tool that can take an authored entity/piece layout and output baked chunks.

## Dynamic Platforms / Movers (Feasibility Spike)
- Prototype kinematic movers:
  - one Bullet rigid body per mover
  - per-frame transform update
  - player "carry" behavior (stick to platform in contact)
- Define a minimal mover schema (`path` keyframes; loop/pingpong; ease).
- Validate collision stability with step+slide controller.

## Buttons / Interactables
- Add `button` entity with a `use_volume` and `on_use` action calls.
- Add simple UI prompt for "Use" (optional).

## Ladders
- Add `ladder` entity:
  - volume detection
  - movement mode override while inside (climb speed, gravity rules)

## Map Transitions (Level Loading)
- Add `map_exit` entity that calls `map.load` with `target_map_id` / `target_spawn_id`.
- Persist local state on transition:
  - player position/yaw
  - timer state
  - inventory (if/when added)

## Retro Rendering (Separate Track, Not Map-Format Blocking)
- Add renderer support for a "retro" texture filter mode:
  - nearest-neighbor option for masked textures and/or globally
  - control min/mag filters and mipmap strategy
- Expose via settings + optional `render_hints` in `map.json`.

## Movement Bug: Step Height Sticking
- Investigate and fix "stuck on stairs" behavior.
- Likely knobs:
  - step height parameter (if present)
  - ground snap tuning
  - capsule sweep behavior vs stair edges
- Add a regression test map or a scripted repro scene.
