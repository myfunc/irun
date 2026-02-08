# Architecture

## Overview
Game apps use **Panda3D** directly to keep iteration fast for movement-focused prototypes.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/ivan/src/ivan/__main__.py`: Ivan entrypoint (`python -m ivan`)
- `apps/ivan/src/ivan/game.py`: App wiring (Panda3D ShowBase), input, camera, and frame update loop
- `apps/ivan/src/ivan/maps/catalog.py`: runtime catalog helpers for shipped bundles and GoldSrc-like map discovery
- `apps/ivan/src/ivan/state.py`: small persistent user state (last launched map, last game dir/mod, debug tuning overrides)
- `apps/ivan/src/ivan/world/scene.py`: Scene building, external map-bundle loading (`--map`), spawn point/yaw
- `apps/ivan/src/ivan/maps/steam.py`: Steam library scanning helpers (manual Half-Life auto-detect)
- `apps/ivan/src/ivan/physics/tuning.py`: Tunable movement/physics parameters (exposed via debug/admin UI)
- `apps/ivan/src/ivan/physics/player_controller.py`: Kinematic character controller (Quake3-style step + slide)
- `apps/ivan/src/ivan/physics/collision_world.py`: Bullet collision query world (convex sweeps against static geometry)
- `apps/ivan/src/ivan/ui/debug_ui.py`: Debug/admin menu UI (CS-style grouped boxes, collapsible sections, scrollable content, normalized sliders, profile dropdown/save)
- `apps/ivan/src/ivan/ui/main_menu.py`: main menu controller (bundle list + import flow)
- `apps/ivan/src/ivan/ui/retro_menu_ui.py`: retro-styled menu widgets (procedural background)
- `apps/ivan/src/ivan/ui/pause_menu_ui.py`: in-game ESC menu (Resume/Map Selector/Key Bindings/Back/Quit) and keybinding controls
- `apps/ivan/src/ivan/common/error_log.py`: small in-memory error feed used to prevent hard crashes and surface unhandled exceptions in-game
- `apps/ivan/src/ivan/ui/error_console_ui.py`: bottom-screen error console (toggle with `F3`)
- `apps/ivan/src/ivan/common/aabb.py`: Shared AABB type used for graybox fallback
- `apps/ivan/tools/build_source_bsp_assets.py`: Source BSP -> IVAN map bundle (triangles + textures; VTF->PNG)
  - Extracts per-face Source lightmaps and basic VMT metadata (e.g. `$basetexture`, translucency hints) into `map.json`.
- `apps/ivan/tools/importers/goldsrc/import_goldsrc_bsp.py`: GoldSrc/Xash3D BSP -> IVAN map bundle (triangles + WAD textures + resource copy)
  - Notes: GoldSrc masked textures use `{` prefix; importer emits PNG alpha using palette/index rules and runtime enables binary transparency for those materials.
  - Notes: The importer extracts embedded BSP textures when present and falls back to scanning `--game-root` for `.wad` files if the BSP omits the worldspawn `wad` list.

## Runtime
- Start: `python -m ivan` (from `apps/ivan`)
- The game loop is driven by Panda3D's task manager.
- In-game UI/input split:
  - `Esc` opens gameplay menu and unlocks cursor.
  - `` ` `` opens debug/admin tuning menu and unlocks cursor.
  - While either menu is open, gameplay input is blocked but simulation continues.
  - Gameplay movement step supports optional noclip mode, optional autojump queueing, and surf behavior on configured slanted surfaces.

## Rendering Notes
- Texture sizing: IVAN disables Panda3D's default power-of-two rescaling for textures (`textures-power-2 none`).
  - Reason: imported GoldSrc maps commonly reference non-power-of-two textures; automatic rescaling breaks BSP UV mapping.
- Imported BSP bundles render with baked lightmaps (Source/GoldSrc) and disable dynamic scene lights for map geometry.
- Per-map run options can be stored in `<bundle>/run.json` (mode/spawn/lighting presets).

## Dependencies
- `panda3d`: 3D engine and window/event loop
- `panda3d.bullet`: Bullet integration used by IVAN for robust character collision queries (convex sweeps, step+slide).
- `bsp_tool`: BSP parsing for IVAN map import pipelines (Source + GoldSrc branches)
- `Pillow`: image IO used by map import tools (VTF/WAD -> PNG)

## Maps (Planned: Format v3)
Maps are distributed as **map bundles** rooted at a `map.json` manifest plus adjacent assets (textures/resources).

Planned format v3 extends the current v2 triangle bundles with:
- **Entities**: triggers, spawners, buttons, ladders, movers, lights (engine-agnostic model).
- **Course logic**: start/finish/checkpoints driven by trigger entities.
- **Chunking**: baked geometry split into chunks for future streaming (initially still loaded eagerly).
- Optional **render hints** to support a retro look (e.g., nearest-neighbor texture filtering); renderer decides actual behavior.

See: `docs/brainstorm/tech/2026-02-08_map-format-v3-entities-chunking.md`.

## Game Modes (Runtime)
Ivan supports **game modes** as small plugins that define "rules around the movement sandbox" without changing
the core player controller or rendering loop.

Mode selection is driven by optional per-bundle metadata:
- File: `<bundle>/run.json` (sits next to `map.json`)
- Fields:
  - `mode`: mode id (`free_run`, `time_trial`, or `some.module:ClassName`)
  - `config`: mode-specific configuration (JSON object)
  - `spawn`: optional spawn override `{ "position": [x, y, z], "yaw": deg }`

Built-in modes:
- `free_run`: default "just run around"
- `time_trial`: local time trial (Start/Finish volumes, restart, local PB + local leaderboard)

## Time Trial (Local Mode)
`time_trial` is currently **local-only**:
- Course is defined by **Start** and **Finish** AABB volumes (provided via `run.json` `config`).
- Runs are persisted in the user state file (`~/.irun/ivan/state.json`) keyed by `map_id`.
- Optional dev helper: if a bundle does not provide Start/Finish yet, the player can set them locally:
  - `F4`: restart (respawn + cancel attempt)
  - `F5`: set Start marker at current player position
  - `F6`: set Finish marker at current player position
  - `F7`: clear local course markers
  - `F8`: export Start/Finish into `<bundle>/run.json`
  - `F9`: export spawn override into `<bundle>/run.json`
  - Marker size is controlled by tuning fields (`course_marker_half_extent_xy`, `course_marker_half_extent_z`).

## Competitive Integrity (Planned)
For speedrun/time-trial workflows we want runs to be comparable and verifiable across map updates.

Planned approach:
- Introduce a stable `map_hash` (cryptographic digest) for a specific built map bundle payload + course rules.
- Introduce a `replay_hash` (cryptographic digest) for the replay payload.
- Leaderboards should key by `map_hash` (not only `map_id`) to avoid comparing runs across different map builds.
- Replays should declare `(map_id, map_hash)` and be treated as "out of date" if the map hash mismatches.

Non-goals for the initial prototype:
- Full anti-cheat validation via deterministic input re-simulation (we can start with local timing and later layer stronger verification).
