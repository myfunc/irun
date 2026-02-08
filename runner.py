#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent
APPS_DIR = REPO_ROOT / "apps"


def _app_dir(app: str) -> Path:
    return (APPS_DIR / app).resolve()


def _python_for(app_dir: Path) -> str:
    venv_py = app_dir / ".venv" / "bin" / "python"
    if venv_py.exists() and os.access(venv_py, os.X_OK):
        return str(venv_py)
    return "python3"


def _default_module_for_app(app: str) -> str:
    # Keep this explicit to avoid surprising module names as the monorepo grows.
    mapping = {
        "ivan": "ivan",
        "baker": "baker",
        # UI kit is a library; `runapp ui_kit` runs the demo/playground.
        "ui_kit": "irun_ui_kit.demo",
    }
    if app in mapping:
        return mapping[app]
    return app


def _with_pythonpath(env: dict[str, str], app_dir: Path) -> dict[str, str]:
    """
    Best-effort "works even without pip -e" behavior:
    - If an app has `src/`, add it to PYTHONPATH.
    - Always add `apps/ui_kit/src` so Ivan/Baker can import `irun_ui_kit` even if not installed.
    """

    parts: list[str] = []
    app_src = app_dir / "src"
    if app_src.is_dir():
        parts.append(str(app_src))

    ui_kit_src = (APPS_DIR / "ui_kit" / "src").resolve()
    if ui_kit_src.is_dir():
        parts.append(str(ui_kit_src))

    if not parts:
        return env

    cur = env.get("PYTHONPATH", "")
    merged = os.pathsep.join(parts + ([cur] if cur else []))
    out = dict(env)
    out["PYTHONPATH"] = merged
    return out


def _run(cmd: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None) -> int:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(cmd, cwd=str(cwd), env=env)
    return int(p.returncode)


def cmd_list_apps(_args: argparse.Namespace) -> int:
    if not APPS_DIR.is_dir():
        print("apps/ folder not found", file=sys.stderr)
        return 2

    apps = sorted([p.name for p in APPS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")])
    for a in apps:
        print(a)
    return 0


def cmd_runapp(args: argparse.Namespace) -> int:
    app = str(args.app)
    app_dir = _app_dir(app)
    if not app_dir.is_dir():
        print(f"Unknown app: {app} (expected folder: {app_dir})", file=sys.stderr)
        return 2

    # Also accept runner flags even if user placed them after <app>.
    # This enables `./runner ivan --print-cmd --map ...` and `./runner runapp ivan --print-cmd ...`.
    app_args = list(args.app_args or [])
    print_cmd = bool(args.print_cmd)
    module_override = args.module
    i = 0
    while i < len(app_args):
        tok = str(app_args[i])
        if tok == "--print-cmd":
            print_cmd = True
            app_args.pop(i)
            continue
        if tok.startswith("--module="):
            module_override = tok.split("=", 1)[1]
            app_args.pop(i)
            continue
        if tok == "--module":
            if i + 1 >= len(app_args):
                print("runner: --module requires a value", file=sys.stderr)
                return 2
            module_override = str(app_args[i + 1])
            del app_args[i : i + 2]
            continue
        i += 1

    module = str(module_override or _default_module_for_app(app))
    py = _python_for(app_dir)

    cmd = [py, "-m", module, *app_args]

    if print_cmd:
        print("+", " ".join(shlex.quote(x) for x in cmd))
        return 0

    env = _with_pythonpath(dict(os.environ), app_dir)
    return _run(cmd, cwd=app_dir, extra_env=env)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="runner.py",
        description="IRUN repo helper (run apps with arguments).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List apps under apps/.")
    sp.set_defaults(fn=cmd_list_apps)

    sp = sub.add_parser("runapp", help="Run an app module from apps/<app>/, passing through arguments.")
    sp.add_argument("app", help="App folder name under apps/ (e.g. ivan, baker).")
    sp.add_argument(
        "--module",
        help="Python module to run (default: app-specific mapping, else <app>).",
        default=None,
    )
    sp.add_argument("--print-cmd", action="store_true", help="Print the resolved command and exit.")
    sp.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments forwarded to the app.")
    sp.set_defaults(fn=cmd_runapp)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]
    # UX sugar: allow `./runner ivan --map ...` as shorthand for `./runner runapp ivan --map ...`.
    if raw and not raw[0].startswith("-") and raw[0] not in {"list", "runapp"}:
        raw = ["runapp", *raw]
    args = parser.parse_args(raw)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
