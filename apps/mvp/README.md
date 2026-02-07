# MVP

MVP is an early-stage **3D platformer** app in the IRUN monorepo, written in **Python** (Panda3D).

## Quick Start

Requirements:
- Python 3.9+ recommended

Install and run:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m mvp
```

Smoke run (starts and exits quickly):
```bash
python -m mvp --smoke
```

## Controls (Prototype)

Movement:
- `W/A/S/D` - Move
- `Space` - Jump
- `Shift` - Sprint (only when enabled via feature flag)

Tuning + feature flags:
- `F1` - Toggle debug/tuning overlay
- `F2` - Toggle air control
- `F3` - Toggle bunny hop
- `F4` - Toggle friction
- `[` / `]` - Adjust gravity
- `;` / `'` - Adjust jump speed
- `,` / `.` - Adjust move speed
- `O` / `P` - Adjust friction
- `F5` - Save tuning JSON
- `F6` - Reload tuning JSON

## Settings

The game loads tuning settings from `mvp_settings.json` in the current working directory by default.
You can override the path:
```bash
python -m mvp --settings path/to/settings.json
```

## Documentation
- Global IRUN docs live at repo root in `docs/`.
