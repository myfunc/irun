# Features

## Implemented (Prototype)
- Ivan: boot to a playable first-person 3D graybox
- Ivan: bhop/strafe-style movement prototype
- Ivan: in-game debug/admin panel with live movement parameter tuning
- Ivan: debug-tuned parameters persist to local state and load as next-run defaults
- Ivan: debug panel upgraded to grouped, collapsible, scrollable CS-style boxed layout with normalized sliders
- Ivan: debug profile manager with default presets (`surf_bhop`, `bhop`, `surf`, `surf_sky2_server`) and persistent custom profile saves
- Ivan: in-game menu on `Esc` (Resume, Map Selector, Key Bindings, Back to Main Menu, Quit)
- Ivan: debug/admin panel moved to `` ` `` (tilde/backtick)
- Ivan: rebindable noclip toggle (default `V`) via in-game Key Bindings
- Ivan: in-game menu/debug UI block gameplay input but keep simulation running (no pause)
- Ivan: classic center crosshair (Half-Life/CS style) visible during active gameplay
- Ivan: input debug overlay (`F2`) for keyboard/mouse troubleshooting
- Ivan: error console overlay (`F3`) that captures and shows unhandled exceptions without crashing the app (cycles hidden/collapsed/feed)
- Ivan: generated test course with walls and jump obstacles
- Ivan: BSP-to-map-bundle asset pipeline and runtime map loading (`--map`, including assets-relative aliases)
- Ivan: packed map bundles (`.irunmap`) for imported maps (zip archive with runtime auto-extract cache)
- Ivan: Source material extraction (VTF->PNG conversion), textured rendering, and skybox hookup
  - Basic VMT parsing for translucency/additive/alphatest and `$basetexture` indirection
  - Source baked lightmap extraction and runtime lightmap rendering (base texture * lightmap)
- Ivan: GoldSrc/Xash3D importer (WAD texture extraction + resource copying to bundle; incl. sound/model paths)
  - Fixes BSP texture V orientation (prevents upside-down textures)
  - Supports masked transparency for `{` textures via GoldSrc-style blue colorkey / palette index 255
  - Converts GoldSrc skybox textures from `gfx/env/` into bundle `materials/skybox/` (when present)
  - Extracts baked GoldSrc lightmaps (RGB) into bundle `lightmaps/` and renders them in runtime (supports up to 4 light styles per face)
- Ivan: GoldSrc PVS visibility culling (BSP VISIBILITY + leaf surface lists) to avoid rendering geometry hidden behind walls (when cache is available)
- Ivan: main menu (retro) with map bundle selection and on-demand GoldSrc/Xash3D import from a chosen game directory
  - Fast navigation: hold Up/Down for accelerated scrolling, Left/Right page jump, and `Cmd+F`/`Ctrl+F` search
  - Delete imported/generated map bundles from the UI (safe delete: `assets/imported/**` and `assets/generated/*`)
- Ivan: CLI prefill for GoldSrc/Xash3D import flow (`--hl-root`, `--hl-mod`)
  - Supports common macOS Steam layout where the game content lives under `<Game>.app/Contents/Resources`
- Ivan: optional Steam Half-Life auto-detect (manual action in main menu, not default)
- Ivan: wall-jump cooldown tuning (default `1.0s`) replaces same-wall consecutive jump lock
- Ivan: wall-jump is gated to airborne state (grounded wall contact cannot trigger wall-jump)
- Ivan: autojump queues only while grounded (prevents airborne corner wall-jump retriggers)
- Ivan: autojump toggle (hold jump to continue hopping)
- Ivan: vault is disabled by default (runtime toggle in debug menu)
- Ivan: surf prototype on slanted surfaces (strafe-held surf with live tuning controls)
- Ivan: legacy-style surf preset (`surf_sky2_server`) approximating public surf_ski_2/surf_sky_2 server cvars
- Ivan: surf steering preserves inertia (momentum can redirect on ramps without single-frame horizontal direction flips)
- Ivan: surf vertical input redirection applies uphill only; downhill acceleration remains gravity-driven
- Ivan: surf-specific acceleration/gravity modifiers stop immediately after contact is lost (no post-leave surf boost)
- Game modes: maps can declare how they should run via bundle metadata (`run.json`)
  - `free_run`: default "just run around"
  - `time_trial`: local time trial with restart and local PB/leaderboard (per `map_id`)

## Planned (High-Level)
- Movement: walk/run, jump, jump buffer, air control
- Movement: iterate wallrun/grapple from toggleable prototype hooks
- Camera: follow camera with collision avoidance and smoothing
- Levels: modular blocks, checkpoints, hazards, collectibles
- Maps: format v3 (entities, triggers, lights, chunked baked geometry) + editor workflow
- Tools: Baker app (map viewer + import manager + configurable lighting rebake with light rig overrides and quality presets)
- Time trial: portal/leaderboards (plus ghosts/replays; map_hash binding)
- Rendering: retro texture filtering options (nearest-neighbor, mipmap strategy)
- Game loop: pause, restart, level select
- Debug: in-game tweakables and metrics

## Out of Scope (For Now)
- Multiplayer
- Networked features
- Modding pipeline
