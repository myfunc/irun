from __future__ import annotations

"""
IVAN game app wiring.

This package intentionally exposes the same public API as the historical `ivan.game` module:
- `RunnerDemo`: Panda3D ShowBase application.
- `run(...)`: convenience entrypoint used by `python -m ivan`.
"""

# Compatibility re-exports:
# Historically `ivan.game` was a single module, and some tests monkeypatch symbols
# on that module (e.g. `EmbeddedHostServer`, `time.sleep`). Keep those stable.
import time as time

from ivan.net import EmbeddedHostServer

from .app import RunnerDemo, run

__all__ = ["RunnerDemo", "run", "EmbeddedHostServer", "time"]
