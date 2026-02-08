# Roadmap

## Milestone 0: Project Initialization
- Repo structure, docs scaffolding
- Runnable Ivan prototype

## Milestone 1: Movement Prototype
- Player controller: ground/air, jump tuning, basic collision
- Camera prototype
- Minimal "graybox" test level
- First-person bhop/strafe tuning lane with wall-jump experimentation
- In-game admin panel for live physics iteration

## Milestone 2: Level Loop
- Checkpoints + respawn
- Hazards + collectibles
- Simple UI (timer/collect count)
- Handcrafted, player-generated map workflow and validation tools
- Packed map bundles for distribution and git-friendly imports (`.irunmap`)
- Baker app: map viewer + import manager + lighting bake tool (presets, light rig overrides, WYSIWYG preview)
- Map format v3: entities + triggers + lights + baked chunking (data first; streaming later)
- Time trial: local timing + local personal best storage (replays/portal later)
