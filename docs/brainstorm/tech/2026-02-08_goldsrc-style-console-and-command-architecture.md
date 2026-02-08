# Proposal: GoldSrc-Style Console + Command-Driven Architecture (Input/Net/Admin)

Date: 2026-02-08
Owner: myfunc

## Problem
We want:
- A **real console** (GoldSrc/Quake style) where players can type commands, change variables, run scripts, and bind keys.
- A unified way for **client and server** to execute commands (same “language”, different permission/context).
- Multiplayer to “feel local”: responsive local control (already mostly there), plus better **remote player prediction**.
- Persist “quality of life” state such as **last server IP/port**.
- A developer-facing bridge: an **MCP server** that can connect to a running game/server and execute console commands.

## Constraints
- Python + Panda3D runtime (see `docs/architecture.md`).
- We should not ship a bespoke “programming language” unless it buys real power; keep things debuggable and safe.
- Multiplayer must remain server-authoritative; commands that mutate game state must be permissioned.
- The console must be usable for: debugging, admin/config, bindings, scripting basic workflows.
- Keep changes incremental: avoid a full rewrite that blocks iteration for weeks.

## Options
### A) GoldSrc/Quake-style command DSL (recommended baseline)
Parsing model:
- Input is **a list of commands**, each command is `name arg1 arg2 ...`
- Quoting rules for strings (spaces allowed)
- Allow `;` to chain multiple commands on one line
- Allow `exec some.cfg` to load scripts (config files)
- Allow `alias` and `bind`

Pros:
- Very small surface area; easy to reason about.
- Matches GoldSrc mental model: “console is the control plane”.
- Works for binds and admin tasks without embedding a general interpreter.

Cons:
- No “real” control flow unless we add it (`wait`, `toggle`, `incrementvar`, `if`).

### B) Embed a lightweight scripting language (Lua, etc)
Pros:
- Real language, easier to write complex scripts/mods.

Cons:
- Adds dependencies and security surface area.
- Harder to sandbox in Python.
- Debugging and determinism become trickier (especially if scripts run on server).

### C) Use Python itself as the console language (restricted eval)
Pros:
- No new language; maximum power.

Cons:
- Extremely risky to sandbox correctly; huge attack surface.
- Hard to keep stable and deterministic; encourages “console = arbitrary code exec”.

## Recommendation
Start with **Option A** (GoldSrc/Quake-style command DSL) implemented as a small library:
- `cvars`: typed configuration variables with flags (client-only, server-only, replicated, cheat, read-only, archived).
- `cmds`: commands with structured metadata, help text, and permission requirements.
- `bindings`: key -> command string (with `+`/`-` “button commands”).
- `exec`: config script loader.

Then, if we later truly need more expressive scripts, add a *minimal* layer (still not a general interpreter):
- `wait <ticks>` (defer execution)
- `toggle <cvar> [a b]`
- `incrementvar <cvar> <min> <max> <delta>`
- maybe `if <cvar> <op> <value> <cmd>` in a very constrained form

## Architecture Sketch
### 1) Core Console Runtime (shared by client and server)
Key types:
- `Console`: executes text, returns `ConsoleResult` (stdout/stderr lines + error codes).
- `CommandRegistry`: `register(name, handler, flags, help, arg_spec, ...)`
- `CvarRegistry`: `register(name, type, default, flags, help, on_change, ...)`
- `CommandContext`: where the command came from and what it is allowed to do:
  - origin: local player UI, remote player, server local, MCP, test
  - role: client/server
  - permissions: admin, can_cheat, can_configure, etc

Execution model:
- Parse `line` into a list of commands (split by `;` respecting quotes).
- Tokenize args with `shlex`-like rules.
- Expand aliases with recursion/loop guard.
- Dispatch to command handlers or cvar setters.

Output model:
- Console has an output “sink”:
  - in-game overlay (“drop-down console”)
  - logs (stdout, file)
  - network replies (for remote execution / MCP)

### 2) Command Routing: client vs server
Two command namespaces are not enough; we need per-command policy:
- `CL`: can run on client only (UI, input, local graphics).
- `SV`: can run on server only (spawning, authoritative gameplay).
- `BOTH`: safe to run in either, but semantics might differ.
- `FORWARD_TO_SERVER`: on a client, automatically forward command to server when connected.

Suggested rule:
- Default: commands run locally.
- Commands flagged `FORWARD_TO_SERVER` will send a `concmd` packet to server.
- Server validates permissions (admin/config owner/cheats) and executes in server console context.
- Server replies with console output lines and success/failure.

This mirrors GoldSrc patterns (local console + remote admin) without turning the client into an authority.

### 3) Input Bindings via Console
Goal: move from “hardcoded keys” to “command-driven input”.

Approach:
- Define built-in button commands: `+forward`, `-forward`, `+jump`, `-jump`, etc.
- The input system only knows about:
  - key down: execute bound command string
  - key up: execute bound “release” command string (or auto-map `+x` -> `-x`)
- Gameplay tick samples the current “input state” produced by these button commands.

Migration path:
- Keep the existing input code initially.
- Introduce a parallel bindings layer and gradually route actions through console commands.
- Then update UI “Key Bindings” to operate on console `bind` state (and write `config.cfg`).

### 4) Netcode: “feels local” + remote prediction
Local player:
- Current client already does fixed-tick prediction + ack reconciliation (rollback + replay). Keep it.
- Improve “feel” by making prediction and correction **invisible**:
  - keep camera smoothing shell (already exists)
  - tune correction thresholds and decay

Remote players (what we want to add):
- Today: remote players are rendered by snapshot-buffer interpolation only; when we run out of samples, we clamp to last.
- Proposed: add **limited extrapolation** (“dead reckoning”) when target tick is beyond newest sample:
  - store velocity in remote samples (it’s already replicated)
  - extrapolate position forward by `vel * dt`, clamped to `max_extrapolate_ticks` (e.g. 6-12 ticks)
  - keep yaw extrapolation minimal: either hold last yaw or extrapolate from last yaw delta (clamped)
  - on new snapshot, smooth-correct toward authoritative sample (avoid pops)

This is the GoldSrc-style solution: remote prediction is *approximate* but improves responsiveness.

Longer-term (optional):
- If we want much better remote prediction, replicate remote players’ input commands (or compressed intent)
  and run a cheap local proxy simulation. This is higher risk and adds divergence headaches.

### 5) Persist “Last Server Host”
Persist in `~/.irun/ivan/state.json`:
- `last_net_host`
- `last_net_port`
- optionally `last_net_name`

Read it to prefill the Multiplayer UI and/or `connect` command defaults.

### 6) MCP Server Bridge
Goal: allow tools/agents to execute console commands against a running instance.

Recommended shape:
- In-game: open a local-only control socket (Unix domain socket on macOS/Linux, TCP localhost fallback).
- Expose a tiny request/response protocol:
  - `{ "cmd": "sv_killall; map de_dust2", "origin": "mcp", "token": "...", "player": 0 }`
  - reply: `{ "ok": true, "lines": ["..."], "ts": ... }`
- MCP server process:
  - Implements MCP tools like `ivan_console.exec(cmd: string) -> {ok, lines}`
  - Connects to the local control socket.

Security notes:
- Local-only by default.
- Require an auth token stored in state file or printed on startup for dev use.
- Server-side permission gating still applies (MCP should not bypass admin checks).

## Risks
- **Architecture migration risk**: switching input to command-driven binds can break “basic control” easily.
- **Security/permission risk**: “console can do anything” must not imply “any client can do anything on server”.
- **Debug UX risk**: poor console UX will make this unused; needs fast history, completion, and clear errors.
- **Net divergence risk**: remote prediction beyond dead reckoning (full proxy sim) can create constant correction pops.
- **Protocol churn**: if map format changes, the handshake (`map_json`) should become a stable map reference
  (`map_hash`/bundle id). Doing console + map + net changes at once can balloon scope.

## Open Questions
- Do we want a single console overlay for both “admin tuning UI” and “command console”, or keep them separate?
- What is the minimum viable scripting feature set beyond basic commands/aliases/exec?
- What is the permission model for “every player has access to console”:
  - which commands are always local-only,
  - which are forwardable,
  - which require admin/config-owner,
  - do we want an `rcon`-like password?
- For remote prediction: do we stop at limited extrapolation, or do we replicate intent and run proxy sim?

