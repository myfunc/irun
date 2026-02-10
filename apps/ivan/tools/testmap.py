#!/usr/bin/env python3
"""Quick-test script for IVAN .map files with auto-reload on save.

Launches ``python -m ivan --map <path>`` as a subprocess, watches the .map
file for changes (mtime polling), and restarts the game on save.  Optionally
talks to the in-game console bridge to request a hot-reload instead of a full
restart (once the ``map_reload`` console command is implemented).

Usage::

    # Basic: launch game with a .map file, auto-reload on save
    python tools/testmap.py path/to/mymap.map

    # With bake step (slower, but with lighting)
    python tools/testmap.py path/to/mymap.map --bake --ericw-tools /path/to/ericw

    # Just convert without launching (useful for CI/testing)
    python tools/testmap.py path/to/mymap.map --convert-only --output mymap.irunmap
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PREFIX = "[testmap]"

# Console bridge defaults (matches ConsoleControlServer in ivan.console.control_server).
_DEFAULT_CONSOLE_PORT = 7779
_CONSOLE_PORT_ENV = "IRUN_IVAN_CONSOLE_PORT"

# Reload command to send via the console bridge.
# NOTE: ``map_reload`` does not exist in the game yet.  The console bridge
# attempt will therefore fail and the script falls back to kill + restart.
_RELOAD_PAYLOAD = json.dumps(
    {"line": "map_reload", "role": "client", "origin": "testmap"},
    ensure_ascii=True,
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Script lives at  apps/ivan/tools/testmap.py
_SCRIPT_DIR = Path(__file__).resolve().parent
_IVAN_DIR = _SCRIPT_DIR.parent  # apps/ivan


# ---------------------------------------------------------------------------
# Console bridge helpers
# ---------------------------------------------------------------------------


def _console_port() -> int:
    """Return the console bridge TCP port."""
    raw = os.environ.get(_CONSOLE_PORT_ENV)
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            pass
    return _DEFAULT_CONSOLE_PORT


def _try_console_reload() -> bool:
    """Attempt to send a ``map_reload`` command via the console bridge.

    Returns ``True`` if the bridge accepted the command, ``False`` otherwise
    (connection refused, timeout, unknown command, etc.).
    """
    port = _console_port()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.sendall((_RELOAD_PAYLOAD + "\n").encode("utf-8"))
            # Read response (single JSON line).
            sock.settimeout(3.0)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            if not buf:
                return False
            resp = json.loads(buf.split(b"\n", 1)[0].decode("utf-8", errors="ignore"))
            if isinstance(resp, dict) and resp.get("ok"):
                # Check if the command actually produced an error message.
                out = resp.get("out", [])
                for line in out:
                    if "unknown" in str(line).lower():
                        return False
                return True
            return False
    except (OSError, json.JSONDecodeError, ValueError, KeyError):
        return False


# ---------------------------------------------------------------------------
# Process management helpers
# ---------------------------------------------------------------------------


def _launch_game(
    map_path: Path,
    *,
    scale: float,
    extra_args: list[str] | None = None,
) -> subprocess.Popen[bytes]:
    """Start ``python -m ivan --map <map_path>`` and return the Popen handle."""
    cmd: list[str] = [
        sys.executable, "-m", "ivan",
        "--map", str(map_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    print(f"{_PREFIX} Launching: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=str(_IVAN_DIR))


def _terminate(proc: subprocess.Popen[bytes], *, timeout: float = 5.0) -> None:
    """Gracefully terminate *proc*, falling back to kill."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------------------
# Convert-only mode
# ---------------------------------------------------------------------------


def _convert_and_exit(
    *,
    map_path: Path,
    output: str | None,
    scale: float,
    bake: bool,
    ericw_tools: str | None,
) -> None:
    """Convert the .map file to .irunmap (via pack_map or bake_map) and exit."""
    if output is None:
        output = str(map_path.with_suffix(".irunmap"))

    if bake:
        if ericw_tools is None:
            print(f"{_PREFIX} Error: --bake requires --ericw-tools <dir>", file=sys.stderr)
            sys.exit(1)
        bake_script = _SCRIPT_DIR / "bake_map.py"
        if not bake_script.is_file():
            print(f"{_PREFIX} Error: bake_map.py not found at {bake_script}", file=sys.stderr)
            sys.exit(1)
        cmd: list[str] = [
            sys.executable, str(bake_script),
            "--map", str(map_path),
            "--output", output,
            "--ericw-tools", ericw_tools,
            "--game-root", str(map_path.parent),
            "--scale", str(scale),
        ]
    else:
        pack_script = _SCRIPT_DIR / "pack_map.py"
        if not pack_script.is_file():
            print(f"{_PREFIX} Error: pack_map.py not found at {pack_script}", file=sys.stderr)
            sys.exit(1)
        cmd = [
            sys.executable, str(pack_script),
            "--map", str(map_path),
            "--output", output,
            "--scale", str(scale),
        ]

    print(f"{_PREFIX} Converting: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Watch + run loop
# ---------------------------------------------------------------------------


def _run_with_watch(
    *,
    map_path: Path,
    scale: float,
    watch: bool,
    poll_interval: float,
    bake: bool,
    ericw_tools: str | None,
) -> None:
    """Launch IVAN and optionally watch for .map changes."""
    # When --bake is specified, convert first, then launch the baked bundle.
    launch_path: Path = map_path
    if bake:
        if ericw_tools is None:
            print(f"{_PREFIX} Error: --bake requires --ericw-tools <dir>", file=sys.stderr)
            sys.exit(1)
        baked = map_path.with_suffix(".irunmap")
        bake_script = _SCRIPT_DIR / "bake_map.py"
        if not bake_script.is_file():
            print(f"{_PREFIX} Error: bake_map.py not found at {bake_script}", file=sys.stderr)
            sys.exit(1)
        print(f"{_PREFIX} Baking {map_path.name} ...")
        bake_cmd: list[str] = [
            sys.executable, str(bake_script),
            "--map", str(map_path),
            "--output", str(baked),
            "--ericw-tools", ericw_tools,
            "--game-root", str(map_path.parent),
            "--scale", str(scale),
        ]
        result = subprocess.run(bake_cmd)
        if result.returncode != 0:
            print(f"{_PREFIX} Bake failed (exit {result.returncode})", file=sys.stderr)
            sys.exit(result.returncode)
        launch_path = baked

    proc = _launch_game(launch_path, scale=scale)
    last_mtime = map_path.stat().st_mtime

    if not watch:
        try:
            proc.wait()
        except KeyboardInterrupt:
            _terminate(proc)
        return

    print(f"{_PREFIX} Watching {map_path.name} for changes (poll every {poll_interval}s)")
    print(f"{_PREFIX} Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(poll_interval)

            # Check if the game exited on its own.
            if proc.poll() is not None:
                print(f"{_PREFIX} Game exited (code {proc.returncode})")
                break

            # Check for file changes.
            try:
                current_mtime = map_path.stat().st_mtime
            except OSError:
                continue

            if current_mtime == last_mtime:
                continue

            last_mtime = current_mtime
            print(f"{_PREFIX} Change detected in {map_path.name}")

            # If --bake, re-bake first.
            if bake:
                print(f"{_PREFIX} Re-baking ...")
                result = subprocess.run(bake_cmd)
                if result.returncode != 0:
                    print(f"{_PREFIX} Bake failed (exit {result.returncode}); skipping reload")
                    continue

            # Try a hot reload via the console bridge.
            if _try_console_reload():
                print(f"{_PREFIX} Reloaded via console bridge")
                continue

            # Fallback: kill and restart.
            print(f"{_PREFIX} Restarting game process ...")
            _terminate(proc)
            time.sleep(0.5)  # Brief pause to release resources.
            proc = _launch_game(launch_path, scale=scale)

    except KeyboardInterrupt:
        print(f"\n{_PREFIX} Shutting down ...")
        _terminate(proc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testmap",
        description="Launch IVAN with a .map file and auto-reload on save.",
    )
    parser.add_argument(
        "map_file",
        help="Path to the .map file.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.03,
        help="World scale factor (default: 0.03).",
    )
    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Don't watch for changes; run once and exit when the game closes.",
    )
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="Convert .map to .irunmap and exit (don't launch the game).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output .irunmap path (only used with --convert-only).",
    )
    parser.add_argument(
        "--bake",
        action="store_true",
        help="Run ericw-tools bake before loading (slower, but with lighting).",
    )
    parser.add_argument(
        "--ericw-tools",
        default=None,
        help="Path to ericw-tools bin directory (required when --bake is set).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="File change poll interval in seconds (default: 1.0).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    map_path = Path(args.map_file).resolve()
    if not map_path.exists():
        print(f"{_PREFIX} Error: .map file not found: {map_path}", file=sys.stderr)
        sys.exit(1)
    if map_path.suffix.lower() != ".map":
        print(f"{_PREFIX} Warning: file doesn't have .map extension: {map_path}", file=sys.stderr)

    if args.convert_only:
        _convert_and_exit(
            map_path=map_path,
            output=args.output,
            scale=args.scale,
            bake=args.bake,
            ericw_tools=args.ericw_tools,
        )
        return

    _run_with_watch(
        map_path=map_path,
        scale=args.scale,
        watch=not args.no_watch,
        poll_interval=args.poll_interval,
        bake=args.bake,
        ericw_tools=args.ericw_tools,
    )


if __name__ == "__main__":
    main()
