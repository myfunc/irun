# ADR 0003: Map Format v3 (Entities And Chunking)

Date: 2026-02-08

## Context
IRUN needs a map format that supports:
- an editor-driven workflow (placing pieces and gameplay objects),
- entity interactions (triggers, spawners, buttons, ladders, movers),
- map-authored lighting,
- and future performance features like chunking/streaming,
without coupling the runtime to Valve/GoldSrc/Source semantics.

The current runtime format (v2) is primarily baked geometry (triangles + optional collision triangles) plus minimal metadata (spawn, bounds, materials).

## Decision
We will introduce `map.json` `format_version=3` as an extension of the v2 map bundle concept:
- Keep **baked geometry** as a first-class runtime input (monolithic or chunked).
- Add an **entity model** to represent gameplay-relevant objects:
  - triggers with `on_enter` / `on_exit` event lists,
  - restricted "script calls" (whitelisted engine actions, not arbitrary code),
  - item spawners, buttons, ladders, movers, lights, and map transitions.
- Add `course` metadata that references trigger entity ids for start/finish/checkpoints.

## Status
Accepted (planned; not implemented).

## Consequences
- Editor can author gameplay objects without generating custom code.
- Runtime can evolve from "static mesh world" to interactive maps incrementally.
- Chunking can be introduced in data first and streaming added later without changing the authoring model.
- Importers can map foreign entity fields into v3 entities, preserving unknown fields for debugging.

## References
- `docs/brainstorm/tech/2026-02-08_map-format-v3-entities-chunking.md`

