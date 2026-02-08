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

List apps:
```bash
./runapp list
```

## Ship Changes (PR Workflow Helper)
This repo uses a PR-only workflow: changes land in `main` via Pull Requests.

Create a topic branch (optional helper):
```bash
./scripts/pr start my-topic
```

After committing your changes, sync the current branch (push -> PR -> update local `main`):
```bash
./scripts/pr sync
```

If you want to attempt merging the PR (squash) when possible:
```bash
./scripts/pr ship
```

If you only want to push and open/update the PR (no merge attempt):
```bash
./scripts/pr ship --no-merge
```

Branch naming for `start` can be customized via `IRUN_BRANCH_PREFIX` (default: `myfunc`).

## UI Kit Demo
Run the UI kit playground:
```bash
./runapp ui_kit
```

Smoke screenshot:
```bash
./runapp ui_kit --smoke-screenshot /tmp/irun-ui-kit.png
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
