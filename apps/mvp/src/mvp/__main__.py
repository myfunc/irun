from __future__ import annotations

import argparse

from mvp.game import run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mvp", description="MVP app runner (IRUN monorepo)")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run briefly and exit (for quick verification).",
    )
    args = parser.parse_args(argv)

    run(smoke=args.smoke)


if __name__ == "__main__":
    main()
