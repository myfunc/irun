from __future__ import annotations

import sys
from pathlib import Path


def ensure_ivan_importable() -> None:
    """Best-effort monorepo convenience.

    Baker reuses Ivan's renderer/scene code for WYSIWYG preview. In this repo layout
    we can import `ivan` directly from source without requiring a separate install.

    This is intentionally best-effort: it is fine to do nothing if the repo layout
    is different (e.g. packaged distribution later).
    """

    try:
        here = Path(__file__).resolve()
        # /.../irun/apps/baker/src/baker/monorepo_paths.py
        repo_root = here.parents[4]
        ivan_src = repo_root / "apps" / "ivan" / "src"
        if ivan_src.exists() and ivan_src.is_dir():
            p = str(ivan_src)
            if p not in sys.path:
                sys.path.insert(0, p)
    except Exception:
        return
