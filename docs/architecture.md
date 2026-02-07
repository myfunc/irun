# Architecture

## Overview
Game apps use **Panda3D** directly to keep iteration fast for movement-focused prototypes.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/ivan/src/ivan/__main__.py`: Ivan entrypoint (`python -m ivan`)
- `apps/ivan/src/ivan/game.py`: App wiring (Panda3D ShowBase), input, camera, and frame update loop
- `apps/ivan/src/ivan/world/scene.py`: Scene building, external map-bundle loading (`--map`), spawn point/yaw
- `apps/ivan/src/ivan/physics/tuning.py`: Tunable movement/physics parameters (exposed via debug/admin UI)
- `apps/ivan/src/ivan/physics/player_controller.py`: Kinematic character controller (Quake3-style step + slide)
- `apps/ivan/src/ivan/physics/collision_world.py`: Bullet collision query world (convex sweeps against static geometry)
- `apps/ivan/src/ivan/ui/debug_ui.py`: Debug/admin menu UI (sliders, entries, toggles, HUD labels)
- `apps/ivan/src/ivan/common/aabb.py`: Shared AABB type used for graybox fallback
- `apps/ivan/tools/build_source_bsp_assets.py`: Source BSP -> IVAN map bundle (triangles + textures; VTF->PNG)
- `apps/ivan/tools/importers/goldsrc/import_goldsrc_bsp.py`: GoldSrc/Xash3D BSP -> IVAN map bundle (triangles + WAD textures + resource copy)

## Runtime
- Start: `python -m ivan` (from `apps/ivan`)
- The game loop is driven by Panda3D's task manager.

## Dependencies
- `panda3d`: 3D engine and window/event loop
- `panda3d.bullet`: Bullet integration used by IVAN for robust character collision queries (convex sweeps, step+slide).
- `bsp_tool`: BSP parsing for IVAN map import pipelines (Source + GoldSrc branches)
- `Pillow`: image IO used by map import tools (VTF/WAD -> PNG)
