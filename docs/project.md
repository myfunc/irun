# Project

## One-Liner
IRUN is a monorepo for the project with multiple game prototypes; current focus includes flow-driven 3D movement and traversal challenges.

## Status
Prototype / initialization phase.

## Pillars
- Movement first: tight controls, predictable physics, forgiving camera.
- Readable levels: strong silhouettes, clear affordances, low ambiguity.
- Short iteration loop: fast to run, easy to tweak.

## Target (Initial)
- Platform: Desktop (macOS/Windows/Linux)
- Runtime: Python

## Apps
- `apps/ivan`: Primary game project (first-person flow-runner movement demo with real-time physics tuning)
- `apps/baker`: Companion tool (map viewer MVP; paused; bake/pack pipelines live in `apps/ivan/tools/`)
- `apps/ui_kit`: Internal procedural UI kit (Panda3D DirectGUI) used by Ivan for most non-HUD UI

## Constraints (Initial)
- Keep dependencies minimal and well-documented.
- Prefer deterministic gameplay rules over emergent physics chaos.
- UI policy (project-wide):
  - Prefer **zero custom UI** in game code: build menus/panels/screens using `apps/ui_kit`.
  - If a global UI feature is missing, add it to `apps/ui_kit` (not as one-off game UI code).
  - Exclusions (do not migrate in this policy pass): gameplay log/error overlays, crosshair, and in-game hint overlays.
