from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False
    # Optional screenshot output path in smoke mode (offscreen render).
    # Useful for verifying map/material changes in CI or scripted checks.
    smoke_screenshot: str | None = None
    # Path to a generated map JSON bundle (see docs/skills/map-conversion/SKILL.md).
    # If None, the app falls back to the graybox scene (or optionally offers a map picker if --hl-root is set).
    map_json: str | None = None
    # Optional Half-Life install root. If set and --map is not provided, IVAN can show an in-game map picker.
    hl_root: str | None = None
    # Mod folder under hl_root to browse for maps (e.g. "valve", "cstrike").
    hl_mod: str = "valve"
