# TrenchBroom Direct Map Pipeline

Date: 2026-02-09

## Context

We revisited how maps work in IVAN with the goal of making TrenchBroom the primary level editor and achieving the fastest possible edit-to-test loop. Previously the only path from TrenchBroom to the game was: TrenchBroom -> .map -> external BSP compiler (qbsp/vis/light) -> .bsp -> GoldSrc importer -> map.json bundle -> game. This required external tools and multiple manual steps.

## Decisions Made

### Format: Valve 220
- Valve 220 is the map format (not Standard Quake).
- Reasons: default Half-Life format in TrenchBroom, explicit UV axis vectors give full texture alignment control, WAD texture workflow already supported.
- Standard Quake format derives UVs from plane normals which breaks on angled faces.

### Architecture: Two Paths, One Runtime
- **Primary (own maps):** `.map` file loaded directly at runtime — parsed and converted in-memory, no intermediate files, no BSP compilation.
- **Legacy (HL/CS imports):** `.bsp -> .irunmap` bundle via existing importers — unchanged.
- Both paths feed the same internal triangle format that scene.py renders.

### Textures: WAD Only
- WAD files are the single texture source for all map workflows.
- TrenchBroom only sees albedo from WAD.
- No loose PNG textures in the editor — WAD is the standard.
- Existing goldsrc_wad.py is reused for WAD3 parsing.

### Materials: .material.json Files
- PBR properties (normal maps, roughness, metallic, emission) are defined via `.material.json` files alongside WAD textures.
- Naming convention was considered but rejected in favor of explicit definition files for more control.
- Lookup: engine resolves `<texture_name>.material.json` in the materials directory. If not found, plain albedo from WAD.
- All fields optional. Format:
  ```json
  {
    "normal": "brick_normal.png",
    "roughness": "brick_rough.png",
    "metallic": "brick_metal.png",
    "emission": "brick_emit.png",
    "alpha_mode": "opaque",
    "roughness_value": 0.8,
    "metallic_value": 0.0
  }
  ```
- First iteration: normal maps plumbed through to renderer. Full PBR shader (roughness/metallic) tracked separately.

### Smooth Normals: _phong Support
- TrenchBroom does NOT support curved surfaces (no patches/bezier).
- Smooth-looking geometry achieved via Phong normal averaging on brush vertices.
- Convention from ericw-tools: `_phong "1"` and `_phong_angle "89"` as entity key-value properties.
- Our brush-to-mesh converter computes smoothed normals when these properties are present.
- Defined in ivan.fgd so mappers see them in TrenchBroom.

### Lighting: Hybrid Approach
- **Dev mode (default):** flat ambient + directional sun. No lightmaps. Instant iteration.
- **Bake mode (optional):** ericw-tools pipeline (.map -> qbsp -> vis -> light -> .bsp -> existing GoldSrc importer -> .irunmap with lightmaps).
- ericw-tools are free, cross-platform, and compile small maps in 2-5 seconds.
- Bake supports: bounce lighting (radiosity), ambient occlusion, soft shadows, phong shading, colored lighting.
- No lightmap baking directly from .map — ericw-tools require BSP. This is acceptable because baking is optional and only for production quality.
- Own lightmap baker (Python/Embree) considered for the future but not planned now.

### BSP Direct Loading: Rejected
- Considered loading BSP files directly at runtime (skipping map.json conversion).
- Rejected: BSP format is complex, engine-specific, and we already have a working import pipeline.
- map.json bundles remain the intermediate/distribution format for imported BSP maps.

## What Was Built

### New Modules (apps/ivan/src/ivan/maps/)
- `map_parser.py` — Valve 220 .map text parser. Handles entities, brushes, faces. Falls back to Standard format gracefully.
- `brush_geometry.py` — CSG brush-to-mesh: half-plane intersection via Sutherland-Hodgman clipping, fan triangulation, Valve 220 UV projection, Phong smooth normals. Pure Python, no deps.
- `map_converter.py` — Orchestrator: parses .map, extracts worldspawn metadata (wad paths, skyname, phong), resolves WADs, extracts textures to PNG, converts brushes per entity type (func_wall/func_illusionary/trigger), finds spawn, computes bounds, resolves material defs. Outputs format-v2 triangle dicts for scene.py.
- `material_defs.py` — MaterialResolver class: scans directories for .material.json, case-insensitive lookup, caches results, graceful fallback.

### TrenchBroom Config (apps/ivan/trenchbroom/)
- `GameConfig.cfg` — Version 8 game definition. Valve 220 format only, WAD textures, editor tags for transparent tool textures (trigger/clip/skip/null/hint/origin/nodraw).
- `ivan.fgd` — Entity definitions: worldspawn, info_player_start, info_player_deathmatch, trigger_start/finish/checkpoint/teleport, func_wall/detail/illusionary, light/light_environment, info_teleport_destination. Base classes for _phong and targetname inheritance.
- `README.md` — Full quickstart guide.

### Tools (apps/ivan/tools/)
- `testmap.py` — Quick-test script. Launches game, watches .map for changes (mtime polling), auto-restarts on save. Console bridge reload attempted first, kill+restart as fallback.
- `bake_map.py` — ericw-tools bake pipeline. Runs qbsp/vis/light, imports resulting BSP via existing GoldSrc importer.
- `pack_map.py` — Direct .map to .irunmap packer (no BSP, no lightmaps).

### Launcher Toolbox (apps/launcher/)
- Standalone Dear PyGui desktop app (`python -m launcher`).
- **Settings panel**: TrenchBroom exe, WAD dir, materials dir, Steam/HL root, ericw-tools, maps dir, Python exe — all persisted to `~/.irun/launcher/config.json`.
- **Map browser**: recursive `.map` scan under maps dir, sorted by mtime, auto-refresh every 5s.
- **Actions**: Play Map (`--watch`), Stop Game, Edit in TrenchBroom, Create Map, Import WAD, Pack .irunmap, Bake Lightmaps.
- **Import WAD**: scans Steam/HL root for `.wad` files, shows checklist dialog with already-imported detection, copies selected WADs to `assets/textures/`. Also supports manual file browse.
- **Create Map**: modal dialog for name input, generates minimal Valve 220 `.map` template with worldspawn + floor brush + info_player_start, auto-opens in TrenchBroom.
- **Log panel**: captures stdout/stderr from all spawned subprocesses, timestamped, scrollable.
- Input fields use table layout (label | stretching input | browse button) to resize with the window.
- Modules: `app.py` (DPG UI + event loop), `config.py` (persistence), `actions.py` (subprocess management), `map_browser.py` (file scanner).

### Runtime Integration (modified files)
- `bundle_io.py` — MapFileHandle dataclass for .map files. Auto-detection in resolve_bundle_handle_path.
- `catalog.py` — .map file discovery under assets/maps/.
- `scene.py` — _try_load_map_file() method. Unlit rendering path (uses scene ambient+sun lights, no lightmap shader).
- `__main__.py` — --watch flag, --map help text updated for .map files.
- `state.py` — .map suffix handling fix.

### Bug Fixes (This Session)
1. **brush_geometry.py: Inverted plane normals** — `_plane_from_points()` used cross product `(p1-p0) x (p2-p0)` which produced inward-facing normals. The Sutherland-Hodgman clipper keeps the back half-space, so inward normals caused every face to be clipped to zero vertices (0 triangles output). **Fix**: swapped to `(p2-p0) x (p1-p0)` to produce outward-facing normals. Confirmed: test map now produces 24 triangles correctly.

2. **brush_geometry.py: Clockwise polygon winding ("inside-out" textures)** — `_make_base_polygon()` produced vertices in clockwise (CW) order when viewed from the outward-facing normal direction. Panda3D / OpenGL treats counter-clockwise (CCW) as front-face. With `setTwoSided(False)` (backface culling enabled), CW polygons were culled from outside the brush but visible from inside — making all textures appear inside-out. The previous vertex order `(-U+V), (+U+V), (+U-V), (-U-V)` was CW regardless of which tangent frame the `up` vector selection produced. **Fix**: reversed to `(-U-V), (+U-V), (+U+V), (-U+V)` which is CCW from the front. Verified via signed-area test for both floor faces (normal ±Z) and wall faces (normal ±X/±Y).

3. **baker/app.py: Baker crashed when opening .map files** — `resolve_bundle_handle()` intentionally returns `None` for `.map` files (they produce a `MapFileHandle`, not a `BundleHandle`). The baker treated `None` as an error and called `SystemExit`. **Fix**: added fallback to `resolve_map_json()` — if the result is a `.map` file, pass its path directly to `scene_cfg.map_json`. Scene.py already handles `.map` files via `_try_load_map_file()`.

### Verification Fixes (Previous Session)
Five issues found and fixed during integration verification:
1. scene.py: WAD textures showed as checkers because material index guard was wrong when _material_texture_root was None.
2. bundle_io.py: MapFileHandle caused AttributeError in callers expecting BundleHandle fields.
3. pack_map.py: dict-access on Triangle dataclass (2 fixes).
4. state.py: .map suffix not excluded from path expansion (generated nonsense paths).

## Resource Structure

```
apps/ivan/assets/
├── textures/           WAD files (TrenchBroom reads these)
│   └── halflife.wad    (imported from Steam HL install via launcher)
├── materials/          PBR material definitions (engine reads these)
│   └── brick/
│       ├── brick.material.json
│       ├── brick_normal.png
│       └── brick_rough.png
├── maps/               .map source files
│   └── mymap/
│       ├── mymap.map
│       └── run.json    (optional game mode/spawn override)
└── imported/           BSP imports (unchanged)
```

## Dev Workflow (Final)

```
Launcher Toolbox (python -m launcher)
  │
  ├── [Import WAD]    scan HL install, copy .wad → assets/textures/
  ├── [Create Map]    scaffold .map file + open TrenchBroom
  │
  │   TrenchBroom  ──save──>  mymap.map
  │
  ├── [Play Map]      python -m ivan --map mymap.map --watch  (auto-reload)
  ├── [Edit in TB]    open selected map in TrenchBroom
  ├── [Pack .irunmap] tools/pack_map.py (distribution bundle)
  └── [Bake]          tools/bake_map.py (optional lightmaps via ericw-tools)
```

## Screenshots

Reference screenshots from this session are in `docs/brainstorm/tech/screenshots/`:
- `01-launcher-initial.png` — Launcher UI first version (fixed-width inputs)
- `02-trenchbroom-preferences.png` — TrenchBroom preferences showing HL game config
- `03-launcher-game-running.png` — Launcher + game running side by side
- `04-game-no-textures-closeup.png` — Map loaded in-game, textures not rendering (fixed)

## Fixed Bug: WAD Textures Not Loading + UV Scale + Orientation

**Status: FIXED**

### Symptoms (original)
1. WAD textures from `halflife.wad` not rendering — surfaces showed as debug checkerboard.
2. UV scale extremely large — texture pattern only visible when very close.
3. Textures appeared vertically flipped ("inside-out") compared to TrenchBroom.
4. Lighting appeared flat / not processing.

### Root causes found and fixed

**Bug A — Case-sensitive texture name mismatch:**
WAD files store texture names in lowercase (`lab1_floor4`), but `.map` files reference them in uppercase (`LAB1_FLOOR4`). GoldSrc is case-insensitive, but Python dict lookups are case-sensitive — all lookups missed.

**Bug B — Temporary directory deleted before render:**
`convert_map_file()` extracted WAD textures to a `TemporaryDirectory`. When the function returned, Python garbage-collected the temp dir, deleting all PNG files before the renderer could load them.

**Bug C — UV V-axis flip (GoldSrc vs Panda3D):**
GoldSrc texture V=0 is at the top (V increases downward). Panda3D V=0 is at the bottom (V increases upward). Without negating V, textures appear vertically flipped.

**Bug D — Vertex colors interfering with lighting:**
The unlit rendering path used a vertex format with `C_color` (all-white vertex colors). This can interfere with Panda3D's fixed-function lighting pipeline. Switching to `GeomVertexFormat.getV3n3t2()` (no vertex colors) allows the ambient + sun lights to work properly.

### All fixes applied (6 changes)
1. **`map_converter.py` / `_extract_wad_textures()`**: Normalised WAD texture name keys to lowercase.
2. **`brush_geometry.py` / `brush_to_triangles()`**: Used `face.texture.lower()` for `tex_sizes` lookup.
3. **`map_converter.py` / `convert_map_file()` step 10**: Used `mat_name.lower()` for `tex_materials` lookup.
4. **`scene.py` / `_try_load_map_file()`**: Passed persistent `texture_cache_dir` (`~/.irun/ivan/cache/map_textures/<map_stem>/`) instead of relying on `TemporaryDirectory`.
5. **`brush_geometry.py` / `_compute_uv()`**: Negated V coordinate to convert GoldSrc V-down to Panda3D V-up.
6. **`scene.py` / `_attach_triangle_map_geometry_v2_unlit()`**: Switched from `_vformat_v3n3c4t2t2()` to `GeomVertexFormat.getV3n3t2()` — no vertex colors, no second texcoord — so Panda3D's default lighting (ambient + sun) applies correctly.

## Open Items / Future Work

- **PBR shader:** Material definitions are parsed and stored, but the renderer currently only uses albedo. Normal map / roughness / metallic rendering needs a proper Panda3D shader.
- **map_reload console command:** testmap.py falls back to kill+restart because the in-game `map_reload` command doesn't exist yet. Adding it would enable hot-reload without restarting.
- **Map format v3:** Unpaused. Entities from .map files (triggers, lights, movers) can now be mapped to v3 entity system.
- **TrenchBroom Icon.png:** Not created yet (cosmetic, low priority).
