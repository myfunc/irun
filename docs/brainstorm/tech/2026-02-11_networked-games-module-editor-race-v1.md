# Proposal: Networked Games Module + In-World Editor (Race V1)

Date: 2026-02-11
Owner: codex

## Problem

Current race/time-trial logic is local-only and modeled as a single-mode plugin (`time_trial`) with just start/finish checkpoints.
It does not cover:
- in-world game editing flow,
- mission-circle interaction flow,
- ordered multi-checkpoint race logic,
- synchronized online countdown/start,
- reusable abstractions for future game types.

## Requested Product Behavior (V1)

- `V` toggles game editor mode.
- Entering editor mode enables noclip.
- In editor mode, `F` opens a UI kit menu with available game modes (currently only `race`).
- After selecting `race`, weapons are disabled and:
  - `1` places race start,
  - `2` appends checkpoint,
  - `3` places finish.
- Exiting editor mode with `V` publishes a mission marker (GTA-style ring) at the player's position captured at game-mode selection time.
- To start a race, players enter the mission marker and press `F`.
- If the same player presses `F` again, race participants are teleported to start and countdown begins.
- Countdown: short intro, `3..2..1..GO`, players frozen during countdown.
- Timer starts only when freeze ends (on `GO`).
- Players must pass checkpoints in placement order before finish is valid.
- Feedback:
  - checkpoint collected: yellow screen flash,
  - race finish: green screen flash,
  - race start: sound + visual notification.
- Works in multiplayer with multiple participants.

## Design Principles

- Server-authoritative race runtime for online correctness.
- Client-only visuals/HUD/audio derived from authoritative state/events.
- Host-owned editing permissions in multiplayer (avoid map griefing and conflict).
- Keep editor and race as generic "games" infrastructure, not hardcoded one-off race paths.
- Preserve backward compatibility with existing `time_trial` run metadata while migrating toward `games` definitions.

## Architecture Proposal

### New package: `ivan.games`

- `apps/ivan/src/ivan/games/contracts.py`
  - Dataclasses/protocol contracts:
    - `GameDefinition`,
    - `MissionMarker`,
    - `RaceCourse`,
    - `GameSessionState`,
    - `GamePlayerState`,
    - `GameEvent`.
- `apps/ivan/src/ivan/games/runtime.py`
  - Authoritative server runtime (definitions + active sessions + event sequencing).
- `apps/ivan/src/ivan/games/editor.py`
  - Client editor controller (input actions, draft placement, host sync commands).
- `apps/ivan/src/ivan/games/race.py`
  - Race-specific rules (ordered checkpoint progression, finish validation, timer semantics).
- `apps/ivan/src/ivan/games/serialization.py`
  - `run.json` read/write for `games` definitions and legacy compatibility.
- `apps/ivan/src/ivan/games/markers.py`
  - Marker rendering helpers (mission/start/checkpoint/finish rings).
- `apps/ivan/src/ivan/games/ui_mode_picker.py`
  - UI kit menu wrapper for game-mode selection.

### Runner integration

- `RunnerDemo` keeps orchestration only:
  - delegates editor lifecycle to `games.editor`,
  - delegates marker rendering to `games.markers`,
  - consumes authoritative session snapshot/events to drive HUD/FX/audio.

### Server integration

- `MultiplayerServer` owns authoritative `GamesRuntime`.
- Each tick:
  - apply input-driven interactions (`F` actions) to games runtime,
  - evaluate countdown/race progression using authoritative player transforms,
  - emit compact game events with sequence ids.

## Runtime Model

### Static definitions (map-authored)

- `GameDefinition`
  - `id`,
  - `type` (`race`),
  - `mission_marker` (cylinder),
  - `payload` (`RaceCourse` for race).
- `RaceCourse`
  - `start`,
  - `checkpoints[]` (ordered),
  - `finish`.

### Session state (authoritative)

- `status`: `idle | lobby | intro | countdown | running | finished`.
- `participants`: player ids currently enrolled.
- `ready_by_player`: readiness/start-intent bookkeeping.
- `countdown_started_at`, `race_started_at`, `race_finished_at`.
- Per-player race state:
  - `next_checkpoint_index`,
  - `started_at`,
  - `finished_at`,
  - `best_elapsed_ms` (session-local).

### Event stream (authoritative -> clients)

- `race_intro`,
- `race_countdown_tick` (`3`, `2`, `1`),
- `race_go`,
- `race_checkpoint_collected`,
- `race_finished`.

Events include monotonic `event_seq` so clients can apply each once.

## State Machines

### Editor flow (client)

- `off` -> `editing_freefly` (`V`).
- `editing_freefly` + `F` -> `mode_picker_open`.
- `mode_picker_open` + select race -> `race_draft`.
- `race_draft`:
  - `1` set start,
  - `2` append checkpoint,
  - `3` set finish.
- `race_draft` + `V` -> publish mission definition and return `off`.

### Race session flow (authoritative)

- `idle` -> `lobby` when first player presses `F` inside mission marker.
- `lobby` -> `intro` when starter presses `F` again (same player behavior requirement).
- `intro` -> `countdown` (players teleported to start, movement frozen).
- `countdown` -> `running` at `GO` (movement unlocked, timer starts).
- `running` -> `finished` when players satisfy ordered progression and cross finish.
- `finished` -> `idle` after result display timeout or explicit restart.

## Input/Action Plan

Introduce context-aware actions in input layer:

- `action_toggle_editor` (default `V`),
- `action_interact` (default `F`),
- `action_place_start` (`1`),
- `action_place_checkpoint` (`2`),
- `action_place_finish` (`3`).

Action routing depends on context:
- editor off: `F` means mission interaction (if inside marker), else no-op/fallback.
- editor on + picker hidden: `F` opens picker.
- editor on + race draft: `1/2/3` place markers, combat slot switching suppressed.

## Multiplayer Authority and Permissions

- Race runtime is server-authoritative.
- In multiplayer, editor publish/update is host/config-owner only.
- Non-owner `V` attempts show status message and do not mutate world definitions.
- Countdown freeze is authoritative:
  - movement commands ignored while frozen,
  - local camera look can remain enabled,
  - timer starts only after freeze release.

## Protocol Changes (Planned)

### Input packet additions

- Add `ip` (interact pressed edge).
- Keep old fields backward-compatible.

### Snapshot additions

- `games_v` (definitions version).
- `games` payload only when `games_v` changes (cacheable).
- `game_state` per active session (compact).
- `game_events` delta list with `event_seq`.

Protocol should bump from v1 to v2 once this lands.

## Persistence Format

Extend run metadata with `games` section:

```json
{
  "games": {
    "definitions": [
      {
        "id": "race_001",
        "type": "race",
        "mission_marker": { "center": [0, 0, 1], "radius": 3.0, "half_z": 2.0 },
        "payload": {
          "start": { "center": [10, 0, 1], "radius": 2.5, "half_z": 2.0 },
          "checkpoints": [
            { "center": [20, 5, 1], "radius": 2.5, "half_z": 2.0 }
          ],
          "finish": { "center": [35, -2, 1], "radius": 2.5, "half_z": 2.0 }
        }
      }
    ]
  }
}
```

Backward compatibility:
- if legacy `time_trial` `start_circle`/`finish_circle` exists and no `games.definitions`, synthesize a single race definition at load.

## Execution Plan

### Phase 0: Input and UI plumbing

- Add context-aware action flags to input command.
- Add UI kit game-mode picker (`race` only).
- Add editor toggle and noclip-forced editor state locally (single-player first).

### Phase 1: Authoring data model

- Implement `games.contracts` + `games.serialization`.
- Add run metadata read/write for `games.definitions`.
- Add host-local marker visualization for mission/start/checkpoint/finish.

### Phase 2: Local race runtime

- Implement local authoritative race state machine in client runtime.
- Add ordered checkpoint logic and finish validation.
- Add countdown freeze + timer-start-at-GO semantics.
- Add HUD/flash/audio event hooks.

### Phase 3: Server authoritative runtime

- Move race authority to `MultiplayerServer` `GamesRuntime`.
- Keep client as predicted/rendering mirror (no local race authority in net sessions).
- Add host-only editor publish RPC path.

### Phase 4: Protocol and replication

- Add `ip` to input packet.
- Add `games_v/games/game_state/game_events` snapshot replication.
- Add client event processing with sequence protection.

### Phase 5: Multiplayer gameplay hardening

- Validate multi-participant lobby/start/restart flows.
- Handle reconnect/spectator/non-owner edge cases.
- Add anti-spam cooldowns for `F` interactions.

### Phase 6: Migration and cleanup

- Bridge legacy `time_trial` configs to `games` definitions.
- Keep mode alias compatibility (`race` -> games race definition) for existing content.

## Test Strategy

- Unit:
  - ordered checkpoint progression,
  - finish rejection when checkpoints skipped,
  - timer start exactly on `GO`.
- Serialization:
  - round-trip `games` definitions in `run.json`,
  - legacy `time_trial` conversion path.
- Net protocol:
  - v2 snapshot encode/decode with optional `games` payload.
- Integration:
  - host starts race with two clients,
  - repeated `F` restart behavior,
  - freeze enforcement during countdown.

## Risks and Mitigations

- Key binding conflicts (`F` demo save, number keys weapon slots):
  - mitigate with action-context layer and explicit suppression in editor/race draft context.
- Snapshot payload growth:
  - mitigate with versioned `games` payload (`games_v`) and event deltas.
- Editor griefing in multiplayer:
  - mitigate with host-only mutation authority.
- Divergence between local and multiplayer behavior:
  - mitigate by keeping one authoritative race runtime implementation reused by server and local offline host path.

