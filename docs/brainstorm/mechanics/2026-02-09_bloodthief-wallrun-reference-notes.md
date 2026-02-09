# Bloodthief Wallrun Reference Notes (2026-02-09)

## Purpose
Capture concrete Bloodthief wallrun cues and map them to IVAN's invariant-first movement rehaul.

## External observations (primary signals)
- Bloodthief patch notes repeatedly call out wallrun feel tuning:
  - wallrun no longer requires extra directional key constraints.
  - player falls slower while wallrunning.
  - player leans on walls (visual engagement signal), later tuned to feel faster/snappier.
  - wall detection and wall jump input buffering were later made more forgiving.
- Source references:
  - https://store.steampowered.com/news/app/2674720
  - https://store.steampowered.com/news/app/2533600
  - https://www.youtube.com/@Blargis3d

## Translation to IVAN design
- Keep wallrun controls permissive:
  - wall contact grace should be forgiving enough to avoid frequent drop-outs on uneven geometry.
- Keep wallrun vertical behavior timing-driven:
  - expose one wallrun sink timing invariant (`wallrun_sink_t90`) instead of multiple overlapping wallrun speed/gravity scalars.
  - derive wallrun sink target from existing jump invariants so jump/wallrun stay coupled by motion profile, not duplicated constants.
- Keep wallrun feedback obvious but read-only:
  - apply camera roll away from wall as a visual indicator only (no simulation coupling).
- Keep wall-jump responsiveness with existing leniency pipeline:
  - preserve buffered jump behavior during wallrun and hitstop via the same input buffering system.

## Resulting invariant policy
- Wallrun should add at most one independent movement slider unless a second axis is proven independent in tests.
- Prefer timing-based wallrun controls over raw velocity/gravity sliders.
- If a wallrun behavior can be derived from jump/run invariants, derive it rather than adding a new free scalar.
