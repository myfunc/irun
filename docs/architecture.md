# Architecture

## Overview
MVP (the game app) uses **Panda3D** directly to get a minimal 3D loop running quickly, with a lightweight
movement controller and runtime tuning overlay.

## Code Layout
- Monorepo: apps are under `apps/`
- `apps/mvp/src/mvp/__main__.py`: MVP entrypoint (`python -m mvp`)
- `apps/mvp/src/mvp/game.py`: Game bootstrap, movement controller, tuning overlay, JSON settings

## Runtime
- Start: `python -m mvp` (from `apps/mvp`)
- The game loop is driven by Panda3D's task manager.
- Settings load from `mvp_settings.json` by default (path override via `--settings`).

## Dependencies
- `panda3d`: 3D engine and window/event loop (MVP)
