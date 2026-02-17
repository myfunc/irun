from __future__ import annotations

import importlib
from typing import Any

from ivan.modes.free_run import FreeRunMode
from ivan.modes.time_trial import TimeTrialMode


def load_mode(*, mode: str, config: dict | None) -> Any:
    """
    Load a game mode.

    Supported values:
    - Built-in ids: "free_run", "time_trial" (alias: "race")
    - Python class path: "some.module:ClassName" (instantiated with config=...)
    """

    mode = str(mode or "").strip() or "free_run"
    if mode == "free_run":
        return FreeRunMode(config=config)
    if mode in {"time_trial", "race"}:
        return TimeTrialMode(config=config)

    if ":" in mode:
        mod_name, cls_name = mode.split(":", 1)
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name, None)
        if cls is None:
            raise RuntimeError(f"Mode class not found: {mode}")
        return cls(config=config)

    raise RuntimeError(f"Unknown mode: {mode}")
