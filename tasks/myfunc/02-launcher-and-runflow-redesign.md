# Scope 02: Launcher and Runflow Redesign

Status: `completed`

## Problem
- Current launcher and run options expose too many low-level controls too early.
- Key choices are split across launcher and in-game menu, which feels non-intuitive.
- Users want settings selected at launch time, with hints/tooltips, and fewer noisy options.

## Outcome
- A guided runflow:
  - pick map,
  - pick preset,
  - launch selected source `.map`,
  - optionally expand launch/pack options.
- Menu actions internally call console commands with structured arguments.

## In Scope
- Redesign launcher information architecture:
  - Primary actions first (`Launch`, `Pack`, `Stop Game`).
  - Advanced section collapsed by default.
- Add tooltips/help text for major controls and profiles.
- Replace redundant run option menus with a single source of truth.
- Introduce launch presets (for example `Fast Iterate`, `Runtime Visual QA`).
- Ensure menu UI calls typed command handlers (no duplicated behavior paths).

## Out Of Scope
- Full visual re-theme or custom design system rewrite.
- Multiplayer/session orchestration UI.

## Dependencies
- `tasks/myfunc/01-runtime-world-baseline.md`

## Implementation Plan
1. Map current launcher and in-game run-option user journeys.
2. Define target IA and remove/relocate low-value controls.
3. Add tooltip and inline help framework.
4. Route menu actions through command bus interfaces.
5. Add migration notes for existing users.

## Acceptance Criteria
- New user can launch `demo.map` with expected defaults without opening advanced panels.
- Advanced options remain available but are clearly marked.
- Duplicate run controls are removed or unified.
- Tooltip coverage exists for all top-level run controls.

## Risks
- Power users may miss hidden advanced controls.
- Transition period may require compatibility shims for old config fields.

## Validation
- Task-based usability check (first-run flow and advanced flow).
- Smoke test for all launcher action buttons and corresponding command calls.

## Progress Notes
- Implemented guided launcher runflow in `apps/launcher`:
  - map selection via existing browser
  - runtime-first launch targeting selected source `.map`
  - launch/pack options collapsed by default
- Prioritized primary action row to `Launch`, `Pack`, `Stop Game`.
- Added tooltip/help coverage for major controls and all launch presets.
- Reduced noisy launch branches by unifying launch resolution through `launcher.runflow.resolve_launch_plan`.
- Added launch presets:
  - `Fast Iterate`
  - `Runtime Visual QA`
- Routed launcher action callbacks through typed command handlers using `launcher.commands.CommandBus`.
- Added launcher unit tests for runflow resolution and typed command dispatch.
- Updated docs:
  - `docs/features.md`
  - `docs/architecture.md`
  - `apps/launcher/README.md` (includes migration notes for users moving from old buttons/flow)
