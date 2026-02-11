# IVAN Launcher Toolbox

A lightweight Dear PyGui desktop app for the pack-centric IVAN map workflow.
One window: pack discovery, build, validate, assign, launch.

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
- **Maps directory** — where `.map` source files and `.irunmap` packs are scanned.
- **Python executable** — interpreter used to launch IVAN and pack scripts.
- **Steam/HL root** — optional Half-Life install root/runtime resource root.
- **WAD dir (optional)** — where `.wad` texture files live (legacy; deprioritized).

Settings are saved to `~/.irun/launcher/config.json`.

### Pack Browser (primary)
- Recursively scans the maps directory for `.irunmap` pack files.
- Sorted by modification time (most recently built first).
- Click a pack to select it for Assign Pack.
- Auto-refreshes every 5 seconds.

### Map Browser
- Scans for `.map` source files.
- Select a map for Build Pack, Edit, or Launch.
- Auto-refreshes every 5 seconds.

### Primary Actions (pack-centric)
| Button | What it does |
|---|---|
| **Build Pack** | Build selected `.map` into sibling `.irunmap` (dev-fast) |
| **Validate Pack** | Run scope05 demo pipeline validation |
| **Assign Pack** | Use selected pack for launch instead of source `.map` |
| **Sync TB Profile** | Copy `GameConfig.cfg` and `ivan.fgd` to `%AppData%\TrenchBroom\games\IVAN\`; set materials root `textures_tb`, searchpath `.`; write Preferences `Games/IVAN/Path` to `apps/ivan/assets` |
| **Generate Textures** | Run `tools/sync_trenchbroom_profile.py` to regenerate TrenchBroom textures/manifest |
| **New Map (Template)** | Create a map from template (name pattern `mYYMMDD_HHMMSS`) under `assets/maps/` and open it in TrenchBroom |
| **Launch** | Launch selected map or assigned pack with runtime options |
| **Edit in TrenchBroom** | Open selected `.map` in the editor |
| **Stop Game** | Terminate the running IVAN game process |

Launch uses the assigned pack when one is set; otherwise it uses the selected source `.map`.

### Log Panel
- Captures stdout/stderr from all spawned subprocesses.
- Timestamped, scrollable, with a Clear button.

### Launch + Pack Options
- Collapsed by default.
- Controls launch overrides (`--watch`, `--runtime-lighting`).
- Pack always uses the runtime-first `dev-fast` profile.

## Dependencies

- `dearpygui` (GPU-accelerated immediate-mode GUI)
- Python 3.9+
- No Panda3D dependency — the launcher spawns IVAN as a subprocess.

## Typical Workflow

1. Open the launcher: `python -m launcher`
2. Confirm maps directory in Settings (first time only).
3. **Discover Packs** to see existing `.irunmap` files.
4. Select a `.map` in Map Browser.
5. **Build Pack** to create sibling `.irunmap`.
6. Select the pack in Pack Browser, click **Assign Pack** to use it for launch.
7. Click **Launch** (uses pack if assigned, else source `.map`).
8. **Generate Textures** to refresh editor textures from current assets.
9. **Sync TB Profile** when setting up TrenchBroom for the first time.
10. **New Map (Template)** to bootstrap a fresh map in the correct project folder.

## Migration Notes

- Launcher is now pack-centric; primary actions are discover, build, validate, assign, sync.
- WAD directory is optional and deprioritized in Settings.
- Launch supports assigned pack: select map + pack, Assign Pack, then Launch.
- Legacy bake and create-map/import-WAD flows were removed previously.

**TrenchBroom troubleshooting:** If TrenchBroom logs or uses `defaults/assets` as the game path, run **Sync TB Profile** — the `Games/IVAN/Path` preference was missing or stale.
