# Task System

This directory stores delivery-oriented work items that are larger than a single PR.

## Goals
- Keep implementation work in clearly scoped chunks.
- Make dependencies explicit before coding.
- Provide a single place to track sequence, ownership, and acceptance criteria.

## Structure
- `tasks/<owner>/` contains one engineer stream (for example `tasks/myfunc/`).
- One markdown file per major scope.
- File naming:
  - `YYYY-MM-DD_short-title.md` for dated proposals.
  - `kebab-case.md` for persistent scope docs.

## Recommended Scope Template
- **Problem**
- **Outcome**
- **In scope**
- **Out of scope**
- **Dependencies**
- **Implementation plan**
- **Acceptance criteria**
- **Risks**
- **Validation**

## Dependency Rules
- Dependencies are listed as relative task file paths.
- No scope starts implementation until all hard dependencies are complete.
- If a scope is blocked, create a short unblocker task instead of expanding scope.

## Delivery Workflow
1. Define scope doc and dependencies.
2. Link impacted docs (`docs/architecture.md`, `docs/features.md`, ADRs if needed).
3. Implement in small PRs against the same scope.
4. Keep acceptance criteria updated to reflect reality.
5. Mark status in the scope file (`planned`, `in-progress`, `done`).

## Status Convention
- `planned`
- `in-progress`
- `blocked`
- `done`

## Notes
- This is planning and execution metadata, not brainstorm material.
- High-level ideas still belong in `docs/brainstorm/`.
