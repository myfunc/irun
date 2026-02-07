# Architecture

## Overview
The prototype uses the **Ursina** Python game engine (built on Panda3D) to get a minimal 3D loop running quickly.

## Code Layout
- `src/irun/__main__.py`: CLI entrypoint (`python -m irun`)
- `src/irun/game.py`: Game bootstrap + minimal scene

## Runtime
- Start: `python -m irun`
- The game loop is driven by Ursina's `update()` callbacks.

## Dependencies
- `ursina`: 3D engine and window/event loop
- `screeninfo`: display/monitor info (required by Ursina on some macOS setups)
