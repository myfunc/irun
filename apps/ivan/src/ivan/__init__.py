from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["__version__"]

__version__ = "0.1.0"


def _ensure_local_ui_kit_importable() -> None:
    try:
        import irun_ui_kit  # noqa: F401

        return
    except Exception:
        pass

    # Monorepo fallback for environments where local path dependency was not installed.
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "ui_kit" / "src",  # monorepo: apps/ui_kit/src
        here.parents[4] / "apps" / "ui_kit" / "src",  # defensive fallback
    ]
    for ui_kit_src in candidates:
        if ui_kit_src.is_dir():
            p = str(ui_kit_src)
            if p not in sys.path:
                sys.path.insert(0, p)
            break


_ensure_local_ui_kit_importable()
