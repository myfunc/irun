---
name: irun-map-conversion
description: Convert Source/GoldSrc BSP maps into IVAN runtime map bundles. Use when adding a new BSP map, re-building generated geometry/collision, extracting/packing textures, wiring skybox, or debugging why a map renders untextured.
---

# IRUN Map Conversion (IVAN)

This skill is intended for an agent/operator workflow: given a BSP + the game assets it depends on (WADs, sounds, models, sprites), produce an IVAN **map bundle** under `apps/ivan/assets/` and run it by a short alias.

## What Exists Today

IVAN loads a **map bundle** described by a single `map.json` file, plus assets next to it.

Runtime loader:
- `apps/ivan/src/ivan/__main__.py` accepts `--map <path>`
- `apps/ivan/src/ivan/world/scene.py` loads `map.json` + resolves textures from `materials.converted_root`.
- Supported bundle formats:
  - `format_version=1`: positions only (fallback debug checker texture)
  - `format_version=2`: per-triangle material + UV + vertex color + (optional) skybox

Coordinate conventions:
- Positions are converted as:
  - `x = x * scale`
  - `y = y * scale`
  - `z = z * scale`
- Triangles are emitted with a winding order that matches Panda3D's default backface culling.
- Normals are not axis-flipped (no scaling).

## Build Workflow

1. Enter IVAN venv:
```bash
cd apps/ivan
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

1. Recommended bundle locations (keeps `--map` aliases short):
- Output bundles: `apps/ivan/assets/imported/<vendor>/<mod>/<map_id>/`
- If you need to drop inputs later for an agent to import: `apps/ivan/assets/incoming/<vendor>/<mod>/`
  - For GoldSrc, treat `<mod>` like a mod folder (e.g. `valve`, `cstrike`):
    - `apps/ivan/assets/incoming/halflife/valve/maps/<map>.bsp`
    - `apps/ivan/assets/incoming/halflife/valve/wads/<wad>.wad` (or directly under the mod root)
    - optional: `sound/`, `models/`, `sprites/`, `gfx/` (resources for `--copy-resources`)

1. Build/refresh a **Source** bundle (VTF -> PNG):
```bash
cd apps/ivan
source .venv/bin/activate
python3 tools/build_source_bsp_assets.py \
  --input <path-to-source.bsp> \
  --materials-root <path-to-materials/> \
  --materials-out <bundle-dir>/materials \
  --output <bundle-dir>/map.json \
  --scale 0.03
```

1. Import a **GoldSrc/Xash3D** bundle (WAD textures; optional resource copy):
```bash
cd apps/ivan
source .venv/bin/activate
python3 tools/importers/goldsrc/import_goldsrc_bsp.py \
  --bsp <path-to-goldsrc.bsp> \
  --game-root <path-to-mod-root> \
  --out <bundle-dir> \
  --scale 0.03
```

1. Import a **TrenchBroom** `.map` (Valve220) by compiling to GoldSrc BSP first:
```bash
cd apps/ivan
source .venv/bin/activate
python3 tools/importers/goldsrc/import_trenchbroom_map.py \
  --map <path-to-trenchbroom.map> \
  --game-root <path-to-mod-root> \
  --out <bundle-dir-or-map.json-or.irunmap> \
  --compile-bin <path-to-hlcsg-hlbsp-hlvis-hlrad> \
  --scale 0.03
```

GoldSrc analyze-only (prints WAD list + detected resource refs, no output written):
```bash
python3 tools/importers/goldsrc/import_goldsrc_bsp.py \
  --bsp <path-to-goldsrc.bsp> \
  --game-root <path-to-mod-root> \
  --analyze
```

GoldSrc “drop-in incoming folder” example:
```bash
cd apps/ivan
source .venv/bin/activate
python3 tools/importers/goldsrc/import_goldsrc_bsp.py \
  --bsp assets/incoming/halflife/valve/maps/crossfire.bsp \
  --game-root assets/incoming/halflife/valve \
  --out assets/imported/halflife/valve/crossfire \
  --map-id crossfire \
  --scale 0.03
python -m ivan --map imported/halflife/valve/crossfire
```

1. Run:
```bash
cd apps/ivan
source .venv/bin/activate
python -m ivan --map <bundle-dir>/map.json
```

You can also run via a short alias under `apps/ivan/assets/`:
```bash
python -m ivan --map imported/halflife/valve/crossfire
```

Half-Life map picker (imports GoldSrc maps on demand from a Steam install):
```bash
python -m ivan --hl-root "<Half-Life install root>" --hl-mod valve
```

## Output Format (Generated JSON)

`format_version=2` uses a compact per-triangle dict:
- `m`: material name (e.g. `cs_dust/-0cssandwall`)
- `p`: 9 floats (triangle positions; already scaled to runtime units)
- `n`: 9 floats (vertex normals)
- `uv`: 6 floats (base texture UV per vertex)
- `lm`: 6 floats (lightmap UV per vertex; currently unused by runtime)
- `c`: 12 floats (vertex color RGBA in 0..1, used as baked lighting tint)

Collision can be imported separately:
- `collision_triangles`: list of position-only triangles (each is 9 floats).
  - If present, runtime collision uses this list instead of deriving collision from render triangles.
  - This is used by the GoldSrc/Xash importer to exclude non-collidable brush entities (e.g. `trigger_*`).

## Material Mapping Rules

- The runtime resolves textures using `materials.converted_root`.
- Lookups are case-insensitive (casefold) and normalize path separators.
- Example:
  - material `cs_dust/-0cssandwall`
  - texture `<bundle-dir>/materials/cs_dust/-0csSandWall.png`

## Texture Conversion (VTF -> PNG)

Converter implementation:
- `apps/ivan/tools/vtf_decode.py` (supports VTF 7.2 and high-res formats DXT1/DXT5/RGBA8888)
- `apps/ivan/tools/build_source_bsp_assets.py` calls the decoder and writes PNGs under the selected bundle.

Troubleshooting:
- If conversion fails, check the VTF header fields (version/format/mip count).
- Some VTFs include extra metadata chunks; the decoder locates the mip chain from EOF instead of assuming a strict layout.

## Skybox

- `build_source_bsp_assets.py` extracts `worldspawn.skyname` into JSON (`skyname`).
- The runtime builds a 6-face skybox from:
  - `<materials-root>/skybox/<SkyName><face>.png` (after conversion to PNG)
- Face suffixes: `ft bk lf rt up dn`

## Extending to Another Map

1. Create a new bundle directory (recommended): `apps/ivan/assets/generated/maps/<map_id>/`
2. Use one of:
   - Source: `tools/build_source_bsp_assets.py`
   - GoldSrc/Xash: `tools/importers/goldsrc/import_goldsrc_bsp.py`
3. Run: `python -m ivan --map <bundle-dir>/map.json`

## Current Limitations (Important)

- VMT parsing is not implemented (only the base texture name is used via BSP material name mapping).
- Lightmaps are not rendered yet. The runtime uses per-vertex color as a baked lighting tint.
- No props, decals, or dynamic entities are imported (only the BSP face meshes).
- GoldSrc sound/models are not used by runtime yet. The importer can optionally copy them into the bundle via `--copy-resources`.
  - When copying resources, the importer intentionally skips executable code/binaries:
    - directories: `dlls/`, `cl_dlls/`, `bin/`, `plugins/`
    - extensions: `.dll`, `.exe`, `.dylib`, `.so`, etc

## Collision/Rendering Import Policy (GoldSrc)

The GoldSrc importer builds two triangle streams:
- `triangles`: render geometry (skips common non-render textures like `trigger`, `skip`, `clip`, `nodraw`, etc).
- `collision_triangles`: collision-only geometry with entity-aware filtering.

Default collision filtering:
- Worldspawn model (`*0`): renders + collides.
- `trigger_*`: does not render and does not collide.
- `func_illusionary`: renders, does not collide.
- Common solid brush entities collide (doors, plats, trains, breakables, etc).
- Conservative default for unknown brush entities: render but do not collide (avoids importing invisible blockers).

## Troubleshooting

- “Map loads but input feels dead”: toggle the input overlay (`F2`) and confirm key/mouse state.
- “Spawn instantly resets”: check `bounds.min.z` and `kill_z` in the loaded `map.json` (respawn plane is derived from map bounds).
