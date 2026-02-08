# BSP Lightmaps And Visibility Backlog (GoldSrc/Source)

Date: 2026-02-08

## Context / Current Symptoms
- After importing some BSP maps, runtime rendering becomes noticeably slower (likely high draw call count + many textures).
- On imported GoldSrc maps, baked lighting is still perceived as missing or too subtle.
- The engine should behave like GoldSrc/Source: baked lightmaps, lightstyles (animated patterns), proper transparency, and skybox behavior.

## Current Implementation Notes (IVAN)
- Source pipeline: per-face lightmaps are extracted into PNGs; runtime multiplies base texture by per-face lightmap.
- GoldSrc pipeline: extracts per-face lightmaps from `LUMP_LIGHTING` into PNGs and uses per-face mapping. Lightstyles can be animated (10Hz) using a GLSL shader.
- Rendering currently groups triangles by `(material, face_id)` when `lmi` is per-face, which can explode draw calls.

## Goals
1. GoldSrc baked lighting should be visually correct and obvious (match HL/CS 1.6 look within reason).
2. Performance should be acceptable on typical GoldSrc maps (reduce draw calls + texture binds).
3. Keep parity with original behavior:
   - up to 4 lightmap styles per surface
   - default server lightstyle patterns available even when the map does not encode them
4. Keep a workflow to pick a lighting preset per map and persist it in `<bundle>/run.json`.

## Investigation Checklist (Why "No Shadows")
- Confirm bundle contains `lightmaps.faces` and triangles contain `lmi` and `lm` UVs.
- Confirm the runtime actually applies the lightmap shader:
  - GPU/driver supports GLSL 1.30+ (or provide a lower GLSL version fallback).
  - detect shader compilation failure and surface it in the error console.
- Validate lightmap UV mapping:
  - verify `lm` UV is in [0..1] for most vertices (debug print or overlay).
  - verify V flip direction for GoldSrc lightmap row order.
- Validate lightmap data decoding:
  - GoldSrc `LUMP_LIGHTING` stores RGB; ensure correct gamma/space (sRGB vs linear).
  - add a debug mode "lightmap only" and "base only" to isolate issues.

## Performance Work (High Priority)
### 1) GoldSrc lightmap atlasing (match engine behavior)
GoldSrc does NOT store a prebuilt atlas; it stores per-surface blocks in `LUMP_LIGHTING`. The engine packs these into lightmap pages at load time.

Plan:
- Import-time: build lightmap pages (e.g. 512x512 RGBA or RGB) and pack each face's `(w,h)` block into an atlas page.
  - Output: `lightmaps/atlas_<n>.png`
  - For each face: store `atlas_id`, `rect` (x,y,w,h), and style slots.
- Geometry: convert per-vertex lightmap UVs to atlas UVs:
  - `atlas_u = (rect.x + u * rect.w) / atlas_w`
  - `atlas_v = (rect.y + v * rect.h) / atlas_h`
  - keep up to 4 sets (or pack styles into 4 atlas textures).
- Runtime: group triangles by `(material, atlas_id)` instead of `(material, face_id)`.

Expected impact:
- Reduces texture count from "one per face" to "few atlas pages".
- Greatly reduces draw calls and improves cache behavior.

### 2) Visibility / culling
GoldSrc/Source maps contain visibility information (PVS). Current runtime renders everything.

Options:
- Implement leaf-based culling using BSP leaves + PVS:
  - compute current leaf from camera position
  - get visible leaf set from PVS
  - render only faces in visible leaves
- If PVS is too complex initially: coarse chunking by spatial grid and frustum culling.

### 3) Material batching and geometry chunking
- Split map geometry into chunks (by spatial partitions) with stable draw call grouping:
  - `chunk_id` -> list of Geoms per `(material, atlas_id)`
- This also aligns with planned map format v3 chunking.

## Lighting Fidelity Work
### 1) Lightstyle correctness
- Use server defaults when requested (already possible).
- Support per-map overrides:
  - `run.json` should allow `lighting.overrides: { "<style>": "<pattern>" }`.
- Add optional UI in "Run Options" to edit a small number of style overrides (future).

### 2) Gamma / intensity tuning
- GoldSrc/Quake lightmaps can look washed out without proper gamma.
- Add a per-map scalar/gamma in `run.json`:
  - `lighting.lightmap_gamma` (e.g. 2.2)
  - `lighting.lightmap_scale` (e.g. 1.0)
- Apply in shader (or pre-bake into atlas at import time).

## Debug / Tooling (Make It Obvious)
- Runtime debug overlay: show
  - map draw calls (geom count)
  - number of lightmap pages loaded
  - whether lightmap shader is active
  - current lightstyle frame/scales
- Rendering toggles (per run, via `run.json`):
  - base-only
  - lightmap-only
  - fullbright

## Deliverables / Acceptance Criteria
- On a known HL/CS 1.6 map:
  - baked shadows are visible near corners/overhangs
  - dynamic lightstyles (if present/default) animate
  - draw calls do not scale with number of faces (should scale with material count + atlas pages + chunks)
- Import time remains reasonable.

## Risks
- PVS parsing is non-trivial across BSP variants.
- GLSL shader compatibility varies; provide fallback path (e.g. fixed-function modulate for single-style, or lower GLSL version).
- Atlas packing needs stable, deterministic output for caching and reproducibility.

