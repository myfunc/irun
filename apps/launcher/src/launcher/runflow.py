"""Single runtime-first launch plan for the launcher."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
PACK_PROFILES = ("dev-fast",)
DEFAULT_MAP_PROFILE = "dev-fast"
DEFAULT_WATCH = True
DEFAULT_RUNTIME_LIGHTING = True


@dataclass(frozen=True)
class AdvancedOverrides:
    """Optional advanced overrides applied by launcher options."""

    watch: bool
    runtime_lighting: bool


@dataclass(frozen=True)
class ResolvedLaunchPlan:
    """Runtime-first launch plan resolved from selected map + overrides."""

    map_path: str
    map_profile: str
    watch: bool
    runtime_lighting: bool


def sanitize_pack_profile(raw: str, *, default: str = "dev-fast") -> str:
    value = (raw or "").strip()
    if value in PACK_PROFILES:
        return value
    return default


def resolve_launch_plan(
    *,
    selected_map: Path | None,
    assigned_pack: Path | None = None,
    use_advanced: bool = True,
    advanced: AdvancedOverrides | None = None,
) -> ResolvedLaunchPlan:
    """Resolve launch plan from selected map and optional assigned pack.

    When assigned_pack is set and valid, launch uses the pack (.irunmap) path.
    Otherwise launch uses the source .map path.
    """
    if selected_map is None:
        raise ValueError("Select a .map file before launching.")

    # Prefer pack when assigned and exists
    launch_path = assigned_pack if (assigned_pack and assigned_pack.is_file()) else selected_map

    watch = DEFAULT_WATCH
    runtime_lighting = DEFAULT_RUNTIME_LIGHTING

    if use_advanced and advanced is not None:
        watch = bool(advanced.watch)
        runtime_lighting = bool(advanced.runtime_lighting)

    return ResolvedLaunchPlan(
        map_path=str(launch_path),
        map_profile=DEFAULT_MAP_PROFILE,
        watch=watch,
        runtime_lighting=runtime_lighting,
    )
