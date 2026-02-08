# Map Format, Chunking, And Replays (Trackmania-Like)

Date: 2026-02-07

This note proposes a map storage format and runtime/editor responsibilities for a Trackmania-like time trial game:
- A map (course) is a start-to-finish experience, optionally with checkpoints.
- A web portal stores maps, leaderboards, and replays (ghosts).
- A dedicated map editor app must author maps using the same format the game consumes.

The repo currently uses an **IVAN map bundle** rooted at a `map.json` file plus adjacent assets (textures/resources). This proposal extends that concept rather than replacing it.

## Goals
- Keep `map bundle` as the unit of distribution (folder that can be zipped/uploaded).
- Support a clean authored representation for a modular editor ("pieces"/"blocks").
- Support efficient runtime loading and future streaming (chunking).
- Make replays stable: replay data must be bound to a specific immutable map build (hash/version).
- Avoid premature complexity: allow a monolithic map for small courses.

## Non-Goals (For Now)
- Multiplayer and server-authoritative validation.
- Perfect deterministic re-simulation across machines (input-only verification).

## Concepts
### Bundle Layout (Proposed)
A bundle is a directory:
- `map.json` (manifest + metadata; small and stable)
- `authoring.json` (optional; editor-friendly representation)
- `chunks/` (optional; baked geometry split into spatial chunks)
  - `chunk_<id>.bin` (mesh + collision payload; exact encoding TBD)
  - `chunk_<id>.json` (or minimal metadata; if needed)
- `materials/` and `resources/` (existing bundle conventions)

Rationale: `map.json` remains the entrypoint, while big payload moves out to chunk files.

### Authoring vs Baked
We support both within the same bundle:
- **Authoring**: piece placement, checkpoints, rules. This is what the editor edits.
- **Baked**: render mesh + collision triangles, optionally chunked. This is what the runtime loads.

The runtime should prefer baked data. If baked data is absent (developer mode), it can fall back to baking on load, but that should not be the default.

## `map.json` Schema (Draft, Backward-Compatible)
Current bundles use `format_version` (observed: `2`). Propose `format_version: 3` and keep `2` loading support.

Top-level keys (draft):
- `format_version`: int
- `map_id`: string (stable user-facing id)
- `map_hash`: string (content-addressed hash of baked + rules; used to bind replays)
- `title`: string
- `author`: string
- `created_at`: ISO-8601 string
- `updated_at`: ISO-8601 string
- `scale`: float (existing)
- `bounds`: `{ "min": [x,y,z], "max": [x,y,z] }` (existing)
- `spawn`: `{ "position": [x,y,z], "yaw": deg }` (existing)
- `course`: course rules and triggers (new)
- `baked`: baked/streaming info (new)
- `materials`: existing (root paths + indices)
- `resources`: existing

### `course` (New)
Defines how the map is "completed" and how timing/checkpoints work.

Suggested shape:
- `start`:
  - `trigger`: volume that starts the timer
  - `spawn_override`: optional spawn point override for time trials
- `finish`:
  - `trigger`: volume that ends the timer
- `checkpoints`: ordered list of checkpoints, or empty
  - each checkpoint includes `id`, `trigger`, and optional `respawn` position/yaw
- `rules`:
  - `mode`: `"time_trial"`
  - `requires_checkpoints`: bool (if true, finish only counts after all checkpoints)
  - `allow_reset`: bool

Trigger volume types to support (minimal set):
- AABB: `{ "type": "aabb", "min": [..], "max": [..] }`
- OBB (optional later): `{ "type": "obb", "center": [..], "half": [..], "yaw": deg }`

### `baked` (New)
Describes where the runtime geometry comes from.

Options:
1) Monolithic (small maps):
- `baked.type = "monolithic"`
- `baked.triangles_inline = true`
- `triangles`: existing payload (positions only or v2 dict triangles)
- `collision_triangles`: existing payload

2) Chunked (preferred for editor-built maps and large courses):
- `baked.type = "chunked"`
- `baked.chunking`:
  - `scheme`: `"grid2d"` or `"segments"`
  - `cell_size`: float (for grid2d)
  - `origin`: `[x,y]`
- `baked.chunks`: list of chunks
  - `id`: string (stable)
  - `aabb`: bounds of the chunk (for culling/streaming decisions)
  - `render_path`: `"chunks/chunk_<id>.bin"` (or json)
  - `collision_path`: `"chunks/chunk_<id>_coll.bin"` (if separated)
  - `tri_count`: int (optional metrics)

For v1, chunk payload can be JSON for simplicity; for performance, move to a compact binary encoding later.

## Chunking Strategy
We have two viable chunking schemes:

### Grid2D (Default)
Partition XY plane into cells of `cell_size` and assign geometry to cells.
- Pros: simple, editor-friendly, streaming-friendly.
- Cons: long thin tracks can touch many cells; needs hysteresis around the player.

### Track Segments (Later)
Partition the course along the path (e.g., editor-defined "segments").
- Pros: predictable streaming based on progress; good for linear tracks.
- Cons: needs pathing metadata; more tooling.

Runtime policy (initial):
- Keep current behavior for monolithic maps.
- For chunked maps: load all chunks initially (no streaming yet), but keep the split so later we can stream without changing the format.

## Replays ("Ghosts") Design
We want portal replays and in-game ghost playback.

### Binding
A replay must include:
- `map_id` and `map_hash` (required)
- `game_build` (version string)
- `tuning_hash` (movement tuning version; or embed tuning params snapshot)

If `map_hash` mismatches, the replay is not eligible for leaderboard comparison; it can still be displayed as "out of date".

### Data Model Options
Option A: **Pose track** (recommended first step)
- Record at fixed tick (e.g., 60 Hz): time, position, yaw/pitch (and optionally velocity).
- Playback by sampling and rendering a ghost; no simulation needed.
- Pros: simple; robust to non-determinism.
- Cons: cannot be used as anti-cheat validation; file size grows with run length.

Option B: **Input track**
- Record player inputs per tick and re-simulate.
- Pros: compact; enables validation if simulation is deterministic.
- Cons: requires strict fixed timestep + deterministic physics and float behavior; harder across platforms.

Recommendation: start with Pose track for user-facing ghosts; optionally add Input track later for competitive validation.

### Storage Format (Replay)
Bundle-independent replay file, intended to be uploaded to the portal:
- `replay.json` (small header)
- `replay.bin` (compressed frames; e.g., zstd later)

Header fields:
- `format_version`
- `map_id`, `map_hash`
- `duration_ms`
- `tick_hz`
- `frames`: stored in `replay.bin`

Frames (suggested):
- `t_ms` (u32)
- `pos` (3 x i32 fixed-point, e.g., millimeters)
- `yaw_deg` (i16 or i32 fixed-point)
- `pitch_deg` (optional)

Quantization makes replays smaller and stable.

## Editor Implications
The editor should:
- Edit `authoring.json` and `map.json` (course metadata).
- Build baked output (monolithic or chunked) into `chunks/` and update `map.json.baked`.
- Compute `map_hash` from baked payload + `course` rules (and maybe piece library version).

Piece library:
- Each piece has an id and its own local collision/render mesh.
- Placing pieces yields a composed baked mesh (and optionally per-piece metadata for debugging).

## Portal Implications (High-Level)
Portal storage:
- Map: store the zipped bundle + extracted metadata (`map_id`, `map_hash`, title, author, bounds).
- Leaderboard: keyed by `map_hash` (not only by `map_id`).
- Replay: store replay file(s) keyed by `map_hash` and player id; optionally keep best-run only.

## Open Questions
- Do we want vertical chunking (Z) or is XY sufficient for early tracks?
- What is the minimum trigger volume type set (AABB only vs OBB/capsule)?
- How strict should `map_hash` be (include materials/resources, or only collision + course rules)?
- Do we need per-surface properties (ice, dirt, boost) in the map format now, or defer to piece ids?

