# Scope 04: Console Command Bus and MCP Realtime Control

Status: `completed`

## Problem
- The project has console and MCP bridge pieces, but not a unified command bus architecture.
- Real-time scene authoring and inspection via MCP is incomplete.
- Console UX lacks expected terminal behavior (history navigation, better hints).

## Outcome
- A command-bus-first architecture where UI and tools invoke typed commands, and MCP can inspect/manipulate the live scene safely and efficiently.

## In Scope
- Define command bus contracts:
  - command registry,
  - argument schema/validation,
  - execution routing (client/server/game-thread),
  - response payload shape.
- Scene introspection commands:
  - list objects by name/type/tag with pagination and filters,
  - inspect selected object details,
  - report player look target / raycast hit.
- Scene manipulation commands:
  - create/delete object by type,
  - move/rotate/scale object,
  - group/ungroup entities,
  - move full group transform together.
- Runtime world controls via console:
  - live fog changes (`mode`, `start/end`, `density`, `color`),
  - skybox switch (with validation).
- Console UX:
  - previous command via Up arrow,
  - command help/hints,
  - discoverability (`help`, completion-friendly metadata).
- Launcher/menu integration:
  - menu actions call bus commands with parameters.

## Out Of Scope
- Network authority model for multiplayer editing.
- Full in-game visual editor UI.

## Dependencies
- `tasks/myfunc/01-runtime-world-baseline.md`
- `tasks/myfunc/02-launcher-and-runflow-redesign.md`

## Implementation Plan
1. Publish command bus ADR and API contracts.
2. Implement registry + typed command metadata.
3. Add scene query/manipulation commands and MCP exposure.
4. Add console history/hints UX improvements.
5. Migrate selected menu/launcher actions to command calls.
6. Add performance safeguards (queueing, frame budget, async where needed).

## Acceptance Criteria
- Any menu action in redesigned runflow maps to a command call.
- MCP can list/filter scene objects with pagination and manipulate targets.
- Fog can be adjusted live through console and reflected immediately.
- Console supports Up-arrow command history and command help hints.
- Command system does not become a frame-time bottleneck under normal usage.

## Risks
- Thread ownership issues when mutating scene from external control paths.
- Overly permissive commands can destabilize gameplay state.

## Validation
- End-to-end MCP script demo:
  - query objects,
  - select by filter,
  - create and move group,
  - modify fog,
  - verify player look target.
- Frame-time sampling during command bursts.

## Progress Notes
- Added typed console command bus contracts in `apps/ivan/src/ivan/console/command_bus.py`:
  - typed command metadata + argument schema specs,
  - validation/coercion (positional + `--name value`/`--name=value`),
  - structured per-command execution result shape (`ok`, `error_code`, `data`, `elapsed_ms`).
- Migrated IVAN runtime command surface to bus-first registration:
  - metadata/discoverability commands: `help`, `cmd_meta`
  - scene introspection: `scene_list`, `scene_select`, `scene_inspect`, `player_look_target`
  - scene manipulation: `scene_create`, `scene_delete`, `scene_transform`, `scene_group`, `scene_ungroup`, `scene_group_transform`
  - world controls: `world_fog_set`, `world_skybox_set`
- Implemented scene runtime registry in `apps/ivan/src/ivan/console/scene_runtime.py` with:
  - filtered/paginated object listing,
  - selected-object inspection,
  - grouping model and transform operations.
- Added console UX improvements:
  - command history Up/Down in `ConsoleUI` + `RunnerDemo` key routing,
  - live command hints/autocomplete (`Tab`) via typed metadata/suggestions.
- Added game-thread execution routing + safeguards:
  - control-server requests are enqueued and drained in the main loop with per-frame budget,
  - bounded queue to prevent MCP/control burst memory growth.
- Extended world runtime controls:
  - fog supports `mode` (`linear`/`exp`/`exp2`/`off`), `density`, and runtime override precedence,
  - skybox switching with runtime validation via discovered skybox presets.
- Added MCP-oriented demo path: `apps/ivan/tools/mcp_scope04_demo.py`.
- Added tests:
  - `apps/ivan/tests/test_console_command_bus.py`
  - `apps/ivan/tests/test_scene_runtime_registry.py`
  - updated `apps/ivan/tests/test_console_ivan_bindings.py` with typed metadata coverage.
