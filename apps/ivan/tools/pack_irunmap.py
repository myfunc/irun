from __future__ import annotations

import argparse
from pathlib import Path

from ivan.maps.bundle_io import PACKED_BUNDLE_EXT, pack_bundle_dir_to_irunmap


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack an IVAN directory bundle into a single .irunmap archive.")
    parser.add_argument("--input", required=True, help="Bundle directory or a path to <bundle>/map.json.")
    parser.add_argument("--output", required=True, help="Output .irunmap path.")
    parser.add_argument("--compresslevel", type=int, default=1, help="ZIP deflate compression level (default: 1).")
    args = parser.parse_args()

    inp = Path(args.input)
    if inp.is_dir():
        bundle_dir = inp
    else:
        bundle_dir = inp.parent

    out = Path(args.output)
    if out.suffix.lower() != PACKED_BUNDLE_EXT:
        raise SystemExit(f"--output must end with {PACKED_BUNDLE_EXT}: {out}")

    pack_bundle_dir_to_irunmap(bundle_dir=bundle_dir, out_path=out, compresslevel=int(args.compresslevel))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

