# ADR 0004: Packed Map Bundles (.irunmap)

Date: 2026-02-08

## Context
Imported BSP maps currently generate large directory trees under `apps/ivan/assets/imported/` (textures, lightmaps, resources, and `map.json`).
This creates friction for collaboration:
- maps produce hundreds or thousands of small files,
- git diffs are noisy and slow,
- moving/sharing maps as a single artifact is awkward.

At runtime we still want to support development workflows where assets remain unpacked (easy to inspect and tweak).

## Decision
We introduce a packed map-bundle storage format: `.irunmap`.

**Default distribution format:** `.irunmap` is the default distribution format for map bundles. All import pipelines and tools produce `.irunmap` unless overridden. Directory bundles are supported only as an explicit development/debugging override when the user requests them.

`.irunmap` is a zip archive with **low compression** intended for fast pack/unpack:
- Archive root contains `map.json`.
- Adjacent folders follow the same layout as directory bundles:
  - `materials/`
  - `lightmaps/`
  - `resources/`
  - (future) chunked geometry payloads for format v3

Runtime loading rules:
- If the selected bundle is a `.irunmap`, extract it to a local cache under `~/.irun/ivan/cache/bundles/<hash>/` and load from the extracted directory.
- If the selected bundle is a directory (contains `map.json`), load it directly — this is an explicit dev/debug override, not the default distribution path.

Run metadata rules:
- Directory bundles use `<bundle>/run.json`.
- Packed bundles use a sidecar file next to the archive: `<bundle>.run.json`.
  - Rationale: allows editing presets/spawn/course without rewriting the archive.

Tooling:
- GoldSrc importer can output either a directory bundle or a packed `.irunmap` bundle (auto-detected by output path extension or explicitly selected).

## Status
Accepted (implemented for v2 bundles).

## Consequences
- Imported maps become single-file artifacts suitable for git LFS or external distribution.
- Runtime remains compatible with unpacked bundles for debugging and iteration.
- Packed bundle updates invalidate the cache (new hash); old caches may accumulate until a cleanup tool is added.

