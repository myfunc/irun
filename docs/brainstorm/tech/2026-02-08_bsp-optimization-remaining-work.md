# BSP Optimization: Remaining Work (Lightmaps + Visibility)

Date: 2026-02-08

This note captures what is still missing after the initial BSP import + runtime lighting work.
It is meant as a handoff checklist for follow-up agents/PRs.

## Current State (Summary)
- GoldSrc importer extracts per-face lightmaps into `lightmaps/f<face>_lm<slot>.png`.
- Runtime renders BSP triangle bundles by grouping triangles into Geoms keyed by `(material, lmi)` where `lmi` is currently the face id.
- Result: too many Geoms / draw calls on typical maps.
- Visibility: no PVS/leaf culling is implemented (everything renders).

## Highest Impact Performance Work
### 1) GoldSrc Lightmap Atlasing (Importer + Runtime)
Problem:
- Per-face lightmap textures force draw calls to scale with face count.

Target behavior:
- Pack per-surface lightmap blocks into a small number of atlas pages (like GoldSrc does at load time).
- Runtime groups by `(material, atlas_id)` instead of `(material, face_id)`.

Importer work (GoldSrc):
- Build atlas pages (e.g. 512x512 or 1024x1024) and pack each face's `(w,h)` lightmap blocks into atlas pages.
- Output:
  - `lightmaps/atlas_<n>_style<slot>.png` (or 4 separate textures, one per style slot)
  - Per-face metadata in `map.json`:
    - `atlas_id` per style slot (or one atlas id shared across slots)
    - `rect` (x, y, w, h) for each packed block
    - styles array (already exists conceptually)
- Update triangle `lm` UVs to point into the atlas:
  - `atlas_u = (rect.x + u * rect.w) / atlas_w`
  - `atlas_v = (rect.y + v * rect.h) / atlas_h`

Runtime work:
- Change grouping key from `(material, lmi)` to `(material, atlas_id)` (plus any other required keys).
- Bind atlas textures instead of per-face textures.

Acceptance:
- Draw calls should scale with `(materials * atlas_pages * chunks)` rather than face count.

### 2) Chunking (Stable Batching, Future Streaming)
Problem:
- Even with atlasing, a single huge batch can become expensive for culling and future streaming.

Work:
- Split baked geometry into chunks (e.g. spatial partitions).
- Group/batch within each chunk by `(material, atlas_id)` and produce stable, deterministic output.

### 3) Visibility / Culling (PVS or Coarse First Pass)
Problem:
- Currently we render the whole map all the time.

Work options:
- Implement BSP leaf-based culling using PVS:
  - Determine current leaf from camera position.
  - Decode PVS bitset for that leaf.
  - Render only faces in visible leaves (requires face->leaf mapping).
- If PVS parsing is too heavy short-term:
  - Coarse grid-based chunk culling + frustum culling as an initial win.

## Lighting Fidelity Work (Correctness/Looks)
### 1) Shader/Runtime Diagnostics
- Detect GLSL compile/link failures and surface them in the error console.
- Add a debug overlay with:
  - draw call count (Geom count)
  - number of lightmap pages loaded
  - whether lightmap shader is active
  - current lightstyle frame/scales

### 2) Rendering Toggles (Per Run)
Add run.json toggles to isolate lighting issues:
- base-only
- lightmap-only
- fullbright

### 3) Gamma/Intensity Controls
Add per-bundle tuning (in `run.json`):
- `lighting.lightmap_gamma`
- `lighting.lightmap_scale`
Apply in shader and/or at import time when baking the atlas.

## Source Pipeline Follow-Ups
- Source importer currently extracts per-face lightmaps as small textures and groups by face id.
- Consider implementing a similar atlasing approach (or other batching strategy) for Source maps.

## Related (Non-Blocking, Future)
- Content-addressed `map_hash` implementation (ADR 0002) and canonical hashing rules.

