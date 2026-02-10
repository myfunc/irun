"""Entry point: python -m launcher"""

from __future__ import annotations

import sys

from launcher.app import run_launcher


def main() -> None:
    print(f"[LAUNCHER] python: {sys.executable}")
    run_launcher()


if __name__ == "__main__":
    main()
