# Console Control and MCP Reference

This document is the canonical reference for everything currently available through the IVAN console surface (local console, localhost control bridge, and MCP tools).

## Surfaces and Transport

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
  - purpose: list typed command metadata
  - args:
    - `prefix` (optional command-name filter)
    - `role` (optional string: `client` or `server`, default `client`)

## Discoverability Commands

- `help [command]`
  - no args: list commands and cvars
  - with `command`: show details for one typed command when available
- `cmd_meta [--prefix <name>]`
  - returns machine-friendly JSON with typed command metadata:
    - `name`, `summary`, `route`, `tags`, `args[]`

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

## Legacy/Compatibility Commands (client runtime)

- `echo <text>`
- `exec <path>`
- `connect <host> [port]`
- `disconnect`
- `ent_list`
- `ent_get <name> [path]`
- `ent_set <name> <path> <json>`
- `ent_dir <name> [path]`
- `ent_pos <name> [x y z]`
- `world_runtime`

### Replay/Telemetry/Tuning Workflows (client runtime)

- `replay_export_latest [out_dir]`
- `replay_export <replay_path> [out_dir]`
- `replay_compare_latest [out_dir] [route_tag]`
- `feel_feedback <text> [route_tag]`
- `tuning_backup [label]`
- `tuning_restore [name_or_path]`
- `tuning_backups [limit]`
- `autotune_suggest <route_tag> <feedback_text> [out_dir]`
- `autotune_apply <route_tag> <feedback_text> [out_dir]`
- `autotune_eval <route_tag> [out_dir]`
- `autotune_rollback [backup_ref]`

## Dedicated Server Console Commands

Server console intentionally keeps a smaller command set:

- `help`
- `echo <text>`
- `exec <path>`
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

## Source of Truth

This reference is synchronized with:

- `apps/ivan/src/ivan/console/ivan_bindings.py`
- `apps/ivan/src/ivan/console/server_bindings.py`
- `apps/ivan/src/ivan/console/autotune_bindings.py`
- `apps/ivan/src/ivan/physics/tuning.py`
- `apps/ivan/src/ivan/mcp_server.py`

When adding/removing commands or tuning fields, update this file in the same change.
