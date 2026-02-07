# Features

## Implemented (Prototype)
- Ivan: boot to a playable first-person 3D graybox
- Ivan: bhop/strafe-style movement prototype
- Ivan: in-game debug/admin panel with live movement parameter tuning
- Ivan: input debug overlay (`F2`) for keyboard/mouse troubleshooting
- Ivan: generated test course with walls and jump obstacles
- Ivan: BSP-to-map-bundle asset pipeline and runtime map loading (`--map`, including assets-relative aliases)
- Ivan: Source material extraction (VTF->PNG conversion), textured rendering, and skybox hookup
- Ivan: GoldSrc/Xash3D importer (WAD texture extraction + resource copying to bundle; incl. sound/model paths)
- Ivan: Half-Life map picker (`--hl-root`) with on-demand GoldSrc import and collision filtering

## Planned (High-Level)
- Movement: walk/run, jump, coyote time, jump buffer, air control
- Movement: iterate wallrun/grapple from toggleable prototype hooks
- Camera: follow camera with collision avoidance and smoothing
- Levels: modular blocks, checkpoints, hazards, collectibles
- Game loop: main menu, pause, restart, level select
- Debug: in-game tweakables and metrics

## Out of Scope (For Now)
- Multiplayer
- Networked features
- Modding pipeline
