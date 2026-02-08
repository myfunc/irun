from __future__ import annotations

import argparse

from ivan.game import run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ivan", description="IVAN app runner (IRUN monorepo)")
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
    parser.add_argument(
        "--map",
        dest="map_json",
        default=None,
        help=(
            "Map bundle to load. Accepts:\n"
            "  - a path to map.json\n"
            "  - an alias under apps/ivan/assets/, e.g. imported/halflife/valve/bounce\n"
            "Relative paths are resolved from the current working dir first, then from apps/ivan/assets/."
        ),
    )
    parser.add_argument(
        "--hl-root",
        default=None,
        help='Optional Half-Life install root. If set (and --map is not), IVAN shows a map picker from "<hl-root>/<hl-mod>/maps".',
    )
    parser.add_argument(
        "--hl-mod",
        default="valve",
        help='Half-Life mod folder to browse (default: "valve"). Examples: valve, cstrike.',
    )
    args = parser.parse_args(argv)

    map_json = args.map_json
    run(
        smoke=args.smoke,
        smoke_screenshot=args.smoke_screenshot,
        map_json=map_json,
        hl_root=args.hl_root,
        hl_mod=args.hl_mod,
    )


if __name__ == "__main__":
    main()
