from __future__ import annotations

import argparse
import os
import sys

from ivan.game import run
from ivan.net import run_server


def main(argv: list[str] | None = None) -> None:
    # Startup diagnostic — visible in launcher log.
    print(f"[IVAN] python: {sys.executable}")
    print(f"[IVAN] ivan pkg: {os.path.dirname(os.path.abspath(__file__))}")
    default_port = int(os.environ.get("DEFAULT_HOST_PORT", "7777"))
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
            "Map to load. Accepts:\n"
            "  - a path to map.json\n"
            "  - a path to a packed bundle (.irunmap)\n"
            "  - a path to a .map file (TrenchBroom, loaded directly)\n"
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
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch .map file for changes and auto-reload (TrenchBroom workflow).",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run as dedicated multiplayer server.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Server bind host (server mode) or remote host (client mode with --connect).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help="Multiplayer TCP bootstrap port (UDP uses port+1).",
    )
    parser.add_argument(
        "--connect",
        default=None,
        help="Connect to multiplayer host (client mode). Example: --connect 127.0.0.1",
    )
    parser.add_argument(
        "--name",
        default="player",
        help="Multiplayer player name.",
    )
    args = parser.parse_args(argv)

    if args.server:
        run_server(
            host=args.host,
            tcp_port=int(args.port),
            udp_port=int(args.port) + 1,
            map_json=args.map_json,
        )
        return

    map_json = args.map_json
    run(
        smoke=args.smoke,
        smoke_screenshot=args.smoke_screenshot,
        map_json=map_json,
        hl_root=args.hl_root,
        hl_mod=args.hl_mod,
        net_host=args.connect,
        net_port=int(args.port),
        net_name=args.name,
        watch=args.watch,
    )


if __name__ == "__main__":
    main()
