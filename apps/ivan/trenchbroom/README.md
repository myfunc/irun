# TrenchBroom + IVAN: Quickstart

## 1. Install TrenchBroom Game Config

Copy **all files** from this folder (`apps/ivan/trenchbroom/`) to TrenchBroom's games directory:

| OS | Path |
|---|---|
| **Windows** | `%AppData%\TrenchBroom\games\IVAN\` |
| **macOS** | `~/Library/Application Support/TrenchBroom/games/IVAN/` |
| **Linux** | `~/.TrenchBroom/games/IVAN/` |

Files to copy: `GameConfig.cfg`, `ivan.fgd`, `Icon.png` (if present).

## 2. Set Game Path in TrenchBroom

1. Launch TrenchBroom
2. Go to **File > Preferences > IVAN**
3. Set **Game Path** to the **absolute path** of `apps/ivan/assets/`
   - Example (Windows): `<your-repo-root>\apps\ivan\assets`

This tells TrenchBroom where to find WAD textures and other assets.

## 3. Get Textures (WAD File)

TrenchBroom needs a **WAD file** for textures. You have two options:

### Option A: Use existing Half-Life WADs (quick start)
If you have Half-Life installed, you can use its WAD files directly:
1. Copy `halflife.wad` (or `cs_dust.wad`, etc.) from your Half-Life install into `apps/ivan/assets/textures/`
2. In TrenchBroom, add the WAD via **Face Inspector > + button** or worldspawn `wad` property

### Option B: Create your own WAD (recommended for own maps)
Use a tool like **TexMex**, **Wally**, or **JACK WAD editor** to create a custom WAD:
1. Create `apps/ivan/assets/textures/ivan_base.wad`
2. Add your PNG textures to the WAD (GoldSrc format: 8-bit indexed, 16-pixel aligned dimensions)
3. In TrenchBroom, add the WAD to your map

### Option C: Work without textures (geometry only)
You can skip textures entirely for geometry testing. The game will show a debug checkerboard pattern on all surfaces.

## 4. Create a Map

1. In TrenchBroom: **File > New Map**
2. Select game **IVAN**, format **Valve**
3. Build your map using brushes
4. Add an `info_player_start` entity (this is where the player spawns)
5. Save as `.map` file — recommended location: `apps/ivan/assets/maps/mymap/mymap.map`

## 5. Test the Map

### Quick test (one command):
```bash
cd apps/ivan
python -m ivan --map path/to/mymap.map
```

### With auto-reload on save:
```bash
cd apps/ivan
python tools/testmap.py path/to/mymap.map
```
Save your map in TrenchBroom — the game auto-restarts and loads the new version.

### From repo root:
```bash
.\runapp ivan --map apps/ivan/assets/maps/mymap/mymap.map
```

## Resource Structure

```
apps/ivan/assets/
├── textures/               WAD files (TrenchBroom reads these)
│   ├── ivan_base.wad       Your project textures
│   └── halflife.wad        (optional) borrowed HL textures
│
├── materials/              PBR material definitions (engine reads these)
│   └── brick/
│       ├── brick.material.json   Defines PBR maps for "brick" texture
│       ├── brick_normal.png      Normal map
│       └── brick_rough.png       Roughness map
│
├── maps/                   Your .map source files
│   └── mymap/
│       ├── mymap.map       TrenchBroom source file
│       └── run.json        (optional) Game mode, spawn override
│
└── imported/               BSP imports (existing HL/CS maps)
    └── halflife/valve/...
```

### How textures flow:

```
                    TrenchBroom                          IVAN Engine
                    ──────────                           ───────────
WAD file ──────►  Shows albedo in editor    ──────►  Extracts albedo from WAD
                                                     Looks for .material.json
                                                     Loads normal/rough/metal maps
                                                     Renders with PBR (if available)
```

- **TrenchBroom** only sees the WAD albedo texture (editor preview)
- **IVAN engine** extracts the albedo from WAD, then checks `assets/materials/` for a `.material.json` that adds PBR maps
- If no `.material.json` exists — plain albedo rendering (fine for testing)

### How to add PBR to a texture:

Say your WAD has a texture called `brick`. Create `assets/materials/brick.material.json`:
```json
{
  "normal": "brick_normal.png",
  "roughness": "brick_rough.png"
}
```
Put `brick_normal.png` and `brick_rough.png` next to the JSON file. Done — the engine picks them up automatically.

## Available Entities

| Entity | Type | Purpose |
|---|---|---|
| `info_player_start` | Point | Player spawn position |
| `info_player_deathmatch` | Point | Alternative spawn |
| `trigger_start` | Brush | Course start zone |
| `trigger_finish` | Brush | Course finish zone |
| `trigger_checkpoint` | Brush | Course checkpoint |
| `func_wall` | Brush | Solid brush entity |
| `func_detail` | Brush | Detail geometry (no BSP split) |
| `func_illusionary` | Brush | Non-solid visible brush |
| `light` | Point | Point light (for bake) |
| `light_environment` | Point | Sun light (for bake) |

### Smooth surfaces (_phong):

On any brush entity (or worldspawn), set:
- `_phong` = `1` — enables smooth normals
- `_phong_angle` = `89` — angle threshold (default 89 degrees)

This makes curved brush geometry look smoother without adding more brushes.

## Files Reference

| File | Purpose |
|---|---|
| `GameConfig.cfg` | TrenchBroom game definition |
| `ivan.fgd` | Entity definitions |
| `Icon.png` | Game icon in TrenchBroom (if present) |
