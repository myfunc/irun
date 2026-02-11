from pathlib import Path

import pytest

from launcher.runflow import (
    DEFAULT_MAP_PROFILE,
    DEFAULT_RUNTIME_LIGHTING,
    DEFAULT_WATCH,
    AdvancedOverrides,
    resolve_launch_plan,
    sanitize_pack_profile,
)


def test_default_runtime_plan_uses_selected_source_map() -> None:
    selected_map = Path("maps/demo/demo.map")

    plan = resolve_launch_plan(
        selected_map=selected_map,
        use_advanced=False,
    )

    assert plan.map_path.endswith("demo.map")
    assert plan.map_profile == DEFAULT_MAP_PROFILE
    assert plan.watch is DEFAULT_WATCH
    assert plan.runtime_lighting is DEFAULT_RUNTIME_LIGHTING


def test_launch_with_options_applies_runtime_overrides() -> None:
    selected_map = Path("maps/demo/demo.map")
    advanced = AdvancedOverrides(watch=False, runtime_lighting=True)

    plan = resolve_launch_plan(
        selected_map=selected_map,
        use_advanced=True,
        advanced=advanced,
    )

    assert plan.map_profile == DEFAULT_MAP_PROFILE
    assert plan.watch is False
    assert plan.runtime_lighting is True


def test_launch_requires_selected_map() -> None:
    with pytest.raises(ValueError):
        resolve_launch_plan(
            selected_map=None,
            use_advanced=False,
        )


def test_pack_profile_is_fixed_to_dev_fast() -> None:
    assert sanitize_pack_profile("dev-fast") == "dev-fast"
    assert sanitize_pack_profile("prod-baked") == "dev-fast"
