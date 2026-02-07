# IRUN

IRUN is a monorepo for multiple applications related to the project.

## Apps
- `apps/mvp`: MVP, the main 3D platformer game (Python + Panda3D)

## Quick Start (MVP)
```bash
cd apps/mvp
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m mvp
```

## Documentation
- Global docs: `docs/` (start with `docs/README.md`)
- Brainstorm: `docs/brainstorm/`
