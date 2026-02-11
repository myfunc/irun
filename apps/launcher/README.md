# IVAN Launcher Toolbox

A lightweight Dear PyGui desktop app for the runtime-first IVAN map workflow.
One window, map selection, launch, and pack.

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
- **TrenchBroom executable** — path to editor executable for opening selected maps.
- **WAD directory** — where `.wad` texture files live (default: `apps/ivan/assets/textures/`).
- **Steam/HL root** — optional Half-Life install root/runtime resource root.
- **Maps directory** — where `.map` source files are scanned (default: `apps/ivan/assets/maps/`).
- **Python executable** — interpreter used to launch IVAN and pack scripts.

Settings are saved to `~/.irun/launcher/config.json`.

### Map Browser
- Recursively scans the maps directory for `.map` files.
- Sorted by modification time (most recently edited first).
- Click a map to select it for all actions.
- Auto-refreshes every 5 seconds.

### Guided Runflow
Top section now uses a single runtime flow:
- **Map selection** from Map Browser.
- **Runtime-first launch** always targets the selected source `.map`.
- **Launch + Pack Options** (collapsed by default): optional overrides for watch/runtime-lighting.

Major controls include tooltips with expected behavior and command-line effect.

### Primary Actions
| Button | What it does |
|---|---|
| **Launch** | Launches selected source `.map` with runtime-first options |
| **Edit in TrenchBroom** | Opens selected `.map` in the editor |
| **Pack** | Runs `tools/pack_map.py` in `dev-fast` mode |
| **Stop Game** | Terminates the running IVAN game process |

Launch is disabled until a source `.map` is selected.

### Log Panel
- Captures stdout/stderr from all spawned subprocesses.
- Timestamped, scrollable, with a Clear button.

### Launch + Pack Options
- Collapsed by default to keep the first-run launch path clean.
- Controls launch overrides (`--watch`, `--runtime-lighting`).
- Pack always uses the runtime-first `dev-fast` profile.

## Dependencies

- `dearpygui` (GPU-accelerated immediate-mode GUI)
- Python 3.9+
- No Panda3D dependency — the launcher spawns IVAN as a subprocess.

## Typical Workflow

1. Open the launcher: `python -m launcher`
2. Confirm maps directory in Settings (first time only).
3. Select a `.map` file in the Map Browser.
4. Click **Edit in TrenchBroom** to continue editing in the external editor.
5. Click **Launch**.
6. Optionally tune Launch + Pack options (`watch`, `runtime-lighting`).
7. When ready to share, click **Pack**.

## Migration Notes
- Legacy launcher bake and baked run-mode paths were removed.
- Legacy create-map/import-WAD launcher flows were removed.
- Runtime-first launch now always uses the selected source `.map`.
