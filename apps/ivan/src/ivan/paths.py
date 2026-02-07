from __future__ import annotations

from pathlib import Path

import ivan


def app_root() -> Path:
    """
    Return the IVAN app root directory: <repo>/apps/ivan.

    This is derived from the installed package location, so it stays correct even
    if the calling module lives in a deeper subpackage (e.g. ivan/world/...).
    """

    return Path(ivan.__file__).resolve().parents[2]

