# ADR 0009: Shared Resource Packs (.irunres)

Date: 2026-02-11

## Context
Map bundles currently embed textures either via `materials.converted_root` (directory of PNGs) or via WAD extraction at offline tooling time. There is no shared, content-addressed asset format for maps to reference external texture packs. WAD runtime loading is being removed in favor of explicit resource packs.

## Decision
We introduce **shared resource packs** (`.irunres`):

- **Format**: zip archive with `manifest.json` at root, schema `ivan.resource_pack.v1`.
- **Manifest**: `schema`, `pack_hash` (pack identity), `assets` (asset_id → path-in-archive).
- **Cache**: runtime extracts to `~/.irun/ivan/cache/resource_packs/<content_hash>/`. Content hash invalidates cache on pack change.
- **Map payload extension**: `resource_packs` (list of paths to .irunres), `asset_bindings` (material_name → asset_id).

Runtime behavior:
- When `map.json` has `resource_packs` and `asset_bindings`, resolve assets by stable `asset_id` from packs. Build `_material_texture_index` from resolved paths.
- If any referenced material's asset is missing in packs, fail load with `MissingResourcePackAssetError`.
- When no `resource_packs`, fall back to `materials.converted_root` (backward compat).

**Hard cutover**: The runtime map loading path (map.json/.irunmap) never reads WAD textures. WAD remains only as optional offline tooling input (e.g. `convert_map_file`, `pack_map.py`).

## Status
Accepted (implemented).

## Consequences
- Maps can share texture packs across multiple maps; packs are content-addressed and cached.
- Missing pack assets fail clearly instead of showing checkers.
- Tooling (pack_map, GoldSrc importer) can emit `resource_packs` + `asset_bindings` for pack-based maps.
