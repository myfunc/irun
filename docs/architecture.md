# Architecture

## Overview
UP (the game app) uses the **Ursina** Python game engine (built on Panda3D) to get a minimal 3D loop running quickly.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/up/src/up/__main__.py`: UP entrypoint (`python -m up`)
- `apps/up/src/up/game.py`: Game bootstrap + minimal scene

## Runtime
- Start: `python -m up` (from `apps/up`)
- The game loop is driven by Ursina's `update()` callbacks.

## Dependencies
- `ursina`: 3D engine and window/event loop (UP)
- `screeninfo`: display/monitor info (required by Ursina on some macOS setups) (UP)
