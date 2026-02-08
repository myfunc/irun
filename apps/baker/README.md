# IRUN Baker (Map Viewer + Import + Bake Tool)

Status: planned (design + implementation checklist)

This app is a **companion tool** to `apps/ivan`:
- open and preview imported maps (GoldSrc / Source / future formats)
- manage imported bundles (catalog, metadata, presets)
- provide an interactive UI to **edit light rigs** and **rebake** lighting artifacts
- export optimized bundles for the runtime game (`apps/ivan`)

This is intentionally **not** a full level editor (at least initially).

## Goals
- WYSIWYG: what you see in Baker should match what Ivan renders for the same bundle.
- Fast iteration loop:
  - open map, fly around, inspect draw calls and lighting
  - edit lights and bake settings
  - rebake with progress + cancellation + caching
  - write results back into the bundle and reload instantly
- Cross-engine readiness:
  - visibility (PVS / portals / chunk-frustum) and lighting are separate subsystems
  - a map can choose a lighting mode (imported vs rebaked vs hybrid) without changing geometry import

## Non-Goals (For Now)
- Full geometry editing (brush/mesh editing).
- Shipping an external mod ecosystem.
- Multiplayer tooling.

## App UX (High-Level)
- **Viewport**: real-time renderer, first-person + fly camera.
- **Left panel**: map catalog (bundles), import actions, recent maps.
- **Right panel (Inspector)**:
  - map info, bounds, triangle counts, material stats
  - lighting modes + tonemapping selector
  - visibility/culling options + debug visualization
  - bake presets and current bake job status
- **Bottom bar**: progress, logs, warnings, and “open artifact” shortcuts.

### Camera + Navigation (Trackpad Friendly)
- Default: fly cam (WASD + mouse look / trackpad look).
- Hotkeys:
  - `F`: focus/teleport to selection / last bookmark
  - `1..9`: camera bookmarks (store pose + view mode)
  - `G`: toggle gravity/grounded preview (optional)
  - `V`: toggle visibility debugging overlays
  - `L`: toggle lighting-only / albedo-only / full render

## Rendering Architecture

### Shared Renderer vs Separate Engine
Default plan: **shared renderer code** with `apps/ivan` (same Panda3D shading path),
so that:
- tone mapping, gamma, texture filtering, lightmap decoding match
- any “looks wrong” issue can be reproduced and debugged in Baker

Implementation approach:
- extract renderer-oriented code into a shared package module under `apps/ivan/src/ivan/…`
  (Ivan already exports `ivan` as a package; Baker can depend on it).
- `apps/baker` becomes a thin UI shell + tooling around shared renderer + import/bake pipeline.

If we later need a different UI stack, we can still keep the shared “render core” as a library.

## Color Management (Linear vs Tonemapping)
Hard rule: all lighting math must be done in **linear** space.

We support **switchable** view transforms for preview (and for runtime):
- `None`: linear -> display (simple gamma encode only)
- `Reinhard`: classic photographic tonemap for bright scenes
- `ACES (approx)`: more cinematic roll-off

Notes:
- Base textures are typically authored for display (sRGB). For correct shading:
  - sample base textures as sRGB and convert to linear for shading, or pre-decode to linear.
- Lightmaps should be treated as **linear data**:
  - store bake outputs in linear and only apply tonemap/gamma at presentation time.
- Baker should let you toggle:
  - base filter: nearest vs linear (retro vs smooth)
  - lightmap filter: nearest vs linear (debugging blockiness vs smoothing)
  - gamma/exposure controls (preview only, not baked into data unless explicitly chosen)

## Bundle Outputs (What Baker Produces)
Baker should write artifacts into the existing bundle layout (directory bundle and `.irunmap`):

- `run.json` (per-bundle runtime metadata):
  - chosen lighting mode/preset
  - visibility/culling config

- `lighting/` (new, Baker-owned):
  - `lighting/bake.json`: bake config + selected preset + provenance info
  - `lighting/lights.json`: extracted + user-edited light rig overrides
  - `lighting/lightmaps/`:
    - atlases (preferred) and/or per-chunk lightmaps
    - metadata mapping surfaces/chunks to atlas rects
  - `lighting/probes/` (optional later): SH probes / irradiance volumes for dynamic objects

- `chunks/` (optional but recommended for performance):
  - chunk meshes (deterministic ids), AABBs, material batches

- `visibility/`:
  - cached PVS/portal data if derived (engine-specific), stored as a cache and not required for correctness

## Lighting Modes (Per Bundle, Selectable)
The runtime (Ivan) should support:
- `fullbright`: albedo only
- `imported_lightmaps`: render using imported engine lightmaps (GoldSrc/Source)
- `rebaked_lightmaps`: render using Baker-produced lightmaps
- `hybrid`: imported or rebaked lighting multiplied by additional AO (optional)

Important: lighting is a choice, not a requirement. Maps without any light artifacts still render.

## Bake Pipeline (Algorithm Plan)

### Stage 0: Import / Normalize Scene
- Import geometry + materials into an engine-agnostic intermediate:
  - triangles/indices per material
  - UV0 (albedo), UV1 (lightmap) if available, or generate UV1 for rebake
  - static collision meshes
  - entity graph (if present)
- Normalize:
  - coordinate system
  - texture lookup rules
  - material metadata (alpha test, additive, etc.)

### Stage 1: Light Discovery
Sources of lights (in priority order):
1. Map entities (engine-specific) mapped to a common light model.
2. Emissive materials heuristic (optional):
   - “light” textures, monitor screens, lamps
3. User-authored lights (overrides stored in `lighting/lights.json`).

User can edit per-light:
- type (point / spot / area surrogate)
- intensity, color temperature, radius
- shadow casting on/off
- grouping (for quick enable/disable)

### Stage 2: Bake Targets
We bake for **static geometry only**.
Targets:
- lightmaps (direct + ambient term)
- optional AO-only map (for hybrid mode)
- optional shadowmask-like channel (future)

Quality knobs (preset-driven):
- luxel density (world units per texel)
- rays per texel (direct shadows)
- AO samples per texel
- filtering/denoise level
- max distance / bias controls (light leaking)

### Stage 3: Bake Core (Initial Version)
Start simple (fast, predictable):
- direct lighting + hard shadows
- AO term
- optional “ambient floor” to prevent pitch-black rooms

Later upgrades:
- 1-bounce GI
- portal/room-aware sampling for interiors

### Stage 4: Packing + Export
- Pack per-surface or per-chunk lightmaps into a small number of atlas pages.
- Add padding + edge dilation to reduce bilinear bleeding.
- Write mapping metadata and lightmap textures into the bundle.

### Stage 5: Validation
Baker should provide:
- “before/after” view toggles (imported vs rebaked)
- saved camera bookmarks for regression checks
- stats panel:
  - draw calls, triangle count, visible chunk count
  - lightmap atlas count + total lightmap texels
  - bake time breakdown

## Visibility / “What Should Render” (Pluggable)
Baker should visualize and validate culling, but should not hard-couple it to lighting.

Order of implementation:
1. Frustum + chunk AABB culling (engine-agnostic, works everywhere).
2. Engine-specific:
   - GoldSrc leaf/PVS
   - Source cluster/PVS
3. Portals/areas (optional, future).

Baker UI should include:
- “show hidden geometry” override toggle
- PVS/leaf debug visualization (camera leaf id, visible leaf count)

## Implementation Steps (Concrete Next Actions)

### Phase 1: Skeleton + Viewer
1. Create `apps/baker` Python app scaffold (entrypoint + window + UI shell).
2. Reuse the current map bundle loader (`ivan.maps.bundle_io`) to open bundles.
3. Reuse renderer path from Ivan for:
   - materials + base texture rendering
   - current lightmap shader path
4. Add a stats overlay: FPS, draw calls, texture counts, visible chunks/faces.

### Phase 2: Color + Tonemapping Controls
1. Add view transform selector (None/Reinhard/ACES approx).
2. Add toggles:
   - albedo-only / lighting-only / combined
   - base filter and lightmap filter modes
3. Add exposure and gamma controls (preview-only).

### Phase 3: Light Rig Editor
1. Define canonical `LightRig` JSON schema in `lighting/lights.json`.
2. Implement UI:
   - list of lights + search
   - per-light inspector + gizmo-less numeric editing initially
3. Add “extract lights from map” (best-effort) into the rig, then allow overrides.

### Phase 4: Bake Prototype (Small Map)
1. Implement UV1 generation for rebake (if missing):
   - per-chunk charting or simple planar unwrap as a bootstrap.
2. Implement bake job runner:
   - multithreaded CPU sampling
   - progress reporting + cancellation
   - caching keyed by (geometry hash, light rig hash, settings hash)
3. Export:
   - atlas textures + metadata into `lighting/`.
4. Runtime integration:
   - add `run.json` knob to select `rebaked_lightmaps`.

### Phase 5: Importer V2 / Optimized Geometry
1. Move away from “huge triangles array in JSON”:
   - chunked binary meshes + small manifest
2. Deterministic chunking and material batching to reduce draw calls.
3. Visibility hooks:
   - connect engine PVS to chunk visibility where possible.

## Open Decisions (Make Early)
- Do we commit to Panda3D for Baker UI, or embed a minimal UI and keep the app “tool-like”?
- Lightmap storage format:
  - PNG is convenient but slow and ambiguous with gamma.
  - Consider a custom binary (or EXR) for bake intermediates, and convert to runtime-friendly textures at export.
- Atlas size defaults and padding/dilation strategy.
- Runtime shader pipeline:
  - keep GLSL 120 compatibility for macOS legacy contexts
  - or require newer GL (if we decide to move the floor up later)

