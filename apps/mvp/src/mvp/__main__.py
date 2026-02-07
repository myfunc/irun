from __future__ import annotations

import argparse
from pathlib import Path

from mvp.game import run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mvp", description="MVP app runner (IRUN monorepo)")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run briefly and exit (for quick verification).",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path("mvp_settings.json"),
        help="Path to JSON settings file for gameplay tuning.",
    )
    args = parser.parse_args(argv)

    run(smoke=args.smoke, settings_path=args.settings)


if __name__ == "__main__":
    main()
