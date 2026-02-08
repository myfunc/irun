from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BakerRunConfig:
    map_json: str | None
    smoke: bool = False
    smoke_screenshot: str | None = None
