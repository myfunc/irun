# Architecture

## Overview
Game apps use **Panda3D** directly to keep iteration fast for movement-focused prototypes.

## UI Kit
We maintain an internal procedural UI kit under `apps/ui_kit/` to standardize:
- layout constants (padding/margins/gaps)
- theme tokens (palette + typography)
- reusable primitives (windows/panels/buttons/text inputs)

Policy:
- Ivan should prefer using the UI kit for **all non-HUD UI** (main menu, pause menu, debug/admin panels, etc).
- If a shared UI feature is missing, implement it in `apps/ui_kit` rather than shipping one-off game-side UI.
- Exclusions in this policy pass: gameplay log/error overlays, crosshair, and in-game hint overlays.

See: `docs/ui-kit.md`.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/baker/src/baker/__main__.py`: Baker entrypoint (`python -m baker`)
- `apps/baker/src/baker/app.py`: Viewer wiring (Panda3D ShowBase), fly camera, tonemap hotkeys
- `apps/baker/src/baker/render/tonemapping.py`: GLSL 120 post-process view transform (gamma-only/Reinhard/ACES approx)
- `apps/ui_kit/src/irun_ui_kit/`: Internal procedural UI kit (Panda3D DirectGUI) used by Ivan UI screens
- `apps/ivan/src/ivan/__main__.py`: Ivan entrypoint (`python -m ivan`)
- `apps/ivan/src/ivan/__init__.py`: package bootstrap (includes monorepo fallback path injection for `apps/ui_kit/src` when `irun-ui-kit` is not installed in the active venv)
- `apps/ivan/src/ivan/game.py`: App wiring (Panda3D ShowBase), input, camera, and frame update loop
- `apps/ivan/src/ivan/maps/catalog.py`: runtime catalog helpers for shipped bundles and GoldSrc-like map discovery
- `apps/ivan/src/ivan/state.py`: small persistent user state (last launched map, last game dir/mod, tuning profiles + active profile snapshot)
- `apps/ivan/src/ivan/world/scene.py`: Scene building, external map-bundle loading (`--map`), spawn point/yaw
- `apps/ivan/src/ivan/maps/steam.py`: Steam library scanning helpers (manual Half-Life auto-detect)
- `apps/ivan/src/ivan/physics/tuning.py`: Tunable movement/physics parameters (exposed via debug/admin UI)
- `apps/ivan/src/ivan/physics/player_controller.py`: Kinematic character controller (Quake3-style step + slide)
- `apps/ivan/src/ivan/physics/collision_world.py`: Bullet collision query world (convex sweeps against static geometry)
- `apps/ivan/src/ivan/ui/debug_ui.py`: Debug/admin menu UI (CS-style grouped boxes, collapsible sections, scrollable content, normalized sliders, profile dropdown/save)
- `apps/ivan/src/ivan/ui/main_menu.py`: main menu controller (bundle list + import flow)
- `apps/ivan/src/ivan/ui/pause_menu_ui.py`: in-game ESC menu (Resume/Map Selector/Key Bindings/Back/Quit) and keybinding controls
- `apps/ivan/src/ivan/ui/replay_browser_ui.py`: in-game replay browser overlay (UI kit list menu)
- `apps/ivan/src/ivan/replays/demo.py`: input-demo storage (record/save/load/list) using repository-local storage under `apps/ivan/replays/`
- `apps/ivan/src/ivan/net/server.py`: authoritative multiplayer server loop (TCP bootstrap + UDP input/snapshots)
- `apps/ivan/src/ivan/net/client.py`: multiplayer client transport for handshake/input send/snapshot poll
- `apps/ivan/src/ivan/net/protocol.py`: multiplayer packet/message schema and payload codecs
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
- Repo root helper: `./runapp ivan` (recommended for quick iteration)
- The game loop is driven by Panda3D's task manager.
- Movement simulation runs at a fixed `60 Hz` tick to support deterministic input replay.
- Multiplayer networking:
  - TCP bootstrap for join/session token assignment.
  - Bootstrap welcome includes server map reference (`map_json`) so connecting clients can auto-load matching content.
  - Bootstrap welcome also includes tuning ownership (`can_configure`) and initial authoritative tuning snapshot/version.
  - UDP packets for gameplay input and world snapshots.
  - Snapshot replication runs at `30 Hz` to reduce visible interpolation stutter.
  - Server simulates movement authoritatively at `60 Hz`; clients use prediction + reconciliation for local player and snapshot-buffer interpolation for remote players.
  - Server broadcasts authoritative tuning snapshot/version in UDP snapshots; clients apply updates in-flight.
  - Only server config owner may submit tuning updates; non-owner clients are read-only for runtime config.
  - Debug-profile switches in multiplayer use the same ownership flow: owner sends full snapshot to server and waits for `cfg_v` ack; non-owners are blocked and re-synced to authoritative tuning.
  - Respawn requests are sent to server over TCP; server performs authoritative respawn and replicates result.
  - Client `R` respawn uses immediate local predictive reset to keep controls responsive while waiting for authoritative `rs` confirmation.
  - Player snapshots include respawn sequence (`rs`) to force immediate authoritative client reset after respawn events.
  - Local reconciliation uses sequence-based prediction history: rollback to authoritative acked state, replay unacked inputs, then apply short visual error decay.
  - Replay during reconciliation runs without per-step render snapshot pushes; a single snapshot is captured after replay completes to reduce jitter/perf spikes.
  - Local first-person render path uses a short camera shell smoothing layer in online mode; reconciliation offsets are not applied directly to the camera.
  - Remote interpolation delay is adaptive (derived from observed snapshot interval mean/stddev), and server-tick estimation uses smoothed offset tracking.
  - Client records network diagnostics (snapshot cadence, correction magnitude, replay cost) and exposes a rolling one-second summary in the `F2` input debug overlay.
  - Client-host mode: the game can run an embedded local server thread on demand; `Esc` menu `Open To Network` toggles host mode ON/OFF.
  - Client join mode: `Esc` menu `Multiplayer` tab allows runtime remote connect/disconnect by host+port (no restart required).
  - Host toggle handles busy local ports gracefully by attempting to join an already running local server.
  - Default multiplayer port uses env var `DEFAULT_HOST_PORT` (fallback `7777`).
- In-game UI/input split:
  - `Esc` opens gameplay menu and unlocks cursor.
  - `` ` `` opens debug/admin tuning menu and unlocks cursor.
  - While either menu is open, gameplay input is blocked but simulation continues.
  - `Esc` menu can open a replay browser (`Replays`) to load saved input demos.
  - Gameplay movement step supports optional noclip mode, optional autojump queueing, surf behavior on configured slanted surfaces, and grapple-rope constraint movement.
  - Grapple targeting uses collision-world ray queries (`ray_closest`) from camera center.

## Rendering Notes
- Baker shares Ivan's scene builder (`ivan.world.scene.WorldScene`) to keep map preview WYSIWYG.
- Baker adds a viewer-only post-process view transform (tonemap + gamma) toggled via `1`/`2`/`3`.
- Texture sizing: IVAN disables Panda3D's default power-of-two rescaling for textures (`textures-power-2 none`).
  - Reason: imported GoldSrc maps commonly reference non-power-of-two textures; automatic rescaling breaks BSP UV mapping.
- Imported BSP bundles render with baked lightmaps (Source/GoldSrc) and disable dynamic scene lights for map geometry.
- Optional visibility culling:
  - GoldSrc bundles can use BSP PVS (VISIBILITY + leaf face lists) to avoid rendering world geometry behind walls.
  - The runtime stores a derived cache next to the bundle as `visibility.goldsrc.json` (directory bundle) or next to the extracted cache (packed bundle).
- Per-map run options can be stored in:
  - directory bundles: `<bundle>/run.json`
  - packed bundles (`.irunmap`): `<bundle>.run.json` (sidecar file next to the archive)

## Dependencies
- `panda3d`: 3D engine and window/event loop
- `irun-ui-kit`: internal reusable DirectGUI component library used by Ivan menus/debug UI
- `panda3d.bullet`: Bullet integration used by IVAN for robust character collision queries (convex sweeps, step+slide).
- `bsp_tool`: BSP parsing for IVAN map import pipelines (Source + GoldSrc branches)
- `Pillow`: image IO used by map import tools (VTF/WAD -> PNG)

## Maps (Planned: Format v3)
Maps are distributed as **map bundles** rooted at a `map.json` manifest plus adjacent assets (textures/resources).

Bundle storage formats:
- **Directory bundle**: `<bundle>/map.json` plus folders like `materials/`, `lightmaps/`, `resources/`.
- **Packed bundle**: a single `.irunmap` file (zip archive) containing `map.json` at the archive root plus the same folder layout.
  - Runtime extracts `.irunmap` bundles to a local cache under `~/.irun/ivan/cache/bundles/<hash>/` before loading assets.

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
  - `visibility`: optional visibility/culling config (JSON object)
    - `enabled`: boolean (default true)
    - `mode`: `"auto"` or `"goldsrc_pvs"`
    - `build_cache`: boolean (default true; if false, runtime will not parse `source_bsp` to build the cache)

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
