# Half-Life RPG Viewmodel Bootstrap (2026-02-11)

## User Goal
- Extract Half-Life RPG assets and use the grenade launcher model as the in-game weapon model now (alignment can be adjusted later).

## User Motivation
- Quickly replace placeholder weapon visuals with recognizable Half-Life source assets.
- Unblock rapid visual iteration first, then refine exact first-person alignment in follow-up tweaks.

## Current Direction
- Copy raw Half-Life RPG model files into project assets for traceability.
- Convert the Half-Life `v_rpg` decompiled SMD mesh into a Panda-loadable OBJ viewmodel.
- Wire combat FX rocket slot to prefer the imported OBJ and keep a procedural fallback path.

## Open Questions / Risks
- GoldSrc `.mdl` is not directly loadable in this Panda3D setup, so conversion quality/axis mapping needs manual validation.
- Current rocket viewmodel transform is intentionally rough and likely requires tuning for camera fit.
- Additional mesh cleanup (material consolidation, triangulation optimization, animation support) may be needed later.

## Timestamped Notes
- **2026-02-11T14:15Z**: Confirmed Panda3D/assimp rejects Half-Life `.mdl` directly in this environment.
- **2026-02-11T14:15Z**: Extracted/decompiled `v_rpg` with `decompmdl`, generated OBJ+MTL+textures under `apps/ivan/assets/models/halflife/v_rpg/`.
- **2026-02-11T14:15Z**: Integrated runtime fallback logic: use imported OBJ for rocket slot when available, else procedural rocket mesh.
- **2026-02-11T14:30Z**: Fixed viewmodel invisibility bug: centering+scaling now uses a dedicated pivot node (instead of scaling the same centered node), which keeps bounds near camera and makes the rocket slot model render again.
- **2026-02-11T14:26Z**: Applied first visual alignment pass toward HL reference framing (lower-right placement + horizontal silhouette) using explicit imported RPG transform constants.
- **2026-02-11T14:31Z**: Added temporary live debug tooling in console (`vm_rpg_*` commands) to tweak imported RPG position/rotation/size at runtime without code edits.
- **2026-02-16T11:40Z**: User reported imported RPG appears inside-out in first-person. Direction: force imported OBJ path into opaque two-sided rendering with cull disabled to avoid alpha-sorting/cull artifacts.
- **2026-02-16T11:40Z**: Added `vm_rpg_model_scale <x> <y> <z>` for live non-uniform scale tuning (including axis mirroring) so camera fit/alignment can be corrected without code edits.
- **2026-02-16T12:25Z**: Locked imported RPG default mirror baseline to `model_scale=(-1, 1, 1)` (and reset default) so inside-out orientation is corrected immediately on fresh launch.
