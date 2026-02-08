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
- The menu includes `Quick Start: Bounce` if either:
  - `assets/imported/halflife/valve/bounce/map.json` (directory bundle), or
  - `assets/imported/halflife/valve/bounce.irunmap` (packed bundle)
  exists.
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
- `Esc`: opens the in-game menu (Resume / Map Selector / Key Bindings / Back to Main Menu / Quit); in the main menu it acts as back/quit
- `` ` `` (tilde/backtick): opens the debug/admin tuning menu
- `F4`: restart run (time trial mode)
- `F5`: set Start marker at current position (time trial mode dev helper)
- `F6`: set Finish marker at current position (time trial mode dev helper)
- `F7`: clear local course markers (time trial mode dev helper)
- `F8`: export course to run.json (time trial mode dev helper)
- `F9`: export spawn to run.json (time trial mode dev helper)
- `F2`: toggle input debug overlay (useful when keyboard/mouse don't seem to register)
- `F3`: toggle error console overlay (shows recent errors without crashing)
- `LMB`: mock grapple impulse (only if grapple toggle enabled)
- `V` (default): toggle noclip (rebindable from `Esc -> Key Bindings`)

Menu/input behavior:
- When `Esc` menu or debug menu is open, gameplay input (mouse look / movement keys) is ignored.
- The world simulation continues running (no hard pause), so physics/time still progress.

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
- Debug-tuned values are persisted in state and reused as startup defaults on the next launch.

## HUD
- A top-center speed readout is always visible (`Speed: <int> u/s`).
- The value is horizontal speed, rounded down to an integer.
- Detailed movement status (`speed/z-vel/grounded/wall`) is shown in the bottom-left corner during gameplay and hidden while the debug/admin panel is open.

## Debug/Admin Menu
Panel layout:
- CS1.6-inspired boxed panel style with grouped collapsible sections (spoilers).
- Scrollable settings canvas for large parameter sets.
- Mouse wheel scroll is supported for the settings canvas and profile dropdown lists.
- Hovering a setting name/control shows a tooltip with a short explanation.
- Numeric sliders are normalized (`0..100`) while still mapping to each field's real min/max range.
- Slider tracks are intentionally large for quick tuning while moving.
- Top-right profile manager includes default presets (`surf_bhop`, `bhop`, `surf`) and a `save` action.
  - Saving a modified default profile creates a short `*_copy` custom profile.
  - Saving a custom profile updates that profile in place.

Numeric settings include normalized sliders + entry fields for precise tuning:
- Gravity, jump height, ground/air speed caps
- Ground acceleration, jump acceleration (bunnyhop/strafe), friction, air control
- Air counter-strafe brake strength
- Mouse sensitivity, crouch speed/height/camera
- Wall jump boost + cooldown, vault jump/speed/ledge window, coyote time, jump buffer time
- Noclip fly speed
- Surf acceleration / gravity scale / surfable slope-normal range (inspired by public CS surf server settings)

Boolean toggles are shown inline as labeled rows with `ON/OFF` buttons:
- Coyote time
- Jump buffer
- Autojump (hold jump to keep hopping)
- Noclip
- Surf
- Wall jump
- Wallrun (toggle only, prototype hook)
- Vault (toggle only)
- Crouch
- Grapple (toggle + mock impulse)

Movement notes:
- Counter-strafe braking in air decelerates horizontal speed based on `air_counter_strafe_brake` without hidden hardcoded bonus deceleration.
- Default `air_counter_strafe_brake` is `23.0`.
- Repeated wall-jumps are controlled by `wall_jump_cooldown` (default: `1.0s`).
- Wallrun is lateral; vertical climb gain is capped.
- `vault_enabled` is OFF by default. If enabled, pressing jump again near a ledge can trigger a vault: feet must be below ledge top, vault jump is higher than normal, and a small forward speed boost is applied.
- Step risers are filtered out for wall-contact detection to reduce jitter and accidental wall-state hits on stairs/steps.
- Surf prototype uses GoldSrc-like air movement on steep ramps: wish direction is projected to ramp plane, then normal air acceleration + collision clipping drive surf movement.

## Level Layout
The map is generated in code and includes:
- Panda3D sample environment model (`models/environment`) as a base scene
- Long floor lane
- Basic jump obstacles
- Two wall sections for wall-jump experimentation
- Alternate elevated side route
- A simple reset/hard-fail condition if you fall off the course

## External Map Assets
IVAN can load an external map bundle via `--map <path-to-map.json>` or `--map <path-to-bundle.irunmap>`.

You can also use a short alias under `apps/ivan/assets/`, for example:
```bash
python -m ivan --map imported/halflife/valve/bounce
```

### Per-Bundle Run Metadata (Game Modes)
Bundles can optionally include run metadata to select a game mode and provide extra runtime data that does not belong in the
geometry manifest.

Storage:
- Directory bundle: `<bundle>/run.json` next to `map.json`
- Packed bundle (`.irunmap`): `<bundle>.run.json` sidecar next to the archive

Example:
```json
{
  "mode": "time_trial",
  "spawn": { "position": [0, 0, 3], "yaw": 90 },
  "config": {
    "start_aabb": { "min": [-2, -2, 0], "max": [2, 2, 4] },
    "finish_aabb": { "min": [98, -2, 0], "max": [102, 2, 4] }
  }
}
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

Notes:
- The tool extracts per-face Source lightmaps into the bundle and the runtime multiplies base texture by lightmap.
- The tool parses common VMT keys (e.g. `$basetexture`, `$translucent`, `$additive`, `$alphatest`, `$alpha`, `$nocull`)
  to drive runtime rendering (e.g. glass/decals).
 - You can store per-map lighting presets in `<bundle>/run.json` under `"lighting"` (see below).

Run with the bundle:
```bash
python -m ivan --map <bundle-dir>/map.json
```

Pack a directory bundle into a single file:
```bash
python3 tools/pack_irunmap.py --input <bundle-dir> --output <bundle>.irunmap
python -m ivan --map <bundle>.irunmap
```

### GoldSrc/Xash3D BSP -> Bundle (WAD + resources)
Example (Counter-Strike 1.6 / Xash3D style mod folder):
```bash
python3 tools/importers/goldsrc/import_goldsrc_bsp.py \
  --bsp <path-to-goldsrc.bsp> \
  --game-root <path-to-mod-root> \
  --out <bundle>.irunmap \
  --scale 0.03
python -m ivan --map <bundle>.irunmap
```

Notes:
- By default, the importer extracts only textures referenced by the BSP into `<bundle-dir>/materials/` and does not
  copy other game assets. If you need extra assets copied, pass `--copy-resources`.
- The importer extracts embedded BSP textures when present (common for custom/community maps).
- The importer extracts baked GoldSrc lightmaps into `<bundle-dir>/lightmaps/` and the runtime multiplies base texture
  by the combined lightmap styles for each face.
- If the BSP does not declare a worldspawn `wad` list, the importer falls back to scanning `--game-root` (and common
  subfolders like `wads/` and `maps/`) for `.wad` files and extracts only the textures the BSP actually uses.
- When copying resources, the importer intentionally skips executable code/binaries (e.g. `dlls/`, `cl_dlls/`, `bin/`,
  and extensions like `.dll`, `.exe`, `.dylib`, `.so`).
- Triangle-map collision response uses Bullet convex sweep tests and a Quake3-style kinematic controller
  (step + slide with plane clipping) for stable wall/ceiling/slope handling.
- The Source build step converts `materials/**/*.vtf` into PNG so Panda3D can load them.
- Map bundles include per-triangle materials, UVs, and optional vertex colors (used as a baked lighting tint/fallback).

### Per-Map Run Options (run.json)
If a bundle directory contains `run.json`, IVAN will use it to control defaults for that map (mode/spawn/lighting).

Lighting example:
```json
{
  "lighting": { "preset": "server_defaults" }
}
```
