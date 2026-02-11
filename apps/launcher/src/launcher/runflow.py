"""Runflow presets and option resolution for the launcher."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PACK_PROFILES = ("dev-fast", "prod-baked")

PresetId = Literal["fast-iterate", "runtime-visual-qa"]


@dataclass(frozen=True)
class LaunchPreset:
    """Named launch profile used by the guided runflow."""

    preset_id: PresetId
    label: str
    description: str
    map_profile: str
    watch: bool
    runtime_lighting: bool
    pack_profile: str


@dataclass(frozen=True)
class AdvancedOverrides:
    """Optional advanced overrides applied by launcher options."""

    watch: bool
    runtime_lighting: bool


@dataclass(frozen=True)
class ResolvedLaunchPlan:
    """Fully resolved launch plan derived from preset + overrides."""

    map_path: str
    map_profile: str
    watch: bool
    runtime_lighting: bool


LAUNCH_PRESETS: tuple[LaunchPreset, ...] = (
    LaunchPreset(
        preset_id="fast-iterate",
        label="Fast Iterate",
        description="Source .map with auto-reload and fast dev profile.",
        map_profile="dev-fast",
        watch=True,
        runtime_lighting=False,
        pack_profile="dev-fast",
    ),
    LaunchPreset(
        preset_id="runtime-visual-qa",
        label="Runtime Visual QA",
        description="Source .map with runtime lighting for quick visual checks.",
        map_profile="dev-fast",
        watch=False,
        runtime_lighting=True,
        pack_profile="dev-fast",
    ),
)

LAUNCH_PRESET_IDS: tuple[PresetId, ...] = tuple(p.preset_id for p in LAUNCH_PRESETS)


def sanitize_pipeline_profile(raw: str, *, default: str) -> str:
    value = (raw or "").strip()
    if value in PACK_PROFILES:
        return value
    return default


def resolve_preset(preset_id: str) -> LaunchPreset:
    for preset in LAUNCH_PRESETS:
        if preset.preset_id == preset_id:
            return preset
    return LAUNCH_PRESETS[0]


def resolve_launch_plan(
    *,
    selected_map: Path | None,
    preset: LaunchPreset,
    use_advanced: bool,
    advanced: AdvancedOverrides | None = None,
) -> ResolvedLaunchPlan:
    if selected_map is None:
        raise ValueError("Select a .map file before launching.")

    map_path = str(selected_map)
    watch = preset.watch
    map_profile = preset.map_profile
    runtime_lighting = preset.runtime_lighting

    if use_advanced and advanced is not None:
        watch = bool(advanced.watch)
        runtime_lighting = bool(advanced.runtime_lighting)

    return ResolvedLaunchPlan(
        map_path=map_path,
        map_profile=sanitize_pipeline_profile(map_profile, default=preset.map_profile),
        watch=watch,
        runtime_lighting=runtime_lighting,
    )
