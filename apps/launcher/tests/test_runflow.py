from pathlib import Path

import pytest

from launcher.runflow import LAUNCH_PRESET_IDS, AdvancedOverrides, resolve_launch_plan, resolve_preset


def test_fast_iterate_defaults_to_source_map_plan() -> None:
    preset = resolve_preset("fast-iterate")
    selected_map = Path("maps/demo/demo.map")

    plan = resolve_launch_plan(
        selected_map=selected_map,
        preset=preset,
        use_advanced=False,
    )

    assert plan.map_path.endswith("demo.map")
    assert plan.map_profile == "dev-fast"
    assert plan.watch is True
    assert plan.runtime_lighting is False


def test_runtime_visual_qa_defaults_to_runtime_lighting() -> None:
    preset = resolve_preset("runtime-visual-qa")
    selected_map = Path("maps/demo/qa.map")

    plan = resolve_launch_plan(
        selected_map=selected_map,
        preset=preset,
        use_advanced=False,
    )

    assert plan.runtime_lighting is True
    assert plan.watch is False


def test_play_with_options_uses_advanced_overrides() -> None:
    preset = resolve_preset("fast-iterate")
    selected_map = Path("maps/demo/demo.map")
    advanced = AdvancedOverrides(watch=False, runtime_lighting=True)

    plan = resolve_launch_plan(
        selected_map=selected_map,
        preset=preset,
        use_advanced=True,
        advanced=advanced,
    )

    assert plan.map_profile == "dev-fast"
    assert plan.watch is False
    assert plan.runtime_lighting is True


def test_launch_requires_selected_map() -> None:
    preset = resolve_preset("fast-iterate")

    with pytest.raises(ValueError):
        resolve_launch_plan(
            selected_map=None,
            preset=preset,
            use_advanced=False,
        )


def test_only_runtime_first_presets_are_available() -> None:
    assert LAUNCH_PRESET_IDS == ("fast-iterate", "runtime-visual-qa")
