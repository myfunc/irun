# Architecture

## Overview
Game apps use **Panda3D** directly to keep iteration fast for movement-focused prototypes.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/mvp/src/mvp/__main__.py`: MVP entrypoint (`python -m mvp`)
- `apps/mvp/src/mvp/game.py`: Game bootstrap + minimal scene
- `apps/ivan/src/ivan/__main__.py`: IVAN demo entrypoint (`python -m ivan`)
- `apps/ivan/src/ivan/game.py`: First-person controller, graybox level generation, debug/admin menu

## Runtime
- Start: `python -m mvp` (from `apps/mvp`)
- Start: `python -m ivan` (from `apps/ivan`)
- The game loop is driven by Panda3D's task manager.

## Dependencies
- `panda3d`: 3D engine and window/event loop (MVP and IVAN demo)
- `bsp_tool`: Source BSP parsing for IVAN Dust2 asset generation pipeline
