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
        "--map",
        dest="map_json",
        default=None,
        help="Path to a generated map JSON bundle to load (relative paths are resolved from the current working dir).",
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

    run(smoke=args.smoke, map_json=args.map_json, hl_root=args.hl_root, hl_mod=args.hl_mod)


if __name__ == "__main__":
    main()
