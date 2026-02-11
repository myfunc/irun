# Map Load Pipeline Debug Session (2026-02-11)

## User Goal
- Identify where startup + map load time is spent end-to-end, not only inside world geometry attach.

## User Motivation
- Current map startup feels fundamentally too slow.
- The team needs concrete stage-level evidence before choosing optimization work.

## Current Direction
- Extend existing `world_load_report` telemetry so one run shows:
  - coarse world stages (`map_parse_import`, `geometry_build_attach`, ...),
  - app startup stages from `RunnerDemo._start_game`,
  - direct `.map` converter sub-stages (parse, WAD resolve, texture extraction, brush conversion, etc.).
- Keep instrumentation smoke-safe and machine-readable in one report payload.

## Open Questions / Risks
- The dominant cost appears to be WAD texture extraction in direct `.map` mode; we still need to validate whether this is mostly one-time (cache warmup) or paid repeatedly.
- Imported/packed `.irunmap` path still needs the same deep measurement to compare against direct `.map` path on this machine.
- If texture extraction remains dominant after warm cache, we may need architectural changes (prebaked texture atlas/index, async predecode, or background extraction with placeholder materials).

## Timestamped Notes
- **2026-02-11T06:30Z**: Added deeper instrumentation:
  - `MapConvertResult.perf_stages_ms` and `perf_counts` in `map_converter.py`.
  - `runtime.map_convert` diagnostics exposure in `WorldScene`.
  - `app_startup.stages_ms` + `app_startup.total_ms` in emitted load report.
- **2026-02-11T06:30Z**: Initial measurements (smoke, direct `.map`):
  - `assets/maps/demo/demo.map`:
    - `total_ms` ~30548 ms
    - `map_parse_import` ~23870 ms
    - `runtime.map_convert.stages_ms.extract_textures` ~23726 ms (dominant)
    - `app_startup.stages_ms.scene_build` ~25112 ms (dominant app stage)
  - `assets/maps/light-test/light-test.map`:
    - `total_ms` ~21012 ms
    - `map_parse_import` ~16374 ms
    - `runtime.map_convert.stages_ms.extract_textures` ~16364 ms (dominant)
    - `app_startup.stages_ms.scene_build` ~16746 ms (dominant app stage)
- **2026-02-11T06:45Z**: Implemented direct `.map` texture cache invalidation by WAD checksums:
  - cache manifest stored in texture cache dir (`.wad_texture_cache_manifest.json`),
  - each resolved WAD fingerprint includes SHA-256,
  - on checksum match, runtime reuses cached PNGs and skips extraction,
  - on checksum mismatch, stale cache is cleared and textures are re-extracted.
