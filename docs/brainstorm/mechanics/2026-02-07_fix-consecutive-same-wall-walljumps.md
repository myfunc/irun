# Fix Consecutive Same-Wall Walljumps

## Problem
- Player can still chain walljumps on effectively the same wall by briefly losing contact and touching it again.
- This allows unintended vertical climbing and bypasses intended traversal limits.

## Goal
- Allow multiple walljumps in one airtime only when switching to a different wall.
- Disallow consecutive walljumps from the same wall plane.

## Proposed Direction
- Track last walljump wall identity using:
  - Wall normal
  - Contact point projected onto the wall plane
- On walljump attempt:
  - Reject if new wall normal is nearly the same as previous walljump normal and wall-plane distance is below threshold.
  - Accept otherwise.

## Notes
- Keep rule independent from grounded state (works fully in-air).
- Add test coverage for:
  - Block: same wall twice in a row
  - Allow: different wall after first walljump
  - Reset behavior if needed after landing

## Open Questions
- Plane similarity threshold tuning (`dot(normal_a, normal_b)` cutoff).
- Plane distance threshold to avoid false negatives on uneven geometry.
