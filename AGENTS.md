# IRUN Agent Instructions

## Language Policy
- All repository files and all documentation are **English by default** (code comments, commit messages, docs, tickets, notes).
- **Russian is allowed only in chat**.

## Documentation Rules (Non-Negotiable)
- Every functional change must be accompanied by updated documentation in the same PR/commit set.
- We maintain **global documentation** for project-wide concepts. If a task changes any concept/feature/scope, update the relevant global docs immediately.
- If you need to verify something about the project, **inspect the code first**, then consult documentation.

## Global Documentation (Keep Current)
Update these when their content changes:
- `docs/project.md`: Project definition, pillars, target platforms, constraints.
- `docs/features.md`: Feature inventory (current + planned), scope boundaries.
- `docs/architecture.md`: Technical architecture, runtime, dependencies, structure.
- `docs/roadmap.md`: Milestones and near-term priorities.
- `docs/decisions/`: Architectural Decision Records (ADRs) for significant choices.

## Brainstorm Structure
Brainstorming lives under `docs/brainstorm/` and is intentionally informal, but still English.
- `docs/brainstorm/inbox/`: Unsorted ideas and quick notes.
- `docs/brainstorm/concepts/`: High-level game concepts, loops, pillars.
- `docs/brainstorm/mechanics/`: Movement, combat, progression, platforming systems.
- `docs/brainstorm/tech/`: Engine/runtime notes, tools, pipelines, perf.
- `docs/brainstorm/levels/`: Level design patterns, setpieces, traversal.
- `docs/brainstorm/ui-ux/`: HUD, menus, onboarding, accessibility.
- `docs/brainstorm/templates/`: Reusable templates for proposals/notes.
- `docs/brainstorm/archive/`: Old/obsolete/merged notes.

Naming convention:
- Use `YYYY-MM-DD_short-title.md` for new brainstorm docs when date matters.
- Otherwise use concise kebab-case filenames.

## Collaboration (Two Engineers)
- Prefer small, reviewable changesets.
- Keep commits coherent; avoid mixing refactors with feature changes.
- Avoid "god files": as features grow, split code into logically scoped modules/files so multiple people/agents can work in parallel with minimal merge conflicts.
- Size guardrail: if a file grows beyond **500 lines of code**, the agent must proactively propose (and preferably implement) a logical split into smaller modules with clear ownership boundaries.
- Default pattern:
  - One concern per module (scene loading, input, physics, UI, importers, etc).
  - Keep public APIs small and explicit; prefer composition over giant classes.
- When adding dependencies, update:
  - `pyproject.toml`
  - `docs/architecture.md`

## Map Bundles
- **`.map` files** (Valve 220 format) are the **primary authoring format** for IVAN-original maps. The engine loads them directly during development (no BSP compilation needed).
- Maps **must** be packed as `.irunmap` (zip archive) for distribution.
- Directory bundles are only used during development/debugging if the user explicitly requests it.
- All import pipelines and tools should produce `.irunmap` output unless overridden.
- Level editing is done in an external editor (TrenchBroom); map conversion/import tooling lives in this repo.
- TrenchBroom game configuration lives at `apps/ivan/trenchbroom/` (`GameConfig.cfg` + `ivan.fgd`). See the README there for install instructions.

## Repository Defaults
- Applications live under `apps/`.
- Python apps use a `src/` layout inside their app folder.
- Primary project: `apps/ivan` (Ivan)
  - Entrypoint: `python -m ivan` (documented in `apps/ivan/README.md`).

## Temporary Artifacts
- Store smoke-test screenshots, quick debug captures, and other temporary run artifacts only under `.tmp/`.
- Do not write smoke outputs into source/docs trees (for example `apps/ivan/` or `docs/brainstorm/.../screenshots/`).
- Temporary artifacts are non-deliverable by default and should not be committed unless the user explicitly asks.
## Git Workflow (Automatic Push-to-Main Flow)
When the user asks to "push", "sync", "push to main", or uses equivalent Russian phrasing like "запушить", "синхронизироваться", "пуш в мейн", always run the same sequence:

1. If current branch is `main`, create and switch to a new branch named `codex/<topic>`.
2. Ensure all current changes are committed on that branch.
3. Push the branch to `origin`.
4. Create (or update) a PR from that branch into `main` with a concise summary of changes.
5. Merge the PR into `main` (prefer squash) and delete the branch.
6. Return local repo to `main` and fast-forward sync it with `origin/main`.

Defaults and constraints:
- Never push directly to `main`.
- Never force-push.
- Use GitHub CLI for PR operations (`gh pr create`, `gh pr merge`).
- If `gh auth status -h github.com` fails, stop and ask the user to run `gh auth login -h github.com`.

Conflict handling (before merge):
- If merge conflicts block PR merge, first attempt to resolve them safely by updating the branch with latest `main`, resolving straightforward conflicts, and pushing the updated branch.
- If conflicts are non-trivial or risky, stop and ask the user how to resolve them.
- If conflicts are resolved successfully, continue and merge the PR, then switch back to `main` and sync.
