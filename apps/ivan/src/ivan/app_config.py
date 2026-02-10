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
    # Optional lighting override for this run (e.g. picked from the main menu).
    # If None, the map falls back to bundle run.json "lighting" (if present), then map.json defaults.
    lighting: dict | None = None
    # Optional visibility/culling configuration for this run.
    # If None, the map falls back to bundle run.json "visibility" (if present), else defaults.
    visibility: dict | None = None
    # Multiplayer: connect to authoritative server host (client mode).
    net_host: str | None = None
    # Multiplayer TCP bootstrap port (UDP gameplay uses tcp_port + 1 by default).
    net_port: int = 7777
    # Multiplayer display/player name.
    net_name: str = "player"
    # Watch .map file for changes and auto-reload (TrenchBroom workflow).
    watch: bool = False