from __future__ import annotations

from pathlib import Path
from typing import Any

from ivan.console.core import CommandContext, Console
from ivan.physics.tuning import PhysicsTuning


def _read_exec_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("//") or s.startswith("#"):
            continue
        out.append(s)
    return out


def build_server_console(server: Any) -> Console:
    con = Console()

    def _cmd_help(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        lines: list[str] = ["commands:"]
        for name, help_s in con.list_commands():
            lines.append(f"  {name} - {help_s}".rstrip(" -"))
        lines.append("cvars:")
        for name, typ, help_s in con.list_cvars():
            lines.append(f"  {name} ({typ}) - {help_s}".rstrip(" -"))
        return lines

    def _cmd_echo(_ctx: CommandContext, argv: list[str]) -> list[str]:
        return [" ".join(argv)]

    def _cmd_exec(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: exec <path>"]
        p = Path(str(argv[0]))
        if not p.is_absolute():
            p = Path.cwd() / p
        lines = _read_exec_lines(p)
        out: list[str] = [f"exec {p} ({len(lines)} line(s))"]
        for ln in lines:
            out.extend(con.execute_line(ctx=CommandContext(role="server", origin="exec"), line=ln))
        return out

    con.register_command(name="help", help="List commands and cvars.", handler=_cmd_help)
    con.register_command(name="echo", help="Print text.", handler=_cmd_echo)
    con.register_command(name="exec", help="Execute a .cfg-like script file.", handler=_cmd_exec)

    for field, anno in PhysicsTuning.__annotations__.items():
        if not isinstance(field, str) or not field:
            continue
        typ = "float"
        if anno is bool:
            typ = "bool"
        elif anno is int:
            typ = "int"
        elif anno is str:
            typ = "str"

        def _make_getter(f: str):
            return lambda: getattr(server.tuning, f)

        def _make_setter(f: str):
            def _set(v: Any) -> None:
                # Reuse the same path as network config updates.
                server._apply_tuning_snapshot({f: v})  # noqa: SLF001
                server._tuning_version += 1  # noqa: SLF001

            return _set

        con.register_cvar(
            name=field,
            typ=typ,
            get_value=_make_getter(field),
            set_value=_make_setter(field),
            help="Server physics tuning field.",
        )

    return con

