---
name: ivan-console-mcp
description: Operates IVAN through MCP console control, including command discovery, scene/world runtime manipulation, replay telemetry, and tuning workflows. Use when the user asks to drive IVAN via MCP, run console commands remotely, inspect command metadata, or automate console-based validation.
---

# IVAN Console MCP Operations

## When To Use
- The task mentions MCP, console bridge, `ivan-mcp`, `console_exec`, or `console_commands`.
- The user wants runtime scene/world edits without manual in-game typing.
- The user wants command discovery or machine-readable command metadata.

## Preconditions
1. IVAN process is running (client and/or dedicated server).
2. Console control bridge is reachable:
   - client: `127.0.0.1:7779` (`IRUN_IVAN_CONSOLE_PORT`)
   - server: `127.0.0.1:39001` (`IRUN_IVAN_SERVER_CONSOLE_PORT`)
3. MCP server is started:
   - `ivan-mcp --control-host 127.0.0.1 --control-port 7779`

## MCP Tool Surface
- `console_exec`
  - Input: `line` (required), `role` (`client` or `server`, optional)
  - Use for command execution.
- `console_commands`
  - Input: `prefix` (optional), `role` (optional)
  - Use for typed command metadata discovery.

## Recommended Workflow
1. Discover first:
   - call `console_commands` with optional prefix.
   - call `console_exec` with `help` for human-readable list.
2. Execute minimal command set needed for user goal.
3. Validate result with introspection command:
   - scene changes: `scene_inspect` or `scene_list`
   - world changes: `world_runtime`
4. Report command outputs and key fields clearly.

## High-Value Command Groups
- Discoverability: `help`, `cmd_meta`
- Scene introspection: `scene_list`, `scene_select`, `scene_inspect`, `player_look_target`
- Scene manipulation: `scene_create`, `scene_delete`, `scene_transform`, `scene_group`, `scene_ungroup`, `scene_group_transform`
- World controls: `world_fog_set`, `world_skybox_set`, `world_map_save`
- Telemetry/tuning: `replay_export_latest`, `replay_export`, `replay_compare_latest`, `feel_feedback`, `tuning_backup`, `tuning_restore`, `tuning_backups`, `autotune_suggest`, `autotune_apply`, `autotune_eval`, `autotune_rollback`

## Safety Notes
- Prefer typed command-bus commands over ad-hoc legacy commands.
- Use `role=client` unless the user explicitly targets server runtime.
- For mutating commands, verify with readback command before concluding success.
- If bridge connection fails (`WinError 10061` / refused), report that IVAN is not listening on the selected port and suggest checking active process and env port values.

## Quick Examples
- List typed commands:
  - `console_commands {}`
- Filter world commands:
  - `console_commands {"prefix":"world_"}`
- Execute command:
  - `console_exec {"line":"scene_list --page 1 --page_size 20","role":"client"}`
- Update fog:
  - `console_exec {"line":"world_fog_set --mode exp2 --density 0.03","role":"client"}`
