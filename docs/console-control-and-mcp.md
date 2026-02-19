# Console Control and MCP Reference

This document is the canonical reference for everything currently available through the IVAN console surface (local console, localhost control bridge, and MCP tools).

## Surfaces and Transport

- Full typed command-bus-first approach: client and server command surfaces share the same command runtime and control bridge protocol.
- In-game console (`F4`) and external control use the same command runtime.
- Client process starts localhost JSON-lines control bridge:
  - host: `127.0.0.1`
  - port: `7779` (override with `IRUN_IVAN_CONSOLE_PORT`)
- Dedicated server process starts localhost JSON-lines control bridge:
  - host: `127.0.0.1`
  - port: `39001` (override with `IRUN_IVAN_SERVER_CONSOLE_PORT`)
- MCP stdio server: `ivan-mcp` (`python -m ivan.mcp_server`)

## Cursor MCP Setup (project-local)

Project includes MCP config at `ivan/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ivan-console": {
      "command": "apps/ivan/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "ivan.mcp_server",
        "--control-host",
        "127.0.0.1",
        "--control-port",
        "7779"
      ],
      "env": {
        "PYTHONPATH": "apps/ivan/src"
      }
    }
  }
}
```

## MCP Tools

`ivan-mcp` exposes two tools:

- `console_exec`
  - purpose: execute one console line
  - args:
    - `line` (required string)
    - `role` (optional string: `client` or `server`, default `client`)
- `console_commands`
  - purpose: list typed command metadata with filtering and pagination (MCP discoverability)
  - args:
    - `prefix` (optional string: command-name prefix filter)
    - `tag` (optional string: command must have this tag)
    - `page` (optional int, 1-based, default 1)
    - `page_size` (optional int, max 200, default 50)
    - `role` (optional string: `client` or `server`, default `client`)
  - returns: JSON with `commands[]` and `pagination` (page, page_size, total, total_pages)

## Discoverability Commands

- `help [command]`
  - no args: list commands and cvars
  - with `command`: show details for one typed command when available
- `cmd_meta [--prefix <name>] [--tag <tag>] [--page <n>] [--page_size <n>]`
  - returns machine-friendly JSON with typed command metadata and pagination:
    - `commands[]`: `name`, `summary`, `route`, `tags`, `args[]`
    - `pagination`: `page`, `page_size`, `total`, `total_pages`

## Typed Command Bus Commands (client runtime)

### Scene Introspection

- `scene_list [--name <text>] [--type <text>] [--tag <key>] [--page <n>] [--page_size <n>]`
- `scene_select <target>`
- `scene_inspect [target]`
- `player_look_target [--distance <float>]`

### Scene Manipulation

- `scene_create <object_type> [name]`
  - `object_type`: `box|sphere|empty`
- `scene_delete [target]`
- `scene_transform <mode> <x> <y> <z> [target] [--relative]`
  - `mode`: `move|rotate|scale`
- `scene_group <group_id> <targets_csv>`
- `scene_ungroup <group_id>`
- `scene_group_transform <group_id> <mode> <x> <y> <z> [--relative]`

### World Runtime Controls

- `world_fog_set [--mode off|linear|exp|exp2] [--start <float>] [--end <float>] [--density <float>] [--color_r <0..1>] [--color_g <0..1>] [--color_b <0..1>]`
- `world_skybox_set <skyname>`
- `world_map_save [--include_fog true|false]`

## Typed Commands (client runtime, MCP-discoverable)

All client commands are now typed and registered on the command bus. They support `--arg value` and positional syntax.

### Utility

- `echo [text...]` – print text (greedy positional)
- `exec <path>` – execute script file
- `help [command]` – list commands/cvars or command details
- `cmd_meta [--prefix <name>] [--tag <tag>] [--page <n>] [--page_size <n>]` – typed metadata + pagination

### Multiplayer

- `connect <host> [port]`
- `disconnect`

### Entity Introspection

- `ent_list`
- `ent_get <name> [path]`
- `ent_set <name> <path> <value>`
- `ent_dir <name> [path]`
- `ent_pos <name> [x y z]`

### World

- `world_runtime` – dump diagnostics
- `world_textures <pixelated|smooth> [reload]`

### RPG Viewmodel (typed, MCP-discoverable)

- `vm_rpg_print` – print current state
- `vm_rpg_pos [x y z]` – get/set weapon root position
- `vm_rpg_hpr [h p r]` – get/set weapon root rotation
- `vm_rpg_model_hpr [h p r]` – get/set model-pivot rotation
- `vm_rpg_model_scale [x y z]` – get/set model-pivot scale
- `vm_rpg_size [value]` – get/set size scalar
- `vm_rpg_reset` – reset to defaults

### Replay/Telemetry/Tuning

- `replay_export_latest [out_dir]`
- `replay_export <replay_path> [out_dir]`
- `replay_compare_latest [out_dir] [route_tag]`
- `feel_feedback <text> [route_tag]`
- `tuning_backup [label]`
- `tuning_restore [backup_ref]`
- `tuning_backups [limit]`
- `autotune_suggest <route_tag> <feedback_text> [out_dir]`
- `autotune_apply <route_tag> <feedback_text> [out_dir]`
- `autotune_eval <route_tag> [out_dir]`
- `autotune_rollback [backup_ref]`

## Dedicated Server Console Commands

Server console intentionally keeps a smaller command set, fully typed on the command bus:

- `help [--command <name>]` — list commands/cvars or show command details
- `echo [--text <...>]` — print text (greedy)
- `exec --path <file>` — execute a .cfg-like script file
- `cmd_meta [--prefix <name>] [--tag <tag>] [--page <n>] [--page_size <n>]` — MCP discoverability (same schema as client)
- same tuning cvars as client runtime (applied through server tuning snapshot path)

## Console CVARs (Physics Tuning Fields)

These cvars exist on both client and server console surfaces (generated from `PhysicsTuning` fields):

- `run_t90`
- `ground_stop_t90`
- `jump_apex_time`
- `slide_stop_t90`
- `grace_period`
- `coyote_buffer_enabled`
- `custom_friction_enabled`
- `slide_enabled`
- `harness_camera_smoothing_enabled`
- `harness_animation_root_motion_enabled`
- `camera_feedback_enabled`
- `character_scale_lock_enabled`
- `camera_base_fov`
- `camera_speed_fov_max_add`
- `camera_tilt_gain`
- `camera_event_gain`
- `jump_height`
- `max_ground_speed`
- `air_speed_mult`
- `air_gain_t90`
- `wallrun_sink_t90`
- `mouse_sensitivity`
- `slide_half_height_mult`
- `slide_eye_height_mult`
- `wall_jump_boost`
- `wall_jump_cooldown`
- `wallrun_min_entry_speed_mult`
- `wallrun_min_approach_dot`
- `wallrun_min_parallel_dot`
- `surf_accel`
- `surf_gravity_scale`
- `surf_min_normal_z`
- `surf_max_normal_z`
- `vault_jump_multiplier`
- `vault_height_boost`
- `vault_forward_boost`
- `vault_min_ledge_height`
- `vault_max_ledge_height`
- `vault_cooldown`
- `autojump_enabled`
- `noclip_enabled`
- `noclip_speed`
- `surf_enabled`
- `walljump_enabled`
- `wallrun_enabled`
- `vault_enabled`
- `grapple_enabled`
- `grapple_fire_range`
- `grapple_attach_boost`
- `grapple_attach_shorten_speed`
- `grapple_attach_shorten_time`
- `grapple_pull_strength`
- `grapple_min_length`
- `grapple_max_length`
- `grapple_rope_half_width`
- `max_ground_slope_deg`
- `step_height`
- `ground_snap_dist`
- `player_radius`
- `player_half_height`
- `player_eye_height`
- `course_marker_half_extent_xy`
- `course_marker_half_extent_z`
- `vis_culling_enabled`

Read/write behavior:
- `<cvar_name>` -> prints current value
- `<cvar_name> <value>` -> parses and applies value
- Bool accepts: `1/0`, `true/false`, `on/off`, `yes/no`, `y/n`

## JSON-lines Control Bridge Protocol

Request:

```json
{"line":"echo hi","role":"client","origin":"mcp"}
```

Response includes:

- `ok`
- `command`
- `out`
- `elapsed_ms`
- `executions[]` with:
  - `name`
  - `ok`
  - `elapsed_ms`
  - `error_code`
  - `data`

## Practical Examples

- List typed scene commands:
  - `cmd_meta --prefix scene_`
- List commands with tag filter and pagination:
  - `cmd_meta --tag mcp --page 1 --page_size 20`
- List commands and cvars:
  - `help`
- Create and move runtime object:
  - `scene_create box test_box`
  - `scene_transform move 4 0 1 test_box`
- Read/modify runtime fog:
  - `world_fog_set --mode exp2 --density 0.03 --color_r 0.6 --color_g 0.7 --color_b 0.8`
  - `world_runtime`
- Save world overrides to map:
  - `world_map_save --include_fog true`

## Runtime Tweak Panel (F10)

Schema-driven panel for RPG viewmodel tuning:
- Reads/writes via typed console commands only (`vm_rpg_*`).
- COPY button exports a console script to clipboard.
- Clipboard: Windows-capable via ctypes (user32/kernel32, no extra deps); graceful fallback on other platforms (pyperclip if installed).

## Source of Truth

This reference is synchronized with:

- `apps/ivan/src/ivan/console/command_bus.py`
- `apps/ivan/src/ivan/console/ivan_bindings.py`
- `apps/ivan/src/ivan/console/server_bindings.py`
- `apps/ivan/src/ivan/console/autotune_bindings.py`
- `apps/ivan/src/ivan/physics/tuning.py`
- `apps/ivan/src/ivan/mcp_server.py`
- `apps/ivan/src/ivan/ui/runtime_tweak_panel.py`
- `apps/ivan/src/ivan/ui/runtime_tweak_schema.py`
- `apps/ivan/src/ivan/ui/clipboard.py`

When adding/removing commands or tuning fields, update this file in the same change.
