# IVAN Launcher Toolbox

A lightweight Dear PyGui desktop app that acts as a command center for the IVAN
map-editing workflow. One window, a few panels, persistent settings — replace
memorizing CLI commands with clicking buttons.

## How to Run

Use the shared Ivan venv (recommended):

```bash
# From repo root:
apps/ivan/.venv/Scripts/python -m pip install -e apps/launcher
apps/ivan/.venv/Scripts/python -m launcher
```

Or create a dedicated venv:

```bash
cd apps/launcher
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e .
python -m launcher
```

## What It Does

### Settings Panel (collapsible)
Configure and persist paths used by the launcher:
- **TrenchBroom executable** — needed to open maps in the editor.
- **WAD directory** — where `.wad` texture files live (default: `apps/ivan/assets/textures/`).
- **Materials directory** — where `.material.json` PBR definitions live (default: `apps/ivan/assets/materials/`).
- **Steam/HL root** — optional Half-Life install root for resource imports.
- **ericw-tools directory** — optional, needed only for the bake workflow (`qbsp`, `vis`, `light`).
- **Maps directory** — where `.map` source files are scanned (default: `apps/ivan/assets/maps/`).

Settings are saved to `~/.irun/launcher/config.json`.

### Map Browser
- Recursively scans the maps directory for `.map` files.
- Sorted by modification time (most recently edited first).
- Click a map to select it for all actions.
- Auto-refreshes every 5 seconds.

### Action Buttons
| Button | What it does |
|---|---|
| **Play Map** | Launches `python -m ivan --map <selected> [--map-profile ...] [--watch]` based on Pipeline Controls |
| **Stop Game** | Terminates the running IVAN game process |
| **Edit in TrenchBroom** | Opens the selected `.map` file in TrenchBroom |
| **Pack .irunmap** | Runs `tools/pack_map.py --profile <selected>` from Pipeline Controls |
| **Bake Lightmaps (legacy)** | Optional CLI bake path via `tools/bake_map.py` with selected profile/overrides |

Buttons that require unconfigured paths (TrenchBroom exe, ericw-tools) are
grayed out until the paths are set in Settings.

### Log Panel
- Captures stdout/stderr from all spawned subprocesses.
- Timestamped, scrollable, with a Clear button.

### Pipeline Controls
- Choose per-action profile: `dev-fast` or `prod-baked`.
- Control Play behavior (`--map-profile`, `--watch`) without editing CLI.
- Control Bake overrides (`--no-vis`, `--no-light`, `--light-extra`, `--bounce`) directly in UI.
- For full lightmap bake, set `Bake profile = prod-baked`, keep `--no-light` unchecked, and configure **ericw-tools dir** in Settings.

## Dependencies

- `dearpygui` (GPU-accelerated immediate-mode GUI)
- Python 3.9+
- No Panda3D dependency — the launcher spawns IVAN as a subprocess.

## Typical Workflow

1. Open the launcher: `python -m launcher`
2. Set TrenchBroom path in Settings (first time only).
3. Select a `.map` file in the Map Browser.
4. Click **Edit in TrenchBroom** to open it.
5. Click **Play Map** to launch the game with auto-reload.
6. Edit in TrenchBroom, save — the game reloads automatically.
7. When ready to share, click **Pack .irunmap**.

Notes:
- Preferred workflow for GoldSrc-style lighting is to compile/bake in the editor toolchain, then package via launcher.
- Launcher bake remains available for advanced/legacy CLI-driven workflows.
