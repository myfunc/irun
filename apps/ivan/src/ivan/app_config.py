from __future__ import annotations

from dataclasses import dataclass


# Map pipeline profile: dev-fast = .map/directory, no bake; prod-baked = packed with lightmaps.
MAP_PROFILE_DEV_FAST = "dev-fast"
MAP_PROFILE_PROD_BAKED = "prod-baked"
MAP_PROFILE_AUTO = "auto"


@dataclass(frozen=True)
class RunConfig:
    smoke: bool = False
    # Boot directly into the deterministic movement feel harness map.
    feel_harness: bool = False
    # Optional screenshot output path in smoke mode (offscreen render).
    # Useful for verifying map/material changes in CI or scripted checks.
    smoke_screenshot: str | None = None
    # Path to a generated map JSON bundle (see docs/skills/map-conversion/SKILL.md).
    # If None, the app falls back to the graybox scene (or optionally offers a map picker if --hl-root is set).
    map_json: str | None = None
    # Map pipeline profile: "dev-fast" | "prod-baked" | "auto". Affects lighting fallback, fog, visibility.
    # Dev-fast: unlit when baked data absent; permissive culling; fog off by default.
    # Prod-baked: preserve baked lightmaps; stricter culling; fog configurable.
    map_profile: str = MAP_PROFILE_AUTO
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
    # Optional distance fog: {"enabled": bool, "start": float, "end": float, "color": [r,g,b]}.
    # If None, falls back to run.json "fog", else profile defaults (dev: off, prod: conservative).
    fog: dict | None = None
    # Multiplayer: connect to authoritative server host (client mode).
    net_host: str | None = None
    # Multiplayer TCP bootstrap port (UDP gameplay uses tcp_port + 1 by default).
    net_port: int = 7777
    # Multiplayer display/player name.
    net_name: str = "player"
    # Watch .map file for changes and auto-reload (TrenchBroom workflow).
    watch: bool = False