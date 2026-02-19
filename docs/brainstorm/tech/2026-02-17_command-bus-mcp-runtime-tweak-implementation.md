# Command-Bus-First, MCP Discoverability, and Runtime Tweak Panel (2026-02-17)

## User Goal
- Document and align project documentation with the delivered implementation direction for console control, MCP discoverability, and runtime tuning surfaces.
- Ensure docs accurately reflect: typed command-bus-first approach, MCP filtering/pagination, schema-driven F10 tweak panel, and Windows-capable COPY export.

## User Motivation
- Implementation has evolved; documentation must stay in sync to avoid confusion and support onboarding.
- MCP-driven workflows (Cursor, external tools) depend on accurate command metadata and discoverability.
- Runtime tuning (RPG viewmodel, etc.) needs reliable clipboard export for Windows developers.
- AGENTS.md mandates: every functional change must be accompanied by updated documentation.

## Current Direction
- **Full typed command-bus-first approach** for both client and server command surfaces:
  - Single typed registry (`CommandBus`) with `CommandMetadata`, `CommandArgSpec`, `CommandResult`.
  - Schema validation, structured execution responses (`ok`, `error_code`, `data`, timings).
  - Client and server both expose localhost JSON-lines control bridge; MCP discoverability via `cmd_meta` and `console_commands`.
- **MCP `console_commands`** supports filtering (`prefix`, `tag`) and pagination (`page`, `page_size`, max 200).
- **Schema-driven runtime tweak panel** (F10):
  - Reads/writes via typed console commands only (`vm_rpg_*`).
  - Schema in `runtime_tweak_schema.py` (`TweakFieldSpec`, `RPG_VIEWMODEL_FIELDS`).
  - COPY button exports console script to clipboard.
- **COPY export Windows-capable**:
  - `clipboard.py` uses ctypes + user32/kernel32 on Windows (no extra deps).
  - Graceful fallback on other platforms (pyperclip if installed).

## Open Questions / Risks
- MCP `tools/list` schema for `console_commands` may not yet advertise `tag`, `page`, `page_size` in inputSchema; implementation accepts them. Consider aligning schema for full discoverability.
- Server command surface remains simpler (basic commands + cvars) than client; both share control bridge protocol.
- Clipboard fallback on non-Windows requires pyperclip; users may see "Clipboard unavailable" if not installed.

## Timestamped Notes
- **2026-02-17**: Initial capture. Updated `docs/features.md`, `docs/architecture.md`, `docs/console-control-and-mcp.md`, `docs/roadmap.md`, `apps/ivan/README.md` to reflect:
  - Typed command-bus-first for client+server.
  - MCP `console_commands` filtering/pagination.
  - Schema-driven F10 tweak panel with Windows-capable COPY.
  - Added `runtime_tweak_schema.py`, `clipboard.py` to architecture and source-of-truth lists.
