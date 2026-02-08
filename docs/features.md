# Features

## Implemented (Prototype)
- Ivan: boot to a playable first-person 3D graybox
- Ivan: bhop/strafe-style movement prototype
- Ivan: in-game debug/admin panel with live movement parameter tuning
- Ivan: in-game menu on `Esc` (Resume, Map Selector, Key Bindings, Back to Main Menu, Quit)
- Ivan: debug/admin panel moved to `` ` `` (tilde/backtick)
- Ivan: rebindable noclip toggle (default `V`) via in-game Key Bindings
- Ivan: input debug overlay (`F2`) for keyboard/mouse troubleshooting
- Ivan: error console overlay (`F3`) that captures and shows unhandled exceptions without crashing the app (cycles hidden/collapsed/feed)
- Ivan: generated test course with walls and jump obstacles
- Ivan: BSP-to-map-bundle asset pipeline and runtime map loading (`--map`, including assets-relative aliases)
- Ivan: Source material extraction (VTF->PNG conversion), textured rendering, and skybox hookup
- Ivan: GoldSrc/Xash3D importer (WAD texture extraction + resource copying to bundle; incl. sound/model paths)
  - Fixes BSP texture V orientation (prevents upside-down textures)
  - Supports masked transparency for `{` textures via GoldSrc-style blue colorkey / palette index 255
- Ivan: main menu (retro) with map bundle selection and on-demand GoldSrc/Xash3D import from a chosen game directory
  - Fast navigation: hold Up/Down for accelerated scrolling, Left/Right page jump, and `Cmd+F`/`Ctrl+F` search
- Ivan: CLI prefill for GoldSrc/Xash3D import flow (`--hl-root`, `--hl-mod`)
  - Supports common macOS Steam layout where the game content lives under `<Game>.app/Contents/Resources`
- Ivan: optional Steam Half-Life auto-detect (manual action in main menu, not default)
- Ivan: wall-jump cooldown tuning (default `1.0s`) replaces same-wall consecutive jump lock
- Ivan: autojump toggle (hold jump to continue hopping)
- Ivan: vault is disabled by default (runtime toggle in debug menu)

## Planned (High-Level)
- Movement: walk/run, jump, coyote time, jump buffer, air control
- Movement: iterate wallrun/grapple from toggleable prototype hooks
- Camera: follow camera with collision avoidance and smoothing
- Levels: modular blocks, checkpoints, hazards, collectibles
- Maps: format v3 (entities, triggers, lights, chunked baked geometry) + editor workflow
- Time trial: local timer + local PB storage (portal/leaderboards later)
- Rendering: retro texture filtering options (nearest-neighbor, mipmap strategy)
- Game loop: pause, restart, level select
- Debug: in-game tweakables and metrics

## Out of Scope (For Now)
- Multiplayer
- Networked features
- Modding pipeline
