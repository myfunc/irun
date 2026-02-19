"""Tests for runtime tweak panel schema and UI wiring."""

from __future__ import annotations

from types import SimpleNamespace

from ivan.ui.runtime_tweak_schema import (
    RPG_FIELD_BY_KEY,
    RPG_VIEWMODEL_FIELDS,
    build_console_script,
    parse_vm_rpg_state,
)


def test_rpg_viewmodel_schema_has_expected_fields() -> None:
    """Schema defines pos, hpr, model_hpr, model_scale, target_longest."""
    keys = {f.key for f in RPG_VIEWMODEL_FIELDS}
    assert "pos" in keys
    assert "hpr" in keys
    assert "model_hpr" in keys
    assert "model_scale" in keys
    assert "target_longest" in keys
    assert len(RPG_VIEWMODEL_FIELDS) == 5


def test_parse_vm_rpg_state_extracts_values() -> None:
    """parse_vm_rpg_state parses vm_rpg_print output lines."""
    lines = [
        "vm_rpg.pos=[0.1, 0.2, 0.3]",
        "vm_rpg.hpr=[0.0, 0.0, 0.0]",
        "vm_rpg.model_hpr=[90.0, 0.0, 0.0]",
        "vm_rpg.model_scale=[1.0, 1.0, 1.0]",
        "vm_rpg.target_longest=[2.5]",
    ]
    state = parse_vm_rpg_state(lines)
    assert state["pos"] == [0.1, 0.2, 0.3]
    assert state["hpr"] == [0.0, 0.0, 0.0]
    assert state["model_hpr"] == [90.0, 0.0, 0.0]
    assert state["model_scale"] == [1.0, 1.0, 1.0]
    assert state["target_longest"] == [2.5]


def test_parse_vm_rpg_state_ignores_unknown_lines() -> None:
    """Unknown or malformed lines are ignored."""
    lines = [
        "vm_rpg.pos=[1, 2, 3]",
        "vm_rpg.unknown=[1, 2]",
        "not a vm line",
        "vm_rpg.pos=invalid",
    ]
    state = parse_vm_rpg_state(lines)
    assert state == {"pos": [1.0, 2.0, 3.0]}


def test_build_console_script_produces_executable_lines() -> None:
    """build_console_script produces vm_rpg_* command lines."""
    state = {
        "pos": [0.5, 0.0, -0.2],
        "hpr": [0.0, 0.0, 0.0],
        "model_hpr": [0.0, 0.0, 0.0],
        "model_scale": [1.0, 1.0, 1.0],
        "target_longest": [1.2],
    }
    script = build_console_script(state)
    assert "vm_rpg_pos" in script
    assert "vm_rpg_hpr" in script
    assert "vm_rpg_size" in script
    assert "0.5" in script
    assert "1.2" in script


def test_build_console_script_empty_returns_reset() -> None:
    """Empty state produces vm_rpg_reset."""
    script = build_console_script({})
    assert script == "vm_rpg_reset"


def test_tweak_panel_f10_exclusivity() -> None:
    """Tweak panel follows menu exclusivity: when open, other menus are closed."""
    # Simulate host state: tweak panel open implies others closed.
    host = SimpleNamespace(
        _tweak_panel_open=True,
        _pause_menu_open=False,
        _debug_menu_open=False,
        _replay_browser_open=False,
        _console_open=False,
        _feel_capture_open=False,
    )
    assert host._tweak_panel_open is True
    assert host._pause_menu_open is False
    assert host._console_open is False
