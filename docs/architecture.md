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
- `apps/launcher/src/launcher/__main__.py`: Launcher Toolbox entrypoint (`python -m launcher`) — Dear PyGui desktop app for one-click map editing, testing, and resource management
- `apps/launcher/src/launcher/app.py`: Dear PyGui window, panels (Settings, Map Browser, Actions, Log), render loop
- `apps/launcher/src/launcher/config.py`: Persistent launcher settings (`~/.irun/launcher/config.json`) — TrenchBroom exe, WAD/materials dirs, Steam root, ericw-tools path
- `apps/launcher/src/launcher/actions.py`: Subprocess spawning for game, TrenchBroom, pack_map, bake_map (output captured to log)
- `apps/launcher/src/launcher/map_browser.py`: Recursive `.map` file discovery sorted by modification time
- `apps/baker/src/baker/__main__.py`: Baker entrypoint (`python -m baker`)
- `apps/baker/src/baker/app.py`: Viewer wiring (Panda3D ShowBase), fly camera, tonemap hotkeys
- `apps/baker/src/baker/render/tonemapping.py`: GLSL 120 post-process view transform (gamma-only/Reinhard/ACES approx)
- `apps/ui_kit/src/irun_ui_kit/`: Internal procedural UI kit (Panda3D DirectGUI) used by Ivan UI screens
- `apps/ivan/src/ivan/__main__.py`: Ivan entrypoint (`python -m ivan`)
- `apps/ivan/src/ivan/__init__.py`: package bootstrap (includes monorepo fallback path injection for `apps/ui_kit/src` when `irun-ui-kit` is not installed in the active venv)
- `apps/ivan/src/ivan/game/`: IVAN client app wiring (Panda3D ShowBase), split into focused modules:
  - `apps/ivan/src/ivan/game/app.py`: composition root (`RunnerDemo`) + frame loop orchestration
  - `apps/ivan/src/ivan/game/netcode.py`: client prediction/reconciliation + remote interpolation helpers
  - `apps/ivan/src/ivan/game/tuning_profiles.py`: tuning profile defaults + persistence helpers
  - `apps/ivan/src/ivan/game/input_system.py`: mouse/keyboard sampling + input command helpers
  - `apps/ivan/src/ivan/game/feel_diagnostics.py`: rolling frame/tick diagnostics buffer and JSON dump utility for movement feel analysis
  - `apps/ivan/src/ivan/game/determinism.py`: per-tick quantized state hashing + rolling determinism trace buffer
- `apps/ivan/src/ivan/game/camera_observer.py`: read-only camera smoothing observer over solved simulation state
  - Also smooths read-only camera roll targets (used for wallrun engagement tilt) without mutating simulation.
- `apps/ivan/src/ivan/game/camera_tilt_observer.py`: read-only movement/wallrun camera tilt observer
  - Computes gentle motion-relative tilt targets and smooths them with a snappy exponential response.
  - Applies visual roll/pitch offsets only; simulation authority remains in movement solver/controller.
- `apps/ivan/src/ivan/game/camera_height_observer.py`: read-only eye-height smoothing observer (slide/vault transitions)
- `apps/ivan/src/ivan/game/camera_feedback_observer.py`: read-only movement feedback observer (speed FOV + unified event envelope for landing/bhop pulses)
- `apps/ivan/src/ivan/game/animation_observer.py`: read-only visual offset observer (camera bob/root-motion layer)
  - `apps/ivan/src/ivan/game/menu_flow.py`: main menu controller + import worker glue
  - `apps/ivan/src/ivan/game/grapple_rope.py`: grapple rope rendering helper
- `apps/ivan/src/ivan/game/feel_metrics.py`: rolling gameplay-feel telemetry (jump/landing/ground flicker/camera jerk proxies)
- `apps/ivan/src/ivan/maps/map_parser.py`: Valve 220 `.map` file parser (TrenchBroom text format)
- `apps/ivan/src/ivan/maps/brush_geometry.py`: CSG brush-to-triangle mesh conversion (half-plane clipping, UV projection, Phong normals)
- `apps/ivan/src/ivan/maps/map_converter.py`: .map to internal map-bundle format converter (orchestrates parser + brush geometry + material defs)
- `apps/ivan/src/ivan/maps/material_defs.py`: `.material.json` loader for PBR overrides (normal, roughness, metallic, emission) alongside WAD base textures
- `apps/ivan/src/ivan/maps/catalog.py`: runtime catalog helpers for shipped bundles and GoldSrc-like map discovery (includes .map file discovery)
- `apps/ivan/src/ivan/state.py`: small persistent user state (last launched map, last game dir/mod, tuning profiles + active profile snapshot, display/video settings)
- `apps/ivan/src/ivan/world/scene.py`: Scene building, external map-bundle loading (`--map`), spawn point/yaw
  - Includes an optional deterministic feel-harness scene (`--feel-harness`) with flat/slope/step/wall/ledge + moving-platform fixtures.
- `apps/ivan/src/ivan/maps/steam.py`: Steam library scanning helpers (manual Half-Life auto-detect)
- `apps/ivan/src/ivan/maps/goldsrc_compile.py`: GoldSrc compiler resolver/helpers (`hlcsg`/`hlbsp`/`hlvis`/`hlrad`) used by TrenchBroom import flow
- `apps/ivan/src/ivan/physics/tuning.py`: Tunable movement/physics parameters (exposed via debug/admin UI)
- `apps/ivan/src/ivan/physics/motion/`: Invariant-based motion configuration and solver layer
  - `config.py`: designer invariants + derived runtime constants (`MotionConfig`)
  - `solver.py`: authority for derived run/jump/gravity/ground-damping operations
  - `intent.py`, `state.py`: motion pipeline contracts for staged refactor
- `apps/ivan/src/ivan/physics/player_controller.py`: Kinematic character controller orchestration (intent -> mode -> solver -> collision)
- `apps/ivan/src/ivan/physics/player_controller_kinematics.py`: Kinematic state mutation mixin (slide solve, jump consume/apply, velocity write helpers)
- `apps/ivan/src/ivan/physics/player_controller_state.py`: Read-only state/query mixin (motion lane name, camera roll/pitch observers, external velocity lane toggles)
- `apps/ivan/src/ivan/physics/player_controller_actions.py`: Player action mixin (jump variants, vault, grapple, slide hull, friction)
- `apps/ivan/src/ivan/physics/player_controller_surf.py`: Air/surf behavior mixin (air steer, surf redirect, wall/surf contact probes)
- `apps/ivan/src/ivan/physics/player_controller_collision.py`: Collision and step-slide mixin (sweep, snap, graybox fallback)
- `apps/ivan/src/ivan/physics/player_controller_momentum.py`: Momentum helper mixin (targeted speed-floor guards for jump transitions; no global per-tick speed lock)
- `apps/ivan/src/ivan/physics/collision_world.py`: Bullet collision query world (convex sweeps against static geometry)
- `apps/ivan/src/ivan/ui/debug_ui.py`: Debug/admin menu UI (CS-style grouped boxes, collapsible sections, scrollable content, real-unit sliders/entries, profile dropdown/save)
- `apps/ivan/src/ivan/ui/main_menu.py`: main menu controller (bundle list + import flow + video settings)
- `apps/ivan/src/ivan/ui/pause_menu_ui.py`: in-game ESC menu (Resume/Map Selector/Key Bindings/Back/Quit) and keybinding controls
  - Menu page uses a two-column action layout to keep all actions visible at gameplay resolutions.
  - Includes a Feel Session tab with route radio options (`A/B/C`), replay export, and feedback-driven tuning tweaks.
- `apps/ivan/src/ivan/ui/feel_capture_ui.py`: in-game quick capture popup (`G`) for route-tagged save/export/apply flow, including one-click `Revert Last` rollback
- `apps/ivan/src/ivan/ui/replay_browser_ui.py`: in-game replay browser overlay (UI kit list menu)
- `apps/ivan/src/ivan/ui/replay_input_ui.py`: in-game replay input HUD (UI kit panel) for recorded command visualization
- `apps/ivan/src/ivan/console/autotune_bindings.py`: console command wiring for route-scoped autotune V1 (`autotune_suggest/apply/eval/rollback`)
- `apps/ivan/src/ivan/replays/demo.py`: input-demo storage (record/save/load/list) using repository-local storage under `apps/ivan/replays/`
- `apps/ivan/src/ivan/replays/telemetry.py`: replay telemetry export pipeline (CSV tick dump + JSON summary metrics)
  - Export summary keeps append-only export metadata history per replay summary file (`route_tag`, optional `route_name`, `run_note`, `feedback_text`, `source_demo`).
- `apps/ivan/src/ivan/replays/compare.py`: replay comparison pipeline
  - route-aware compare path selects runs from exported telemetry summaries for the same route (instead of global latest raw replays)
  - emits latest-vs-reference compare JSON, optional baseline compare JSON, and per-route history context JSON
- `apps/ivan/src/ivan/game/feel_capture_flow.py`: gameplay-side orchestration for save/export/compare/apply actions (used by pause tab + `G` popup)
- `apps/ivan/src/ivan/game/feel_feedback.py`: rule-based free-text feedback interpreter for tuning suggestions
- `apps/ivan/src/ivan/game/autotune.py`: route-scoped autotune core (context load from compare/history, invariant-only bounded suggestions, guardrail evaluation)
- `apps/ivan/src/ivan/game/tuning_backups.py`: tuning snapshot backup/restore helpers (safety rail for auto-apply/autotune iteration)
- `apps/ivan/src/ivan/net/server.py`: authoritative multiplayer server loop (TCP bootstrap + UDP input/snapshots)
- `apps/ivan/src/ivan/net/client.py`: multiplayer client transport for handshake/input send/snapshot poll
- `apps/ivan/src/ivan/net/protocol.py`: multiplayer packet/message schema and payload codecs
- `apps/ivan/src/ivan/common/error_log.py`: small in-memory error feed used to prevent hard crashes and surface unhandled exceptions in-game
- `apps/ivan/src/ivan/ui/error_console_ui.py`: bottom-screen error console (toggle with `F3`)
- `apps/ivan/src/ivan/common/aabb.py`: Shared AABB type used for graybox fallback
- `apps/ivan/tools/build_source_bsp_assets.py`: Source BSP -> IVAN map bundle (triangles + textures; VTF->PNG)
  - Extracts per-face Source lightmaps and basic VMT metadata (e.g. `$basetexture`, translucency hints) into `map.json`.
- `apps/ivan/tools/importers/source/import_source_vmf.py`: Source VMF -> BSP -> IVAN bundle helper
  - Uses Source compile tools (`vbsp`/`vvis`/`vrad`) to compile a VMF first, then invokes `build_source_bsp_assets.py`.
  - Builds in an isolated temporary game root that links VMF-local assets and can optionally reference a real Source game root for fallback content.
- `apps/ivan/tools/importers/goldsrc/import_goldsrc_bsp.py`: GoldSrc/Xash3D BSP -> IVAN map bundle (triangles + WAD textures + resource copy)
  - Notes: GoldSrc masked textures use `{` prefix; importer emits PNG alpha using palette/index rules and runtime enables binary transparency for those materials.
  - Notes: The importer extracts embedded BSP textures when present and falls back to scanning `--game-root` for `.wad` files if the BSP omits the worldspawn `wad` list.
- `apps/ivan/tools/bake_map.py`: Bake pipeline — compiles a .map file with ericw-tools (qbsp → vis → light) then imports the resulting BSP via the GoldSrc importer to produce an .irunmap bundle with production-quality lightmaps.
  - Requires external ericw-tools binaries (qbsp, vis, light) pointed to by `--ericw-tools`.
  - Stages can be skipped individually (`--no-vis`, `--no-light`); light supports `--bounce N` and `--light-extra` (-extra4).
- `apps/ivan/tools/pack_map.py`: Fast-iteration packer — converts a .map file directly to an .irunmap bundle without BSP compilation (no lightmaps).
  - Parses .map with `ivan.maps.map_parser`, converts brushes via `ivan.maps.brush_geometry` (planned), resolves WAD textures, and packs the result.
  - Depends on future `ivan.maps.brush_geometry` and `ivan.maps.material_defs` modules; will degrade gracefully until those are implemented.
- `apps/ivan/tools/testmap.py`: Quick-test launcher — runs `python -m ivan --map <file>` and watches the .map for changes (mtime polling), auto-restarting the game on save.
  - Supports `--bake` (ericw-tools pipeline), `--convert-only`, and `--no-watch` modes.
  - Attempts hot-reload via the console bridge (`map_reload` command) before falling back to kill + restart.
- `apps/ivan/tools/importers/goldsrc/import_trenchbroom_map.py`: TrenchBroom Valve220 `.map` -> GoldSrc BSP compile (`hlcsg`/`hlbsp`/`hlvis`/`hlrad`) -> IVAN bundle helper
  - Supports both classic `hl*` binaries and SDHLT `sdHL*` binaries (auto-handles toolchain CLI differences).

## Runtime
- Start: `python -m ivan` (from `apps/ivan`)
- Repo root helper: `./runapp ivan` (recommended for quick iteration)
- The game loop is driven by Panda3D's task manager.
- Movement simulation runs at a fixed `60 Hz` tick to support deterministic input replay.
- Movement refactor rollout is staged:
  - active movement tuning is invariant-first: run, stop damping, jump, air gain/cap, wallrun sink, and slide are derived from timing/target invariants
  - `PlayerController` now uses `MotionSolver` for derived ground run, ground coasting damping, jump takeoff speed, air gain/cap, wallrun sink response, and gravity
  - gameplay and authoritative server ticks now feed movement through `MotionIntent` (`step_with_intent`) instead of ad-hoc feature velocity calls
  - deceleration policy is explicit:
    - regular grounded coasting/run is a deceleration lane
    - slide uses invariant damping + slope-aligned acceleration (downhill gains, uphill losses)
    - walljump keeps targeted total-speed floor preservation at jump transition only
    - collision clipping is non-energy-gaining (`overbounce=1.0`) to reduce high-speed ricochet escalation
  - slide invariant (`slide_stop_t90`) derives grounded slide speed decay; slide is hold-driven, preserves carried speed, and owns low-profile hull state while active
  - shared leniency invariant (`grace_period`) drives jump buffer, coyote window, and vault grace checks from one slider, with runtime distance-derivation (`grace_distance = grace_period * Vmax`) for speed-aware grace timing
  - optional character scale lock derives geometry-facing values (`player_radius`, `step_height`) from `player_half_height` while keeping motion feel invariants independent
  - debug tuning UI is intentionally narrow: invariant-first controls plus harness isolation toggles (legacy direct scalars and niche sliders are hidden), with one explicit utility control for `noclip_speed`
  - character group also exposes `step_height` for live step-up/ground-contact tuning without reopening broader legacy slider surface
  - slide lane includes short ground-loss grace so transient slope contact jitter does not flap slide hull state (crouch/stand spam)
  - step-slide resolver now compares path progress along intended horizontal move direction and preserves grounded state from the selected path, matching Quake-style step intent under oblique stair contact
  - ground trace/snap use footprint multi-probe fallback (plus a small lifted re-probe) when center downward sweeps are blocked by step faces, keeping grounded classification stable on angled stair edges
  - ground contact filtering rejects near-level off-center side grazes from downward probes, preventing false grounded states along wall/ledge seams
  - wallrun gating splits acquire vs sustain: stricter entry heuristics (intent/speed/approach/parallel) and softer sustain thresholds for curved wall continuity, with tunable gate fields
  - legacy direct run/gravity tuning fields are migrated to invariants and no longer part of active tuning schema
  - legacy air gain scalars are migrated (`max_air_speed`, `jump_accel`, `air_control`, `air_counter_strafe_brake`) and removed from active tuning schema
- Feel diagnostics:
  - `F2` overlay now includes frame-time p95, sim steps per frame, motion state, accel, contacts, floor/wall normals, leniency timers, and determinism hash status.
  - `F10` dumps the rolling 2-5 second diagnostics buffer to `apps/ivan/replays/telemetry_exports/*_feel_rolling.json`.
  - `F11` dumps rolling determinism trace hashes to `apps/ivan/replays/telemetry_exports/*_det_trace.json`.
- Multiplayer networking:
  - TCP bootstrap for join/session token assignment.
  - Bootstrap welcome includes server map reference (`map_json`) so connecting clients can auto-load matching content.
  - Bootstrap welcome includes per-player authoritative spawn + yaw so clients can align immediately on join.
  - Dedicated/embedded server supports direct `.map` authoring inputs by converting the map for authoritative spawn/collision at startup (same scale/spawn offset parity as client runtime map loading).
  - `.map` host startup is fail-fast: conversion errors or empty collision results raise and abort host startup (no silent empty-world server fallback).
  - Embedded host handoff seeds authoritative spawn from current local player transform when host mode is toggled mid-run (prevents forced map-start respawn on host open).
  - Per-player spawn assignment applies deterministic small ring offsets for later joins so multiple clients do not overlap one spawn point.
  - Bootstrap welcome also includes tuning ownership (`can_configure`) and initial authoritative tuning snapshot/version.
  - UDP packets for gameplay input and world snapshots.
  - Snapshot replication runs at `30 Hz` to reduce visible interpolation stutter.
  - Server simulates movement authoritatively at `60 Hz`; clients use prediction + reconciliation for local player and snapshot-buffer interpolation for remote players.
  - Server broadcasts authoritative tuning snapshot/version in UDP snapshots; clients apply updates in-flight.
  - Only server config owner may submit tuning updates; non-owner clients are read-only for runtime config.
  - Debug-profile switches in multiplayer use the same ownership flow: owner sends full snapshot to server and waits for `cfg_v` ack; non-owners are blocked and re-synced to authoritative tuning.
  - Respawn requests are sent to server over TCP; server performs authoritative respawn and replicates result.
  - Client `R` respawn uses immediate local predictive reset to keep controls responsive while waiting for authoritative `rs` confirmation.
  - Connected clients skip local kill-plane auto-respawn; death/respawn stays server-authoritative.
  - Player snapshots include respawn sequence (`rs`) to force immediate authoritative client reset after respawn events.
  - Local reconciliation uses sequence-based prediction history: rollback to authoritative acked state, replay unacked inputs, then apply short visual error decay.
  - Movement authority stays deterministic and code-first (Bullet remains collision/query layer only), which keeps advanced movement mechanics and multiplayer reconciliation aligned.
  - Replay during reconciliation runs without per-step render snapshot pushes; a single snapshot is captured after replay completes to reduce jitter/perf spikes.
  - Local first-person render path uses a short camera shell smoothing layer in online mode; reconciliation offsets are not applied directly to the camera.
  - Remote interpolation delay is adaptive (derived from observed snapshot interval mean/stddev), and server-tick estimation uses smoothed offset tracking.
  - Server snapshot replication supports AOI relevance filtering on GoldSrc bundles when visibility cache exists:
    - uses the same `visibility.goldsrc.json`/leaf VIS data model as render culling
    - includes local player unconditionally in each client snapshot stream
    - keeps short-range distance fallback to avoid over-culling near VIS boundaries
  - Client records network diagnostics (snapshot cadence, correction magnitude, replay cost) and exposes a rolling one-second summary in the `F2` input debug overlay.
  - Client-host mode: the game can run an embedded local server thread on demand; `Esc` menu `Open To Network` toggles host mode ON/OFF.
  - Client join mode: `Esc` menu `Multiplayer` tab allows runtime remote connect/disconnect by host+port (no restart required).
  - Host toggle force-restarts embedded host state before connect, and if bind fails (busy port) it exits without auto-joining unknown local servers.
  - Default multiplayer port uses env var `DEFAULT_HOST_PORT` (fallback `7777`).
- Console control / MCP:
  - Runtime includes a minimal command console engine (`apps/ivan/src/ivan/console/`) for command + cvar execution.
  - IVAN client process starts a localhost control bridge (JSON-lines TCP) for driving the console externally.
    - Env: `IRUN_IVAN_CONSOLE_PORT` (default `7779`).
    - Protocol: request `{"line":"echo hi","role":"client","origin":"mcp"}` -> response `{"ok":true,"out":["hi"]}`.
  - Dedicated server process also starts a localhost control bridge on `IRUN_IVAN_SERVER_CONSOLE_PORT` (default `39001`).
  - Replay telemetry export commands are available in the client console:
    - `replay_export_latest [out_dir]`
    - `replay_export <replay_path> [out_dir]`
    - `replay_compare_latest [out_dir] [route_tag]` (route-scoped exported-run compare when route is provided)
    - `feel_feedback "<text>" [route_tag]`
    - `tuning_backup [label]` (save current tuning snapshot to `~/.irun/ivan/tuning_backups/`)
    - `tuning_restore [name_or_path]` (restore latest or chosen snapshot)
    - `tuning_backups [limit]` (list recent backups)
    - `autotune_suggest <route_tag> <feedback_text> [out_dir]` (route-scoped invariant-only proposal from compare/history context)
    - `autotune_apply <route_tag> <feedback_text> [out_dir]` (backup-first apply of current route-scoped suggestion)
    - `autotune_eval <route_tag> [out_dir]` (guardrail checks + weighted route score)
    - `autotune_rollback [backup_ref]` (alias over backup restore flow; defaults to latest backup)
  - `ivan-mcp` runs an MCP stdio server (Python 3.9, no deps) that exposes a single tool: `console_exec`.
- CLI telemetry export:
  - `python -m ivan --export-latest-replay-telemetry [--replay-telemetry-out <dir>]` exports latest replay metrics and exits.
  - `python -m ivan --compare-latest-replays [--replay-telemetry-out <dir>] [--replay-route-tag A]` auto-exports latest+previous and writes comparison JSON.
  - `python -m ivan --verify-latest-replay-determinism [--determinism-runs N] [--replay-telemetry-out <dir>]` re-simulates latest replay offline multiple times and emits a determinism report JSON.
  - `python -m ivan --verify-replay-determinism <path> [--determinism-runs N] [--replay-telemetry-out <dir>]` runs the same determinism check for a specific replay file.
- Display/window:
  - Default: windowed 1280x720 on all platforms (Windows + macOS). Window is user-resizable.
  - Display settings (fullscreen, resolution) persist in `~/.irun/ivan/state.json` and are applied on startup.
  - Main menu "Video Settings" screen allows switching between windowed presets and fullscreen at runtime.
- In-game UI/input split:
  - `Esc` opens gameplay menu and unlocks cursor.
  - `` ` `` opens debug/admin tuning menu and unlocks cursor.
  - `G` opens quick feel-capture popup during active gameplay (route/name/notes/feedback + save/export/apply + `Revert Last` buttons).
  - entering quick feel-capture (`G`) snapshots/cuts the active replay recording immediately; export actions operate on that frozen run to avoid post-finish input contamination.
  - while quick feel-capture is open, respawn hotkey handling is blocked so text-entry keys do not trigger gameplay restarts.
  - mouse center-snap look capture is automatically suspended when the window is unfocused/minimized and resumes with a one-frame recenter guard on focus return.
  - While either menu is open, gameplay input is blocked but simulation continues.
  - `Esc` menu can open a replay browser (`Replays`) to load saved input demos.
  - `Esc` menu Feel Session tab can export current run telemetry and apply feedback-based tuning changes.
  - Any feedback-driven apply path creates a pre-apply tuning backup snapshot for rollback safety.
  - quick capture `Export + Apply` treats `run note` as fallback feedback text when feedback field is empty, then tries feel-feedback intents first and invariant-autotune suggestions as fallback.
  - feedback intent parser includes explicit wallrun/false-ground phrase handling (including "wallrun is not engaging" / "fall off wall" variants) so in-game `Export + Apply` does not silently no-op on common phrasing variants.
  - Apply-feedback flow auto-runs route-scoped compare (latest route run vs prior route run) and reports deltas.
  - Route compare can also emit baseline + route-history context files for longer tuning sessions.
  - Replay playback shows a dedicated replay input HUD and keeps gameplay/menu inputs locked until exit (`R`).
  - Replay input HUD prefers explicitly recorded held states (`WASD`, arrows, mouse buttons) over derived movement axes.
  - `F2` input debug overlay includes rolling gameplay-feel telemetry (for movement/camera tuning passes).
  - Gameplay movement step supports optional noclip mode, optional autojump queueing, surf behavior on configured slanted surfaces, and grapple-rope constraint movement.
  - Grapple targeting uses collision-world ray queries (`ray_closest`) from camera center.
  - Camera feedback effects are read-only and isolated behind compact camera invariants (`camera_feedback_enabled`, `camera_base_fov`, `camera_speed_fov_max_add`, `camera_tilt_gain`, `camera_event_gain`).
  - Wallrun behavior is enabled by default in base tuning (`wallrun_enabled=True`), with per-profile overrides still supported (for example `surf_sky2_server` keeps wallrun disabled).

## Rendering Notes
- Baker (paused) shares Ivan's scene builder (`ivan.world.scene.WorldScene`) to keep map preview WYSIWYG.
- Baker adds a viewer-only post-process view transform (tonemap + gamma) toggled via `1`/`2`/`3`.
- Texture sizing: IVAN disables Panda3D's default power-of-two rescaling for textures (`textures-power-2 none`).
  - Reason: imported GoldSrc maps commonly reference non-power-of-two textures; automatic rescaling breaks BSP UV mapping.
- Coordinate system: IVAN uses Panda3D's default world axes (`X` right, `Y` forward, `Z` up). GoldSrc BSP imports keep the same axes and only apply a uniform scale.
- Imported BSP bundles render with baked lightmaps (Source/GoldSrc) and disable dynamic scene lights for map geometry.
- If a face references missing lightmap files at runtime, IVAN skips lightmap shading for that face and falls back to base-texture rendering (avoids full-black output for partial bundles).
- Optional visibility culling:
  - GoldSrc bundles can use BSP PVS (VISIBILITY + leaf face lists) to avoid rendering world geometry behind walls.
  - Currently disabled by default; `vis_culling_enabled` is available in tuning/profile data (not in the compact invariant debug menu).
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
- `goldsrc_wad`: WAD file parsing for GoldSrc texture extraction (used by both BSP importer and direct .map loader)
- `dearpygui`: GPU-accelerated immediate-mode GUI used by the Launcher Toolbox (`apps/launcher`)

No new dependencies were added for the TrenchBroom direct .map pipeline — it reuses existing `Pillow` and `goldsrc_wad`.

## Maps
Maps are distributed as **map bundles** rooted at a `map.json` manifest plus adjacent assets (textures/resources).

**Default distribution format is `.irunmap`** (packed zip archive). Directory bundles are only used during development/debugging when explicitly requested.

Bundle storage formats:
- **Directory bundle** (dev only): `<bundle>/map.json` plus folders like `materials/`, `lightmaps/`, `resources/`.
- **Packed bundle** (default): a single `.irunmap` file (zip archive) containing `map.json` at the archive root plus the same folder layout.
  - Runtime extracts `.irunmap` bundles to a local cache under `~/.irun/ivan/cache/bundles/<hash>/` before loading assets.

Level editing uses **TrenchBroom** as the external editor. `.map` files (Valve 220 format) are the **primary authoring format** for IVAN-original maps. The engine can load `.map` files directly — no BSP compilation step is needed for development.

TrenchBroom game configuration files live in `apps/ivan/trenchbroom/`:
- `GameConfig.cfg`: TrenchBroom game definition (Valve 220 format, WAD textures, editor tags)
- `ivan.fgd`: Entity definitions (spawns, triggers, lights, brush entities with `_phong` / `_phong_angle` support)
- `README.md`: Setup instructions for installing the IVAN game profile into TrenchBroom

### Map Pipeline

Three workflows exist depending on the use case:

- **Dev workflow (direct .map loading)**: TrenchBroom saves a `.map` file → IVAN loads it directly at runtime (parser → CSG half-plane clipping → triangulated mesh). Textures come from WAD files referenced in the map's worldspawn. Lighting is flat ambient (no bake). This is the fastest iteration path — save in TrenchBroom, reload in-game.
- **Pack workflow**: `.map` → `tools/pack_map.py` → `.irunmap` bundle (no lightmaps). Used to distribute maps without requiring end-users to have WAD files or the raw `.map` source.
- **Bake workflow** (optional, production): `.map` → ericw-tools (qbsp → vis → light) → `.bsp` → GoldSrc importer → `.irunmap` bundle with production-quality baked lightmaps. Use `tools/bake_map.py`.
- **Legacy BSP import**: `.bsp` → GoldSrc/Source importer → `.irunmap` bundle (unchanged).

### Material System

IVAN supports optional `.material.json` sidecar files for PBR properties alongside WAD base textures.

- Location: `materials/<texture_name>.material.json` inside the map bundle or alongside WAD textures.
- Supported PBR maps: `normal_map`, `roughness_map`, `metallic_map`, `emission_map`.
- Scalar fallbacks: `roughness` (0.0–1.0), `metallic` (0.0–1.0), `emission_color`.
- Lookup order: exact name match → casefold match → fallback to WAD base texture only.
- The material definition system is loaded by `ivan.maps.material_defs`.

### Map Format v3 (Unpaused)
Format v3 development can proceed now that TrenchBroom integration is complete. The planned extensions are:
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
  - `Shift+F4`: restart (respawn + cancel attempt)
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
