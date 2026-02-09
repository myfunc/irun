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
- Maps **must** be packed as `.irunmap` (zip archive) by default.
- Directory bundles are only used during development/debugging if the user explicitly requests it.
- All import pipelines and tools should produce `.irunmap` output unless overridden.
- Level editing is done in an external editor (TrenchBroom); map conversion/import tooling lives in this repo.

## Repository Defaults
- Applications live under `apps/`.
- Python apps use a `src/` layout inside their app folder.
- Primary project: `apps/ivan` (Ivan)
  - Entrypoint: `python -m ivan` (documented in `apps/ivan/README.md`).

## Git Workflow (PR-Only, No Approvals)
Goal: enable fast "vibe-coding" without stepping on each other, while keeping `main` always mergeable.

- `main` is protected: no direct pushes, no force-pushes. Changes land in `main` only via Pull Requests.
- Work happens in short-lived branches (one change / topic).
- Branch naming:
  - Use engineer-prefixed branches to avoid collisions: `myfunc/<topic>` and `ivan/<topic>`.
  - When the agent creates branches, use `codex/<topic>`.
- When asked to "push a new branch" or "push changes":
  1. Create a branch if needed (never commit directly to `main`).
  2. Push the branch to `origin` and create a PR targeting `main`.
  3. Keep pushing additional commits to the same branch; the PR updates automatically.
  4. Attempt to merge the PR into `main` (prefer squash) and delete the branch.
  5. If the merge is blocked by conflicts, stop and ask the user how to proceed (see "Conflicts" below).
  6. After a successful merge, sync the local `main` to the latest `origin/main` (see "Post-Merge Sync" below).

Local helper script (preferred to reduce manual steps and token usage):
- Sync (push current branch -> create/update PR -> fast-forward local `main`): `./scripts/pr sync`
- Ship (sync + attempt squash-merge PR): `./scripts/pr ship`

Implementation notes for the agent:
- Prefer GitHub CLI:
  - Create PR: `gh pr create --base main --head <branch> --fill`
  - Merge PR: `gh pr merge --squash --auto --delete-branch`
  - If auto-merge is not available, fall back to: `gh pr merge --squash --delete-branch`
- If `gh auth status -h github.com` fails, stop and ask the user to run `gh auth login -h github.com` before continuing.
- "No approvals" means: do not request reviewers, and branch protection must not require PR reviews (0 required). Status checks may be required if the repo has CI.

Conflicts:
- If the PR cannot be merged due to merge conflicts, do not guess conflict resolutions.
- Ask the user which strategy to use:
  - Rebase the branch onto `main` (preferred for linear history).
  - Merge `main` into the branch (preferred if rebase is undesirable).
  - Abort and let the user resolve conflicts manually.
- After the user chooses, perform the chosen strategy, push the updated branch, and re-attempt the PR merge.

Post-Merge Sync (Always):
- After a PR is merged, always attempt to update the local `main` to match `origin/main`.
- Commands:
  - `git fetch origin main`
  - `git switch main`
  - `git pull --ff-only origin main`
- If the fast-forward pull is blocked by local uncommitted changes or divergent history, stop and ask the user whether to stash/commit/discard local changes before retrying. Do not discard changes without explicit user instruction.

Non-goal:
- Do not add repository-side automation that creates PRs or merges automatically (GitHub Actions, bots, etc.). This workflow is intentionally agent-driven.
