"""Shared map pipeline profile definitions for pack_map and bake_map.

Profiles control trade-offs between fast local iteration and production quality:
- dev-fast: Skip expensive steps; output runtime-consumable artifacts without mandatory .irunmap pack.
- prod-baked: Full bake/pack quality flow.
"""

from __future__ import annotations

import argparse

PROFILE_DEV_FAST = "dev-fast"
PROFILE_PROD_BAKED = "prod-baked"

PROFILE_CHOICES = (PROFILE_DEV_FAST, PROFILE_PROD_BAKED)


def add_profile_argument(
    parser: argparse.ArgumentParser,
    *,
    default: str = PROFILE_DEV_FAST,
) -> None:
    """Add --profile argument to an ArgumentParser."""
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=default,
        help=(
            "Pipeline profile: dev-fast (skip expensive steps, fast iteration) or "
            "prod-baked (full quality). Default: dev-fast."
        ),
    )


def get_profile(args: argparse.Namespace) -> str:
    """Return the effective profile from parsed args."""
    return getattr(args, "profile", PROFILE_DEV_FAST)
