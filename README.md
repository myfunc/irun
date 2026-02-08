# IRUN

IRUN is a monorepo for applications related to the project.

## Apps
- `apps/ivan`: Ivan, first-person flow runner movement demo (Python + Panda3D)
- `apps/baker`: Baker ("mapperoni"), companion map viewer/import/bake tool (viewer MVP)

## Quick Start (Ivan)
```bash
cd apps/ivan
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m ivan
```

## Run Apps From Repo Root (Helper)
If you prefer running apps from the repo root (and passing through args), use:
```bash
./runapp ivan --map imported/halflife/valve/bounce
./runapp baker
```

Advanced:
```bash
./runner list
./runner runapp ivan --map imported/halflife/valve/bounce
```

## Quick Start (Baker / mapperoni)
```bash
cd apps/baker
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .

# Viewer MVP (default map selection prefers Crossfire; falls back to committed bundles)
python -m baker
```

## Documentation
- Global docs: `docs/` (start with `docs/README.md`)
- Brainstorm: `docs/brainstorm/`
