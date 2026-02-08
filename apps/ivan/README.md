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

Default boot:
- `python -m ivan` now boots into the **main menu**.
- The menu includes `Quick Start: Bounce` if `assets/imported/halflife/valve/bounce/map.json` exists.
- You can still run a bundle directly via `--map`.

Smoke run:
```bash
python -m ivan --smoke
```

Smoke run with a screenshot (offscreen):
```bash
python -m ivan --smoke --smoke-screenshot /tmp/ivan-smoke.png
```

Prefill the menu with a Half-Life install (imports GoldSrc/Xash3D maps on demand):
```bash
python -m ivan --hl-root "/Users/myfunc/Library/Application Support/Steam/steamapps/common/Half-Life" --hl-mod valve
```

## Code Layout
- `src/ivan/game.py`: App wiring, input, camera, and update loop.
- `src/ivan/world/scene.py`: Scene building and external map loading (`--map` bundles).
- `src/ivan/physics/tuning.py`: Movement/physics tuning parameters (editable at runtime via the debug/admin menu).
- `src/ivan/physics/player_controller.py`: Kinematic character movement (step + slide) and jump/wall interactions.
- `src/ivan/ui/debug_ui.py`: Debug/admin UI widgets and HUD labels.

## Controls
- `WASD`: move (US layout). On RU layout you can use `ЦФЫВ`. Arrow keys also work.
- `C` (hold): crouch
- `Space`: jump
- `R`: reset to spawn
- `Esc`: in-game toggles pointer lock and opens the debug/admin menu plus a right-side system panel (Resume / Back to Menu / Quit); in the main menu it acts as back/quit
- `F2`: toggle input debug overlay (useful when keyboard/mouse don't seem to register)
- `F3`: toggle error console overlay (shows recent errors without crashing)
- `LMB`: mock grapple impulse (only if grapple toggle enabled)

## Main Menu
Booting without `--map` starts in the main menu:
- Run an existing bundle shipped under `apps/ivan/assets/` (imported/generated/hand-authored).
- Pick a GoldSrc/Xash3D game directory, select a mod, then select a `.bsp` to import and run.
- `Continue` runs the last launched map (persisted in a small local state file).

Navigation:
- Up/Down: move selection (hold accelerates)
- Left/Right: page jump by 10 items (hold `Shift` for 20)
- `Cmd+F` (macOS) / `Ctrl+F`: search (jumps selection to first match as you type)

Notes:
- Directory picking uses a native dialog via `tkinter` (stdlib). If Tk is unavailable, the menu will show an error.
- State file location defaults to `~/.irun/ivan/state.json` (override via `IRUN_IVAN_STATE_DIR`).

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
- Gravity, jump height, ground/air speed caps
- Ground acceleration, jump acceleration (bunnyhop/strafe), friction, air control
- Air counter-strafe brake strength
- Mouse sensitivity, crouch speed/height/camera
- Wall jump boost, vault jump/speed/ledge window, coyote time, jump buffer time

Boolean toggles are shown inline as labeled rows with `ON/OFF` buttons:
- Coyote time
- Jump buffer
- Wall jump
- Wallrun (toggle only, prototype hook)
- Vault (toggle only)
- Crouch
- Grapple (toggle + mock impulse)

Movement notes:
- Counter-strafe braking in air aggressively decelerates horizontal speed and does not accelerate in reverse while opposite input is held.
- Default `air_counter_strafe_brake` is set to `5.0`.
- Repeated wall-jumps from the same wall face are temporarily blocked.
- Wallrun is lateral; vertical climb gain is capped.
- If `vault_enabled` is on, pressing jump again near a ledge can trigger a vault: feet must be below ledge top, vault jump is higher than normal, and a small forward speed boost is applied.

## Level Layout
The map is generated in code and includes:
- Panda3D sample environment model (`models/environment`) as a base scene
- Long floor lane
- Basic jump obstacles
- Two wall sections for wall-jump experimentation
- Alternate elevated side route
- A simple reset/hard-fail condition if you fall off the course

## External Map Assets
IVAN can load an external map bundle via `--map <path-to-map.json>`.

You can also use a short alias under `apps/ivan/assets/`, for example:
```bash
python -m ivan --map imported/halflife/valve/bounce
```

### Source BSP -> Bundle (VTF -> PNG)
```bash
python3 tools/build_source_bsp_assets.py \
  --input <path-to-source.bsp> \
  --materials-root <path-to-materials/> \
  --materials-out <bundle-dir>/materials \
  --output <bundle-dir>/map.json \
  --scale 0.03
```

Run with the bundle:
```bash
python -m ivan --map <bundle-dir>/map.json
```

### GoldSrc/Xash3D BSP -> Bundle (WAD + resources)
Example (Counter-Strike 1.6 / Xash3D style mod folder):
```bash
python3 tools/importers/goldsrc/import_goldsrc_bsp.py \
  --bsp <path-to-goldsrc.bsp> \
  --game-root <path-to-mod-root> \
  --out <bundle-dir> \
  --scale 0.03
python -m ivan --map <bundle-dir>/map.json
```

Notes:
- By default, the importer extracts only textures referenced by the BSP into `<bundle-dir>/materials/` and does not
  copy other game assets. If you need extra assets copied, pass `--copy-resources`.
- The importer extracts embedded BSP textures when present (common for custom/community maps).
- If the BSP does not declare a worldspawn `wad` list, the importer falls back to scanning `--game-root` (and common
  subfolders like `wads/` and `maps/`) for `.wad` files and extracts only the textures the BSP actually uses.
- When copying resources, the importer intentionally skips executable code/binaries (e.g. `dlls/`, `cl_dlls/`, `bin/`,
  and extensions like `.dll`, `.exe`, `.dylib`, `.so`).
- Triangle-map collision response uses Bullet convex sweep tests and a Quake3-style kinematic controller
  (step + slide with plane clipping) for stable wall/ceiling/slope handling.
- The Source build step converts `materials/**/*.vtf` into PNG so Panda3D can load them.
- Map bundles include per-triangle materials, UVs, and optional vertex colors (used as baked lighting tint).
