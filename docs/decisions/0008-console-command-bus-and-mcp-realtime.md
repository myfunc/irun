# ADR 0008: Console Command Bus and MCP Realtime Control

## Status
Accepted

## Context
- Scope 04 requires a command-bus-first runtime control surface shared by in-game console, localhost control bridge, and MCP.
- Existing console commands were mostly ad-hoc string handlers with weak discoverability and no typed schema validation.
- MCP/control requests were executed from socket threads, which risked scene/thread ownership issues.

## Decision
- Introduce a typed command bus (`ivan.console.command_bus`) with:
  - explicit command metadata (`name`, `summary`, `route`, `tags`, argument specs),
  - argument schema validation/coercion for positional and named options,
  - structured result payloads (`ok`, `error_code`, `data`, `elapsed_ms`).
- Keep legacy command/cvar registration for compatibility, but execute bus commands first.
- Add scene/runtime command surface (`ivan.console.scene_runtime`) for:
  - scene introspection/list/select/inspect/raycast,
  - scene manipulation (create/delete/transform/group/ungroup/group-transform),
  - world runtime controls (fog + skybox).
- Route control-server command execution to the game thread:
  - worker thread enqueues command requests,
  - game loop drains queue under per-frame budget and returns results.
- Expose discoverability metadata through command `cmd_meta` and MCP tool `console_commands`.

## Consequences
- Console and MCP now share one typed, discoverable command contract.
- Runtime mutations are safer because scene changes execute on the game thread.
- Command bursts are less likely to affect frame time due to bounded queue + per-frame processing budget.
- Some legacy commands remain for backward compatibility, increasing temporary surface area until full migration.

## Follow-ups
- Migrate remaining legacy commands to typed bus handlers over time.
- Consider adding optional auth/allowlist for localhost control bridge in non-dev builds.
- Add automated runtime perf sampling for sustained command bursts in CI smoke runs.

