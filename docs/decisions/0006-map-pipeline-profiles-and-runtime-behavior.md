# ADR 0006: Map Pipeline Profiles and Runtime Behavior

Date: 2026-02-10

## Status

Accepted (implemented).

## Context

Map workflows span fast local iteration (TrenchBroom → save → run) and production distribution (baked lightmaps, packed archives). Unifying both led to:

- Bake pipeline: vis and light stages are expensive; devs often only need quick geometry validation.
- Pack pipeline: compression adds latency; fast iteration prefers uncompressed archives.
- Runtime: fog and visibility culling behave differently for dev vs prod content; wrong defaults cause confusion.

## Decision

Introduce **map pipeline profiles** shared by build tools and runtime:

### Profiles

| Profile | Purpose | Bake (vis/light) | Pack (compression) |
|---------|---------|------------------|--------------------|
| `dev-fast` | Fast iteration | Skip (default) | Off (level 0) |
| `prod-baked` | Production quality | Run both | On (level 6) |

- `bake_map.py` and `pack_map.py` accept `--profile`; default `dev-fast`.
- `bake_map.py`: when `--no-vis` / `--no-light` not explicitly set, dev-fast skips both.
- `pack_map.py`: dev-fast uses `compresslevel=0`; prod-baked uses `compresslevel=6`.

### Runtime Map Profile

Runtime `--map-profile` chooses `auto` | `dev-fast` | `prod-baked`:

- **auto** (default): Infer from path — `.map` file or directory bundle → `dev-fast`; `.irunmap` → `prod-baked`.
- **dev-fast**: Fog off unless `run.json` enables; visibility culling off (permissive).
- **prod-baked**: Fog from `run.json` or conservative defaults (start 80, end 200); visibility can enable via `run.json`.

### Primary Authoring Flow

1. Edit `.map` in TrenchBroom → direct load in Ivan (no pack/bake required).
2. Optional pack or bake with `--profile dev-fast` for quick `.irunmap` output.
3. Production: `bake_map.py --profile prod-baked` or `pack_map.py --profile prod-baked` for full-quality distribution.

### Debug HUD (F12)

Compact F12-driven overlay with mode cycle:

| Mode | Purpose |
|------|---------|
| minimal | FPS + frame time (ms) |
| render | FPS, frame time, p95, sim steps/hz |
| streaming | FPS, p95, network perf |
| graph | FPS, spike count, mini frametime bar graph |

Cycle: off → minimal → render → streaming → graph → off. Top-right placement to avoid HUD overlap.

## Consequences

- Devs get fast edit-run loops without paying for vis/light or compression.
- Production builds get predictable full-quality output.
- Runtime defaults match content type; explicit `--map-profile` overrides inference when needed.
- Debug HUD (F12) provides compact frametime/net perf overlay orthogonal to profile behavior.

## Related

- ADR 0004: Packed Map Bundles (.irunmap)
- `docs/architecture.md`: Map Pipeline, Runtime Map Profile, Debug HUD
