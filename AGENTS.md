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
- When adding dependencies, update:
  - `pyproject.toml`
  - `docs/architecture.md`

## Repository Defaults
- Applications live under `apps/`.
- Python apps use a `src/` layout inside their app folder.
- Current game app: `apps/mvp`
  - Entrypoint: `python -m mvp` (documented in `apps/mvp/README.md`).
