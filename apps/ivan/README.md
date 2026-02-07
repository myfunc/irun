# IVAN Demo

IVAN is a **first-person 3D runner movement demo** focused on flow-first movement and high skill ceiling through pathing, routing, and timing.

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
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m ivan
```

Smoke run:
```bash
python -m ivan --smoke
```

## Controls
- `WASD`: move
- `Shift`: sprint
- `Space`: jump
- `R`: reset to spawn
- `Esc`: toggle pointer lock and debug/admin menu
- `LMB`: mock grapple impulse (only if grapple toggle enabled)

## HUD
- A top-center speed readout is always visible (`Speed: <int> u/s`).
- The value is horizontal speed, rounded down to an integer.

## Debug/Admin Menu
Panel includes sliders + numeric entry fields for precise tuning:
- Gravity, jump speed, ground/air speed caps
- Ground/air acceleration, friction, air control
- Air counter-strafe brake strength
- Sprint multiplier, mouse sensitivity
- Wall jump boost, coyote time, jump buffer time

Toggles:
- Coyote time
- Jump buffer
- Wall jump
- Wallrun (toggle only, prototype hook)
- Vault (toggle only)
- Grapple (toggle + mock impulse)

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
  --input assets/maps/de_dust2_largo/csgo/dist/de_dust2_largo.bsp \
  --output assets/generated/de_dust2_largo_map.json \
  --scale 0.03
```
- At startup:
  - If generated asset exists and is valid, IVAN loads Dust2 geometry + collision from the same triangle data.
  - Otherwise, IVAN falls back to sample environment + graybox lane.
