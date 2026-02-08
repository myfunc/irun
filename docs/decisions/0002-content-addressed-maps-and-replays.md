# ADR 0002: Content-Addressed Maps And Replays

Date: 2026-02-08

## Context
IRUN targets a time-trial / speedrun-oriented community. Runs must remain comparable over time even as maps evolve. We also want to avoid confusing "same map id, different geometry/rules" cases and enable basic integrity checks for uploaded artifacts.

## Decision
We will treat map builds and replays as content-addressed artifacts:
- Each shipped/runnable map build will have a `map_hash` computed as a cryptographic digest over:
  - baked collision + baked render payload (or baked chunk payloads), and
  - course rules that affect completion/timing (start/finish/checkpoints, etc),
  - and the format version(s) required to interpret the payload.
- Each replay will have a `replay_hash` computed as a cryptographic digest over the replay payload (and replay format version).
- Leaderboards and run submissions will key primarily by `map_hash` (with `map_id` as a human-friendly label).

## Status
Accepted (planned; not fully implemented).

## Consequences
- Map updates naturally create a new `map_hash`; prior leaderboard entries remain meaningful and can be kept per-hash.
- Replays can be quickly checked for corruption/tampering by recomputing `replay_hash`.
- Replays can be marked incompatible/out-of-date when `(map_id, map_hash)` does not match the currently selected map build.
- This does not, by itself, provide anti-cheat guarantees; it is an integrity and identity mechanism.

## Notes / Follow-Ups
- Choose a specific digest algorithm when implementing (e.g., SHA-256).
- Define canonical serialization rules for hashing (stable ordering, normalization, and file inclusion rules) to ensure consistent hashes across machines.
- Decide whether materials/resources are included in `map_hash` or whether `map_hash` is collision+rules only (tradeoff: visual-only changes vs strict identity).

