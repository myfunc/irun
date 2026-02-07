# IRUN

IRUN is a monorepo for applications related to the project.

## Apps
- `apps/ivan`: Ivan, first-person flow runner movement demo (Python + Panda3D)

## Quick Start (Ivan)
```bash
cd apps/ivan
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m ivan
```

## Documentation
- Global docs: `docs/` (start with `docs/README.md`)
- Brainstorm: `docs/brainstorm/`
