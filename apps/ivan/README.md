# IVAN Demo

IVAN is a **first-person 3D runner movement demo** focused on flow-first movement and high skill ceiling through pathing, routing, and timing.

## Project Rules (Non-Negotiable)
- All repository files and documentation are **English by default** (Russian is allowed only in chat).
- Any new gameplay/engine parameter (even if introduced as a bugfix) must be:
  - Globally configurable by default (no hardcoded tuning constants).
  - Exposed in the in-game debug/admin menu so it can be changed at runtime.
- Debug/admin menu UX requirement:
  - Parameters are presented as a multi-column list/table.
  - You can select a parameter and adjust it (numeric) or toggle it (boolean) quickly.

## Goals of This Demo
- Easy to learn, hard to master movement feel
- Bunnyhop/strafe-acceleration inspired control
- Wall jump as an advanced option
- Real-time in-game tuning via debug/admin panel

## Quick Start
Requirements:
- Python 3.9+

Install and run:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m ivan
```

Smoke run:
```bash
python -m ivan --smoke
```

## Code Layout
- `src/ivan/game.py`: App wiring, input, camera, and update loop.
- `src/ivan/world/scene.py`: Scene building and external map loading (Dust2 triangles/materials/skybox).
- `src/ivan/physics/tuning.py`: Movement/physics tuning parameters (editable at runtime via the debug/admin menu).
- `src/ivan/physics/player_controller.py`: Kinematic character movement (step + slide) and jump/wall interactions.
- `src/ivan/ui/debug_ui.py`: Debug/admin UI widgets and HUD labels.

## Controls
- `WASD`: move (US layout). On RU layout you can use `ЦФЫВ`. Arrow keys also work.
- `Shift`: sprint
- `Space`: jump
- `R`: reset to spawn
- `Esc`: toggle pointer lock and debug/admin menu
- `LMB`: mock grapple impulse (only if grapple toggle enabled)

## HUD
- A top-center speed readout is always visible (`Speed: <int> u/s`).
- The value is horizontal speed, rounded down to an integer.
- Detailed movement status (`speed/z-vel/grounded/wall`) is shown in the bottom-left corner during gameplay and hidden while the debug/admin panel is open.

## Debug/Admin Menu
Panel layout:
- The setting list is rendered in dynamic columns.
- Total panel height is capped at two-thirds of the game window height.
- As settings grow, new columns are added so the list does not run to the bottom.
- Hovering a setting name/control shows a tooltip with a short explanation.

Numeric settings include sliders + entry fields for precise tuning:
- Gravity, jump speed, ground/air speed caps
- Ground acceleration, bunnyhop acceleration, friction, air control
- Air counter-strafe brake strength
- Sprint multiplier, mouse sensitivity
- Wall jump boost, coyote time, jump buffer time

Boolean toggles are shown inline as labeled rows with `ON/OFF` buttons:
- Coyote time
- Jump buffer
- Wall jump
- Wallrun (toggle only, prototype hook)
- Vault (toggle only)
- Grapple (toggle + mock impulse)

Movement notes:
- Counter-strafe braking in air aggressively decelerates horizontal speed and does not accelerate in reverse while opposite input is held.
- Default `air_counter_strafe_brake` is set to `5.0`.
- Repeated wall-jumps from the same wall face are temporarily blocked.
- Wallrun is lateral; vertical climb gain is capped.

## Level Layout
The map is generated in code and includes:
- Panda3D sample environment model (`models/environment`) as a base scene
- Long floor lane
- Basic jump obstacles
- Two wall sections for wall-jump experimentation
- Alternate elevated side route
- A simple reset/hard-fail condition if you fall off the course

## External Map Assets
- The repository `de_dust2_largo` is stored under:
  - `assets/maps/de_dust2_largo/`
- Runtime uses generated triangle asset:
  - `assets/generated/de_dust2_largo_map.json`
- This file is built from BSP using:
```bash
python3 tools/build_dust2_assets.py \
  --input assets/maps/de_dust2_largo/csgo/maps/de_dust2_largo.bsp \
  --output assets/generated/de_dust2_largo_map.json \
  --scale 0.03
```
- At startup:
  - If generated asset exists and is valid, IVAN loads Dust2 geometry + collision from the same triangle data.
  - Otherwise, IVAN falls back to sample environment + graybox lane.

Notes:
- Triangle-map collision response uses Bullet convex sweep tests and a Quake3-style kinematic controller
  (step + slide with plane clipping) for stable wall/ceiling/slope handling.
- The build step converts the shipped `assets/maps/de_dust2_largo/csgo/materials/**/*.vtf` into PNG under
  `assets/generated/materials/` so Panda3D can load them.
- The generated Dust2 JSON includes per-triangle materials, UVs, and vertex colors (used as baked lighting).
