from __future__ import annotations

import argparse

from baker.monorepo_paths import ensure_ivan_importable


def main(argv: list[str] | None = None) -> None:
    # Make `import ivan` work in the monorepo without an explicit install.
    ensure_ivan_importable()

    # Imports that depend on `ivan` must happen after `ensure_ivan_importable()`.
    from baker.app import run
    from baker.app_config import BakerRunConfig
    from ivan.maps.bundle_io import resolve_bundle_handle

    parser = argparse.ArgumentParser(
        prog="baker",
        description="IRUN Baker (mapperoni): map viewer skeleton (no baking yet).",
    )
    parser.add_argument(
        "--map",
        dest="map_json",
        default=None,
        help=(
            "Map bundle to load. Accepts:\n"
            "  - a path to map.json\n"
            "  - a path to a packed bundle (.irunmap)\n"
            "  - an alias under apps/ivan/assets/, e.g. imported/halflife/valve/datacore\n"
            "Relative paths are resolved from the current working dir first, then from apps/ivan/assets/."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run briefly and exit (for quick verification).",
    )
    parser.add_argument(
        "--smoke-screenshot",
        default=None,
        help="Optional PNG output path (only used with --smoke). Saves a single screenshot before exit.",
    )
    args = parser.parse_args(argv)

    chosen_map = str(args.map_json) if args.map_json else None
    if chosen_map is None:
        # Smoke-friendly default: prefer Crossfire, but fall back to known committed bundles.
        candidates = [
            "imported/halflife/valve/crossfire",
            "imported/halflife/valve/datacore",
            "imported/halflife/valve/surf_ski_4_2",
        ]
        for c in candidates:
            if resolve_bundle_handle(c) is not None:
                chosen_map = c
                break

    if chosen_map is None:
        parser.error("--map is required (no default bundle found)")

    cfg = BakerRunConfig(map_json=chosen_map, smoke=bool(args.smoke), smoke_screenshot=args.smoke_screenshot)
    run(cfg)


if __name__ == "__main__":
    main()
