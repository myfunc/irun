from __future__ import annotations

import argparse
import os
from pathlib import Path

from ivan.game import run
from ivan.net import run_server
from ivan.replays.compare import compare_latest_replays
from ivan.replays.determinism_verify import verify_latest_replay_determinism, verify_replay_determinism
from ivan.replays.telemetry import export_latest_replay_telemetry


def main(argv: list[str] | None = None) -> None:
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
        "--feel-harness",
        action="store_true",
        help="Boot directly into the deterministic movement feel harness scene.",
    )
    parser.add_argument(
        "--map",
        dest="map_json",
        default=None,
        help=(
            "Map bundle to load. Accepts:\n"
            "  - a path to map.json\n"
            "  - a path to a packed bundle (.irunmap)\n"
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
    parser.add_argument(
        "--export-latest-replay-telemetry",
        action="store_true",
        help="Export telemetry (CSV + JSON summary) for the latest replay and exit.",
    )
    parser.add_argument(
        "--replay-telemetry-out",
        default=None,
        help="Optional output directory for replay telemetry exports.",
    )
    parser.add_argument(
        "--compare-latest-replays",
        action="store_true",
        help="Auto-export latest+previous replay telemetry and write a comparison summary, then exit.",
    )
    parser.add_argument(
        "--replay-route-tag",
        default=None,
        help="Optional route tag (A/B/C) attached to replay compare output.",
    )
    parser.add_argument(
        "--verify-latest-replay-determinism",
        action="store_true",
        help="Replay the latest demo input N times in offline sim and report determinism stability, then exit.",
    )
    parser.add_argument(
        "--verify-replay-determinism",
        default=None,
        help="Replay a specific demo input N times in offline sim and report determinism stability, then exit.",
    )
    parser.add_argument(
        "--determinism-runs",
        type=int,
        default=5,
        help="Number of repeated offline replay simulations used for determinism verification (default: 5).",
    )
    args = parser.parse_args(argv)

    if args.export_latest_replay_telemetry:
        out_dir = Path(args.replay_telemetry_out) if args.replay_telemetry_out else None
        result = export_latest_replay_telemetry(out_dir=out_dir)
        print(f"source: {result.source_demo}")
        print(f"csv: {result.csv_path}")
        print(f"summary: {result.summary_path}")
        print(f"ticks: {result.tick_count} (telemetry: {result.telemetry_tick_count})")
        return

    if args.compare_latest_replays:
        out_dir = Path(args.replay_telemetry_out) if args.replay_telemetry_out else None
        result = compare_latest_replays(out_dir=out_dir, route_tag=args.replay_route_tag)
        print(f"latest: {result.latest_export.source_demo}")
        print(f"reference: {result.reference_export.source_demo}")
        print(f"comparison: {result.comparison_path}")
        print(f"result: +{result.improved_count} / -{result.regressed_count} / ={result.equal_count}")
        return

    if args.verify_latest_replay_determinism:
        out_dir = Path(args.replay_telemetry_out) if args.replay_telemetry_out else None
        result = verify_latest_replay_determinism(runs=int(args.determinism_runs), out_dir=out_dir)
        print(f"source: {result.source_demo}")
        print(f"report: {result.report_path}")
        print(f"runs: {result.runs} ticks: {result.tick_count}")
        print(
            f"stable: {result.stable} divergence_runs: {result.divergence_runs} "
            f"recorded_hash_mismatches: {result.recorded_hash_mismatches}/{result.recorded_hash_checked}"
        )
        return

    if args.verify_replay_determinism:
        out_dir = Path(args.replay_telemetry_out) if args.replay_telemetry_out else None
        result = verify_replay_determinism(
            replay_path=Path(args.verify_replay_determinism),
            runs=int(args.determinism_runs),
            out_dir=out_dir,
        )
        print(f"source: {result.source_demo}")
        print(f"report: {result.report_path}")
        print(f"runs: {result.runs} ticks: {result.tick_count}")
        print(
            f"stable: {result.stable} divergence_runs: {result.divergence_runs} "
            f"recorded_hash_mismatches: {result.recorded_hash_mismatches}/{result.recorded_hash_checked}"
        )
        return

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
        feel_harness=args.feel_harness,
        map_json=map_json,
        hl_root=args.hl_root,
        hl_mod=args.hl_mod,
        net_host=args.connect,
        net_port=int(args.port),
        net_name=args.name,
    )


if __name__ == "__main__":
    main()
