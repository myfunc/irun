# TrenchBroom + IVAN: Quickstart

## 0. Generate editor textures and manifest

Run sync from `apps/ivan` (or use launcher **Generate Textures**):

```bash
python tools/sync_trenchbroom_profile.py
```

This generates:
- `trenchbroom/generated/manifest.json`
- `trenchbroom/generated/editor_paths.json`
- `trenchbroom/generated/textures/` (tool output)
- `assets/textures_tb/` (folder TrenchBroom reads as materials)

Source textures are scanned from `assets/raw/**/*.png`. WAD textures under `assets/textures/` are also extracted when present.

## 1. Install TrenchBroom game config

Use launcher **Sync TB Profile** to install the IVAN game profile. It:
- Copies `GameConfig.cfg` and `ivan.fgd` to `%AppData%\TrenchBroom\games\IVAN\` (Windows; macOS/Linux use equivalent paths)
- Sets `GameConfig` materials root to `textures_tb` and searchpath to `.`
- Writes TrenchBroom Preferences key `Games/IVAN/Path` to `apps/ivan/assets` so TB does not fallback to defaults

**Troubleshooting:** If TrenchBroom logs or uses `defaults/assets` as the game path, run **Sync TB Profile** — `Games/IVAN/Path` was missing or stale.

## 2. Create maps

Use launcher button **New Map (Template)** to create a starter map under:
- `apps/ivan/assets/maps/<short-name>/<short-name>.map`

Template names use the `mYYMMDD_HHMMSS` pattern (e.g. `m250211_143022`).

Template includes:
- world brush
- player start
- one sample textured block

## 3. Available entities

- `info_player_start`
- `info_player_deathmatch`
- `info_teleport_destination`
- `trigger_start`
- `trigger_finish`
- `trigger_checkpoint`
- `trigger_teleport`
- `func_wall`
- `func_detail`
- `func_illusionary`
- `light`
- `light_environment`
- `light_spot`
- `env_fog`
