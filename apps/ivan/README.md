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
- The menu includes `Quick Start: Metropolis` if either:
  - `assets/imported/source/community/ttt_metropolis/map.json` (directory bundle), or
  - `assets/imported/source/community/ttt_metropolis.irunmap` (packed bundle)
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
- `src/ivan/game/`: App wiring, input, camera, and update loop (split into focused modules).
  - `src/ivan/game/app.py`: composition root (`RunnerDemo`) + frame loop orchestration
  - `src/ivan/game/menu_flow.py`: main menu controller + import worker glue
  - `src/ivan/game/input_system.py`: mouse/keyboard sampling + input command helpers
  - `src/ivan/game/tuning_profiles.py`: tuning profile defaults + persistence helpers
  - `src/ivan/game/netcode.py`: client prediction/reconciliation + remote interpolation helpers
  - `src/ivan/game/grapple_rope.py`: grapple rope rendering helper
- `src/ivan/world/scene.py`: Scene building and external map loading (`--map` bundles).
- `src/ivan/physics/tuning.py`: Movement/physics tuning parameters (editable at runtime via the debug/admin menu).
- `src/ivan/physics/player_controller.py`: Kinematic character movement (step + slide) and jump/wall interactions.
- `src/ivan/ui/debug_ui.py`: Debug/admin UI widgets and HUD labels.

## Controls
- `WASD`: move (US layout). On RU layout you can use `ЦФЫВ`. Arrow keys also work.
- `Shift` (hold): slide (low-profile hull; release to exit)
- `Space`: jump
- `R`: reset to spawn
- `Esc`: opens the in-game menu (Resume / Map Selector / Key Bindings / Back to Main Menu / Quit); in the main menu it acts as back/quit
- `Esc -> Replays`: open replay browser and load an input-demo file
  - while replay playback is active, input is locked; press `R` to exit replay and respawn
  - replay playback shows an input HUD (movement/jump/slide/mouse directions)
- `` ` `` (tilde/backtick): opens the debug/admin tuning menu
- `F`: save current demo recording (recording window starts on respawn and ends when saved)
- `F4`: toggle the in-game console
- `Shift+F4`: restart run (time trial mode)
- `F5`: set Start marker at current position (time trial mode dev helper)
- `F6`: set Finish marker at current position (time trial mode dev helper)
- `F7`: clear local course markers (time trial mode dev helper)
- `F8`: export course to run.json (time trial mode dev helper)
- `F9`: export spawn to run.json (time trial mode dev helper)
- `F2`: toggle input debug overlay (useful when keyboard/mouse don't seem to register)
- `F3`: toggle error console overlay (shows recent errors without crashing)
- `LMB`: grapple hook primary
  - click (not attached): fire grapple to aimed surface
  - click (attached): detach
- In multiplayer, grapple hit on another player deals `20` damage.
- `V` (default): toggle noclip (rebindable from `Esc -> Key Bindings`)

Menu/input behavior:
- When `Esc` menu or debug menu is open, gameplay input (mouse look / movement keys) is ignored.
- The world simulation continues running (no hard pause), so physics/time still progress.
- Core movement simulation uses a fixed `60 Hz` tick for deterministic input replay.

Multiplayer launch:
- Dedicated server:
```bash
python -m ivan --server --host 0.0.0.0 --port 7777 --map <bundle-or-map-json>
```
- Client connect:
```bash
python -m ivan --connect <server-host> --port 7777 --name <player-name>
```
- Default multiplayer port is read from env var `DEFAULT_HOST_PORT` (fallback: `7777`).
- In normal client play (no `--connect`), the game is local/offline by default.
- `Esc` menu includes `Open To Network` checkbox:
  - OFF: no local host server is running
  - ON: starts embedded host server bound to `0.0.0.0` so other clients can join by your machine IP

MCP console control:
- IVAN starts a localhost console control bridge (JSON-lines TCP) on port `7779` by default.
  - Override port via env var `IRUN_IVAN_CONSOLE_PORT`.
- Run the MCP stdio server (for an MCP-capable client) with:
```bash
ivan-mcp --control-host 127.0.0.1 --control-port 7779
```

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
- Debug-tuned values are persisted per tuning profile in state; switching profiles restores that profile's slider/toggle values.

## HUD
- A small top-right speed chip is visible during gameplay (`SPEED <int>`).
- The value is horizontal speed, rounded down to an integer.
- A classic Half-Life/CS-style center crosshair is shown during active gameplay (hidden in pause/debug/menu).
- Detailed movement status (`speed/z-vel/grounded/wall`) is shown in the bottom-left corner during gameplay and hidden while the debug/admin panel is open.
- A health bar/chip is shown in the top-left corner (`HP`).
- Input debug (F2) and the error console (F3) are shown as boxed overlays that avoid overlapping the HUD bars.

## Demos (Input Replay)
- Ivan records input demos automatically from each spawn/respawn window.
- A demo stores per-tick input commands (look deltas, movement axes, action presses) and replay telemetry
  snapshots (position/velocity/speeds/camera angles/state/buttons) for feel tuning/diagnostics.
- Press `F` to save the current demo to `apps/ivan/replays/` in this repository.
- Replays can be loaded in-game from `Esc -> Replays`.
- Replay playback re-simulates movement through the normal engine/controller path at fixed `60 Hz`.

## Debug/Admin Menu
Panel layout:
- CS1.6-inspired boxed panel style with grouped collapsible sections (spoilers).
- Scrollable settings canvas for large parameter sets.
- Mouse wheel scroll is supported for the settings canvas and profile dropdown lists.
- Hovering a setting name/control shows a tooltip with a short explanation.
- Numeric sliders are normalized (`0..100`) while still mapping to each field's real min/max range.
- Slider tracks are intentionally large for quick tuning while moving.
- Top-right profile manager includes default presets (`surf_bhop_c2`, `surf_bhop`, `bhop`, `surf`, `surf_sky2_server`) and a `save` action.
  - Selecting a profile immediately applies that profile snapshot to all movement settings and updates menu controls.
  - Saving a modified default profile creates a short `*_copy` custom profile.
  - Saving a custom profile updates only that active profile in place.

Numeric settings include normalized sliders + entry fields for precise tuning:
- `max_ground_speed` (Vmax)
- `run_t90`
- `ground_stop_t90`
- `air_speed_mult`
- `air_gain_t90`
- `wallrun_sink_t90`
- `jump_height`
- `jump_apex_time`
- `jump_buffer_time`
- `coyote_time`
- `slide_stop_t90`

Boolean toggles are shown inline as labeled rows with `ON/OFF` buttons:
- Autojump (hold jump to keep hopping)
- Coyote/buffer enable
- Custom friction enable
- Slide enable
- Wallrun enable
- Surf enable
- Harness camera smoothing enable
- Harness animation/root-motion enable

Movement notes:
- Air speed and bunnyhop gain are controlled by two invariants:
  - `air_speed_mult` (`air_speed = max_ground_speed * air_speed_mult`)
  - `air_gain_t90` (`air_accel = 0.9 / air_gain_t90`)
- Slide feel is controlled by one independent invariant:
  - `slide_stop_t90` (how slowly slide preserves carried ground speed while held)
- Slide behavior:
  - `Shift` is hold-based: press/hold to stay in slide, release to exit slide immediately.
  - Slide does not apply an entry speed boost; it preserves existing horizontal speed and decays it using `slide_stop_t90`.
  - Keyboard strafe input is ignored while sliding; heading is controlled by camera yaw (mouse look).
  - Jump can be triggered while sliding and exits slide on takeoff.
- Repeated wall-jumps are controlled by `wall_jump_cooldown` (default: `1.0s`).
- Wall-jump is airborne-only: it cannot trigger while grounded, even if the player is touching a wall.
- Autojump only queues while grounded; holding jump in fully airborne states will not trigger wall-jump retries.
- Grapple hook can attach to any hit surface under crosshair and keeps rope length constraints for pendulum-style swinging.
- Clicking LMB while already attached detaches the grapple.
- On grapple attach, a one-shot boost is applied toward the rope direction (`grapple_attach_boost`).
- After attach, rope also auto-shortens for a short configurable window (`grapple_attach_shorten_speed`, `grapple_attach_shorten_time`) for a seamless pull-in feel.
- Wallrun camera tilts away from the active wall side.
- Wallrun vertical sink is timing-driven (`wallrun_sink_t90`) instead of direct velocity clamps.
- `vault_enabled` is OFF by default. If enabled, pressing jump again near a ledge can trigger a vault: feet must be below ledge top, vault jump is higher than normal, and a small forward speed boost is applied.
- Step risers are filtered out for wall-contact detection to reduce jitter and accidental wall-state hits on stairs/steps.
- Surf prototype uses GoldSrc-like air movement on steep ramps: wish direction is projected to ramp plane, then normal air acceleration + collision clipping drive surf movement.
- On surf ramps, acceleration follows the ramp-plane wish direction (not world-up injection), allowing controlled horizontal-to-vertical momentum transfer.

Lighting notes:
- GoldSrc/Quake-style animated lightstyles are applied at `~10Hz` (server-like), not every render frame.
- For performance on large maps, only surfaces that reference an actually-animated style pattern participate in lightstyle updates.
- If a bundle references lightmap files that are missing on disk, affected faces fall back to base-texture rendering instead of turning fully black.
- While surfing, horizontal momentum is redirected toward the ramp tangent each frame, enabling natural horizontal<->vertical speed exchange (inertia transfer) on slopes.
- Surf steering against current momentum preserves carry: it redirects momentum along the ramp and limits per-tick scrub so speed is not hard-stopped.
- Surf input acceleration contributes vertical velocity only for uphill redirection; downhill acceleration uses normal gravity.
- Once surf contact is lost, no additional surf accel/gravity modifiers are applied; existing velocity is preserved and normal air/gravity rules continue.
- `surf_sky2_server` approximates publicly listed legacy surf server movement cvars used on surf_ski_2/surf_sky_2 variants (`sv_accelerate 5`, `sv_airaccelerate 100`, `sv_friction 4`, `sv_maxspeed 900`, `sv_gravity 800`).

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

### Source VMF -> BSP -> Bundle
Use this when you have Source `.vmf` sources and want one-step import into IVAN.

```bash
python3 tools/importers/source/import_source_vmf.py \
  --vmf <path-to-map.vmf> \
  --out <bundle-dir-or-map.json-or.irunmap> \
  --materials-root <path-to-materials/> \
  --game-root <optional-source-game-root> \
  --scale 0.03
```

Notes:
- Requires Source compilers (`vbsp`, `vvis`, `vrad`) available in `PATH` or via `--compile-bin` / `--vbsp` / `--vvis` / `--vrad`.
- If `--game-root` is set, compile can resolve stock assets from that Source install while keeping map-local assets from the VMF folder.
- The tool compiles in an isolated temporary game root and does not modify your game installation.

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

### TrenchBroom `.map` -> GoldSrc BSP -> Bundle
Use this when you author geometry in TrenchBroom (Half-Life / Valve220 map format) and want one command to compile
and import into IVAN.

```bash
python3 tools/importers/goldsrc/import_trenchbroom_map.py \
  --map <path-to-trenchbroom.map> \
  --game-root <path-to-mod-root> \
  --out <bundle>.irunmap \
  --compile-bin <path-to-hlcsg-hlbsp-hlvis-hlrad> \
  --scale 0.03
python -m ivan --map <bundle>.irunmap
```

Notes:
- In TrenchBroom, select `Half-Life (experimental)` and `Valve 220` map format for best compatibility with the GoldSrc compiler chain.
- Requires GoldSrc compile tools (`hlcsg`, `hlbsp`, `hlvis`, `hlrad`) available in `PATH` or via `--compile-bin` / explicit `--hl*` args.
- The importer auto-detects SDHLT-style tool names (`sdHLCSG`, `sdHLBSP`, `sdHLVIS`, `sdHLRAD`) and omits `-game` for those binaries.
- The script runs compile stages, finds the produced BSP, then forwards it to `import_goldsrc_bsp.py`.
- Use `--skip-hlvis` and/or `--skip-hlrad` for fast graybox iteration.
- Use `--hlcsg-args`, `--hlbsp-args`, `--hlvis-args`, `--hlrad-args` to pass extra compiler flags (string values are shell-split).

### Per-Map Run Options (run.json)
If a bundle directory contains `run.json`, IVAN will use it to control defaults for that map (mode/spawn/lighting).

Lighting example:
```json
{
  "lighting": { "preset": "server_defaults" }
}
```
