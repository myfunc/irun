# Map Format v3: Entities, Triggers, Lights, Chunking

Date: 2026-02-08

This document proposes `map.json` **format_version=3** for IRUN/IVAN map bundles.
The goal is an editor-friendly, engine-agnostic representation that supports:
- course logic (start/finish/checkpoints),
- entity-driven interactions (spawners, triggers, buttons, ladders, movers),
- lighting authoring,
- baked geometry split into chunks (future streaming),
without tying the format to Valve/GoldSrc/Source specifics.

## Design Principles
- **Entity-first**: gameplay-relevant objects are entities with typed components.
- **Baked is optional but preferred**: runtime should prefer baked geometry/collision.
- **Back-compat**: format v2 (`triangles`, `collision_triangles`) continues to load.
- **No arbitrary code execution**: "scripts" are event ids or restricted calls, not raw Python/Lua.
- **Deterministic identity**: compatible with ADR 0002 (content-addressed maps/replays) by enabling stable hashing rules.

## Bundle Layout (Recommended)
- `map.json` (manifest, metadata, entities, baked geometry index)
- `materials/` (textures and material assets)
- `resources/` (optional extra assets: sounds/models/etc)
- `chunks/` (optional)
  - `chunk_<id>.json` (v1: JSON triangles; later: binary)

## Top-Level Schema (Draft)
```json
{
  "format_version": 3,
  "map_id": "string",
  "title": "string",
  "author": "string",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "scale": 0.03,
  "bounds": { "min": [0,0,0], "max": [0,0,0] },
  "spawn": { "position": [0,0,0], "yaw": 0.0, "id": "optional-entity-id" },
  "materials": { "root": null, "converted_root": "materials", "converted": 0 },
  "resources": { "root": "resources" },
  "render_hints": { "texture_filter": "nearest", "mipmaps": "nearest" },
  "baked": { /* see below */ },
  "entities": [ /* see below */ ],
  "course": { /* see below */ }
}
```

Notes:
- `render_hints` is a *hint* for a retro look; actual filtering is controlled by the renderer.
- `spawn.id` allows spawn to be an entity (or remain an explicit position/yaw).

## Baked Geometry (`baked`)
Two supported modes:

### Monolithic
Use existing v2 keys; easiest for small maps.
```json
{
  "baked": {
    "type": "monolithic",
    "triangles_inline": true
  },
  "triangles": [ /* v2 triangle dicts */ ],
  "collision_triangles": [ /* optional position-only tris */ ]
}
```

### Chunked
Chunks are spatial partitions (initially grid2d in XY).
```json
{
  "baked": {
    "type": "chunked",
    "chunking": { "scheme": "grid2d", "cell_size": 64.0, "origin": [0.0, 0.0] },
    "chunks": [
      {
        "id": "0_0",
        "aabb": { "min": [0,0,0], "max": [0,0,0] },
        "path": "chunks/chunk_0_0.json"
      }
    ]
  }
}
```

Chunk file (v1 JSON):
```json
{
  "triangles": [ /* v2 triangle dicts */ ],
  "collision_triangles": [ /* optional position-only tris */ ]
}
```

## Entities
Entities are a list of objects with:
- `id` (string, stable within the map),
- `type` (string enum),
- `name` (optional),
- `transform` (optional; default identity),
- `props` (type-specific payload),
- `components` (optional; used when `type` is generic).

Two approaches are acceptable; pick one:
1) **Typed entities** (`type` drives schema). Simpler for early runtime.
2) **Entity + components** (ECS-like). Better long-term editor tooling.

This v3 draft supports both by allowing either `props` or `components`.

### Common Fields
```json
{
  "id": "cp_1",
  "type": "trigger",
  "name": "Checkpoint 1",
  "transform": { "pos": [0,0,0], "yaw": 0.0, "pitch": 0.0, "roll": 0.0 },
  "tags": ["course"],
  "props": { /* per-type */ }
}
```

### Volumes
Minimal volume shapes:
- `aabb`: world or local min/max
- `obb`: center + half + yaw/pitch/roll (optional for v3.1)
- `cylinder`: radius + height (good for checkpoints)

### Triggers (`type="trigger"`)
```json
{
  "id": "start",
  "type": "trigger",
  "props": {
    "volume": { "type": "aabb", "min": [-1,-1,0], "max": [1,1,2] },
    "on_enter": [
      { "call": "course.start_timer", "args": {} }
    ],
    "on_exit": []
  }
}
```

### Script Calls
"Scripts" are *calls* to registered engine actions, not code:
- `call`: string id resolved by runtime (whitelist)
- `args`: json object

Examples of calls:
- `course.start_timer`
- `course.finish_timer`
- `course.touch_checkpoint` (args: checkpoint id)
- `map.load` (args: target map id, spawn id)
- `spawner.spawn` / `spawner.despawn`
- `ui.toast` (debug)

### Item Spawners (`type="spawner"`)
```json
{
  "id": "health_1",
  "type": "spawner",
  "props": {
    "prefab": "item.health_small",
    "count": 1,
    "respawn_sec": 30.0,
    "enabled": true
  }
}
```

### Lights (`type="light"`)
```json
{
  "id": "sun",
  "type": "light",
  "props": {
    "kind": "directional",
    "color": [0.95, 0.93, 0.86],
    "intensity": 1.0,
    "hpr": [34, -58, 0]
  }
}
```

Supported `kind`:
- `ambient`
- `directional`
- `point`
- `spot` (later)

### Ladders (`type="ladder"`)
```json
{
  "id": "ladder_1",
  "type": "ladder",
  "props": {
    "volume": { "type": "aabb", "min": [0,0,0], "max": [1,1,4] },
    "up_speed": 4.0,
    "snap_to_plane": true
  }
}
```

### Movers / Platforms (`type="mover"`)
Initial assumption: kinematic mover with a path; runtime updates transform and provides collision.
```json
{
  "id": "plat_1",
  "type": "mover",
  "props": {
    "shape": "box",
    "half": [2.0, 2.0, 0.25],
    "path": {
      "mode": "loop",
      "points": [
        { "pos": [0,0,1], "t": 0.0 },
        { "pos": [0,10,1], "t": 3.0 }
      ],
      "ease": "linear"
    },
    "carry_player": true
  }
}
```

### Buttons (`type="button"`)
```json
{
  "id": "btn_1",
  "type": "button",
  "props": {
    "use_volume": { "type": "aabb", "min": [-0.5,-0.5,0], "max": [0.5,0.5,1] },
    "cooldown_sec": 0.5,
    "on_use": [ { "call": "mover.toggle", "args": { "id": "plat_1" } } ]
  }
}
```

## Course (`course`)
Course logic references trigger entity ids rather than duplicating volumes.
```json
{
  "course": {
    "mode": "time_trial",
    "start_trigger": "start",
    "finish_trigger": "finish",
    "checkpoints": ["cp_1", "cp_2"],
    "requires_checkpoints": true,
    "respawn": { "mode": "last_checkpoint" }
  }
}
```

## Map Transitions (Level Loading)
For Half-Life-like multi-map flows, represent transitions as entities:
- `type="map_exit"`: a trigger that calls `map.load` with `target_map_id` and `target_spawn_id`.
- Persist player state via runtime save state (position/yaw, timer, inventory) when crossing.

Example:
```json
{
  "id": "exit_a",
  "type": "map_exit",
  "props": {
    "volume": { "type": "aabb", "min": [0,0,0], "max": [1,2,2] },
    "target_map_id": "b",
    "target_spawn_id": "spawn_from_a",
    "preserve_velocity": false
  }
}
```

## Compatibility With Imports
Importers may:
- keep current baked triangle output (v2) and add entities on top,
- optionally map foreign entity properties to v3 entity `props`,
- store unmapped foreign fields under `props.source` for debugging.

Important note (current behavior):
- Today, imported GoldSrc brush models that are "dynamic" in the source engine (doors, trains, rotating platforms, etc)
  are still baked into IVAN's static triangle streams, so they render/collide as if they were part of the static world.
  v3 should enable importers to preserve these brush models separately and map them to v3 entities (e.g. `mover`).

## Open Questions
- Exact canonical hashing rules for `map_hash` (ADR 0002 follow-up).
- How far we go with OBB/capsule volumes in v3 vs v3.1.
- Kinematic mover collision strategy in Bullet (one body per mover; broadphase; carrying player).
- Material system scope: do we store "materials" as separate definitions or keep "texture path only" for now.
