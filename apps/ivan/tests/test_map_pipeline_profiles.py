"""Smoke-safe tests for map pipeline profile definitions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure tools/ is on path when running tests from apps/ivan.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def test_pipeline_profiles_constants() -> None:
    from pipeline_profiles import (
        PROFILE_CHOICES,
        PROFILE_DEV_FAST,
        PROFILE_PROD_BAKED,
    )

    assert PROFILE_DEV_FAST == "dev-fast"
    assert PROFILE_PROD_BAKED == "prod-baked"
    assert PROFILE_CHOICES == ("dev-fast", "prod-baked")


def test_add_profile_argument_parses_default() -> None:
    from pipeline_profiles import PROFILE_DEV_FAST, add_profile_argument, get_profile

    parser = argparse.ArgumentParser()
    add_profile_argument(parser)
    args = parser.parse_args([])
    assert get_profile(args) == PROFILE_DEV_FAST


def test_add_profile_argument_parses_prod_baked() -> None:
    from pipeline_profiles import PROFILE_PROD_BAKED, add_profile_argument, get_profile

    parser = argparse.ArgumentParser()
    add_profile_argument(parser)
    args = parser.parse_args(["--profile", "prod-baked"])
    assert get_profile(args) == PROFILE_PROD_BAKED
