# MCP Launch Process Coherence and RPG Runtime Tuning (2026-02-16)

## User Goal
- Ensure MCP commands target the same IVAN runtime instance shown on screen.
- Eliminate duplicate `python -m ivan` processes during normal launcher/runapp workflows.
- Keep imported RPG viewmodel tuning reliable in live runtime sessions.

## User Motivation
- Runtime tuning commands were reported as "no visible effect" because MCP was connected to a different process.
- Duplicate processes made iteration confusing and unstable (wrong interpreter, stale command set, mismatched build behavior).
- User needs predictable one-process launch behavior for fast visual tuning loops.

## Current Direction
- Align launcher defaults with workspace runtime (`apps/ivan/.venv`) and workspace import paths.
- Prevent duplicate game launches from launcher UI while one game process is alive.
- Keep process shutdown deterministic on window close / in-game quit so MCP ports do not remain attached to stale instances.
- Preserve live RPG transform controls through `vm_rpg_*` command surface and document expected verification workflow (`vm_rpg_print` + MCP listener inspection).

## Open Questions / Risks
- Existing user-local launcher config can still override Python path intentionally; this may reintroduce mixed interpreter behavior if misconfigured.
- `--watch` workflows can still confuse users when external tools also launch IVAN in parallel outside launcher guardrails.
- Command discoverability mismatch (`cmd_meta` vs direct command execution) should be audited separately if typed metadata remains unexpectedly empty.

## Timestamped Notes
- **2026-02-16T12:10Z**: Confirmed multiple concurrent `python -m ivan` processes with MCP bound to a different instance than the visible gameplay window.
- **2026-02-16T12:20Z**: Added launcher-side duplicate launch guard (do not spawn a second `IVAN Game` process while one is alive).
- **2026-02-16T12:22Z**: Updated launcher Python resolution to prefer `apps/ivan/.venv` when `python_exe` is unset.
- **2026-02-16T12:24Z**: Added launcher subprocess `PYTHONPATH` injection for workspace-first imports (`apps/ivan/src`, `apps/ui_kit/src`).
- **2026-02-16T12:28Z**: Added explicit window-close exit handling path in IVAN app so closing window follows `userExit()` cleanup and closes MCP bridge.
- **2026-02-16T12:32Z**: Stabilized imported RPG baseline orientation with default model mirror (`model_scale=[-1,1,1]`) and continued runtime tuning via `vm_rpg_*`.
