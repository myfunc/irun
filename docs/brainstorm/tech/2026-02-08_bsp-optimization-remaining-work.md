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
- Runtime groups by `(material, page, styles_tuple)` instead of `(material, face_id)`.
  - `styles_tuple` is the face's 4 lightstyle ids (255/None for unused slots).
  - Rationale: current runtime lightstyle animation (`WorldScene.tick`) is driven by one uniform (`lm_scales`) per draw call.
    If we batch faces with different styles into the same Geom, we lose correctness unless we add per-vertex style indices.

Importer work (GoldSrc):
- Build atlas pages (e.g. 512x512 or 1024x1024) and pack each face's `(w,h)` lightmap blocks into atlas pages.
- Packing constraints:
  - Add 2px padding (or duplicate-edge padding) around each rect to reduce bilinear bleed.
  - Keep packing deterministic: stable iteration order by `face_idx`, stable packer (no randomization).
  - Prefer power-of-two atlas sizes for GPU friendliness; start with `1024x1024` (tune later).
- Output:
  - `lightmaps/atlas_<page>_slot<slot>.png` (4 textures per page, one per style slot)
    - For faces missing a given slot: write black into that face's rect in that slot's atlas.
    - This lets a face have a single `(page, rect)` while still supporting 0..4 style slots.
  - Per-face metadata in `map.json` (new schema; see example below):
    - `page` (int)
    - `rect` (x, y, w, h) in atlas pixels (excluding padding)
    - `styles` (length 4: int style id or 255)
- Update triangle `lm` UVs to point into the atlas:
  - `atlas_u = (rect.x + u * rect.w) / atlas_w`
  - `atlas_v = (rect.y + v * rect.h) / atlas_h`
  - Note: preserve the existing GoldSrc->Panda V flip (the importer already flips V once).

Suggested `map.json` shape (GoldSrc):
```json
{
  "lightmaps": {
    "encoding": "goldsrc_rgb",
    "scale": 16.0,
    "atlases": {
      "size": [1024, 1024],
      "pages": [
        {
          "slot_paths": [
            "lightmaps/atlas_0_slot0.png",
            "lightmaps/atlas_0_slot1.png",
            "lightmaps/atlas_0_slot2.png",
            "lightmaps/atlas_0_slot3.png"
          ]
        }
      ],
      "faces": {
        "12": { "page": 0, "rect": [128, 256, 17, 9], "styles": [0, 255, 255, 255] }
      }
    }
  },
  "triangles": [
    { "m": "BRICK1", "lmp": 0, "lmr": [128, 256, 17, 9], "lm": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6], "lms": [0, 255, 255, 255] }
  ]
}
```
Notes:
- Two viable approaches:
  1) Store atlas page/rect per face under `lightmaps.atlases.faces` and keep triangles with `lmi=face_idx`.
     Runtime looks up face->(page, rect, styles) and uses already-atlased UVs.
  2) Inline `lmp` (lightmap page), `lms` (styles tuple) per triangle and drop face lookup.
     Bigger JSON but simpler runtime. Prefer (1) first to keep payload small.

Runtime work:
- Change grouping key from `(material, lmi)` to `(material, page, styles_tuple)`.
  - File: `apps/ivan/src/ivan/world/scene.py` (`_attach_triangle_map_geometry_v2` currently groups by `(material, lmi)`).
  - If we keep per-face lookup (approach 1 above), runtime needs:
    - face_idx -> `page`, `styles_tuple` lookup (and uses already-atlased `lm` UVs).
    - page -> slot texture paths (`atlas_<page>_slot<slot>.png`).
- Bind atlas textures instead of per-face textures:
  - For each `(material, page, styles_tuple)` node, bind `lm_tex0..3` from that page.
  - Keep using `lm_scales` uniform driven by `styles_tuple` in `WorldScene.tick`.

Acceptance:
- Draw calls should scale with `(materials * atlas_pages * chunks)` rather than face count.
- With animated lightstyles enabled, surfaces using different style patterns must still animate correctly
  (hence the `styles_tuple` in the draw-call key unless we add per-vertex style indices).

Implementation slice (recommended PR order):
1. Importer: atlas writer + JSON schema + UV remap (no runtime changes yet; keep old per-face mode behind a flag).
2. Runtime: load atlas pages and switch grouping key; keep a compatibility path for old bundles.
3. Remove per-face lightmap extraction once atlas path is stable.

### 2) Chunking (Stable Batching, Future Streaming)
Problem:
- Even with atlasing, a single huge batch can become expensive for culling and future streaming.

Work:
- Split baked geometry into chunks (e.g. spatial partitions).
- Prefer chunking that is:
  - deterministic (stable output for the same input BSP)
  - coarse enough to cut draw calls and culling cost, but fine enough to cull well (start with ~64-256 chunks per map)
  - compatible with later PVS: chunks should have AABBs for fast reject
- Group/batch within each chunk by `(material, page, styles_tuple)` and produce stable, deterministic output.

Possible chunking strategies:
- Grid chunking (fast to implement):
  - Pick a cell size (e.g. 512 or 1024 world units in scaled space).
  - Assign each triangle by centroid to a cell id `(cx, cy, cz)` (or 2D `(cx, cy)` if vertical stacks are rare).
  - Derive chunk AABB from triangle bounds.
- BSP leaf chunking (ties into PVS):
  - Use leaf id as "chunk", or merge small leaves into leaf-groups.
  - Requires importing leaf/marksurface data.

Suggested runtime representation:
- One NodePath per chunk.
- Each chunk contains 1..N GeomNodes grouped by `(material, page, styles_tuple)`.
- Maintain chunk AABBs for frustum culling (even before PVS).

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

GoldSrc-specific notes (to reduce guesswork later):
- The data needed for PVS-based visibility is typically in:
  - BSP leaf structures (bounding boxes + marksurface ranges)
  - MARKSURFACES / leaf->surface index list
  - VISIBILITY lump (RLE-compressed bitsets per leaf)
- Export plan (importer -> `map.json`):
  - `bsp_vis.leaves[]`: `{"mins":[x,y,z],"maxs":[x,y,z],"first_marksurface":i,"num_marksurfaces":n,"vis_ofs":ofs}`
  - `bsp_vis.marksurfaces[]`: list of face indices
  - `bsp_vis.visdata`: raw bytes (base64) or keep as an external binary blob `resources/vis.bin`
  - Keep it optional and behind a flag; maps without VIS should still run (fallback to frustum+chunk culling).
- Runtime plan:
  1) Find current leaf:
     - Option A: export enough BSP node/plane data to do a true point-in-leaf walk.
     - Option B (fast hack): pick the leaf whose AABB contains the camera point; if none match, fallback to "all visible".
  2) Decode PVS for that leaf into a `visible_leafs` bitset.
  3) Compute `visible_chunks` by leaf->chunk mapping:
     - If chunking is leaf-based: trivial.
     - If chunking is grid-based: precompute chunk<->leaf overlap (AABB overlap) once at load time.
  4) Show/hide chunk NodePaths each frame (or when leaf changes).

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

## Open Questions / Decisions To Record (ADR Candidates)
- Atlas size + padding policy:
  - 512 vs 1024 vs 2048
  - padding pixels and whether to duplicate edge texels into padding
- Where to store VIS data:
  - inline JSON (base64) vs external binary blob inside the bundle
- Lightstyle correctness vs draw calls:
  - keep batching key including `styles_tuple` (simple, likely good enough)
  - or add per-vertex style indices + uniform/texture lookup (more complex, potentially fewer draw calls)
