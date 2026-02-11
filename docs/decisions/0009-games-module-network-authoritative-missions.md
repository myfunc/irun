# ADR 0009: Games Module and Network-Authoritative Mission Sessions

## Status
Accepted

## Context

- Current race/time-trial behavior is implemented as a local mode plugin (`time_trial`) and does not support:
  - in-world mission authoring flow,
  - ordered multi-checkpoint races,
  - synchronized multiplayer countdown/start semantics,
  - reusable abstractions for additional mission types.
- Online play in IVAN is already movement-authoritative on the server, so mission/race outcomes must also be server-authoritative to avoid divergence.
- We need a scalable "games" layer to avoid putting editor/race/session logic directly into `RunnerDemo` and `MultiplayerServer`.

## Decision

- Introduce a dedicated `ivan.games` package with separated concerns:
  - `contracts`: shared definition/session/event data contracts,
  - `serialization`: `run.json` read/write and legacy conversion,
  - `editor`: in-world authoring workflow,
  - `runtime`: mission session state machine,
  - `race`: race-specific ordered-checkpoint rules,
  - marker/UI adapters for visuals and picker UX.
- Keep mission/race authority on the server in multiplayer sessions.
- Restrict mission authoring mutations to host/config-owner in multiplayer.
- Replicate game definitions/state/events to clients via versioned snapshot fields plus event sequence ids.
- Maintain backward compatibility for existing `time_trial` metadata by conversion into `games` definitions when needed.

## Consequences

- Adds a clear extension point for future mission types without rewriting core game loop code.
- Improves multiplayer correctness for race progression, countdown freeze, and timer start semantics.
- Introduces protocol and replication complexity that requires targeted tests and migration support.
- Requires input-action context routing to prevent key conflicts (`V`, `F`, `1/2/3` vs existing gameplay bindings).

## Follow-ups

- Implement phased rollout described in:
  - `docs/brainstorm/tech/2026-02-11_networked-games-module-editor-race-v1.md`
- Define and land protocol v2 fields for game interactions and replicated game events.
- Add unit/integration coverage for ordered checkpoint logic, countdown freeze, and multiplayer session flow.
