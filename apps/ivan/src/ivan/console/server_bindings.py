from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ivan.console.command_bus import CommandArgSpec, CommandMetadata, CommandResult
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


def _legacy_wrap(legacy_handler, meta: CommandMetadata):
    def _wrapped(ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        argv: list[str] = []
        for spec in meta.args:
            v = args.get(spec.name)
            if spec.required:
                argv.append(str(v) if v is not None else "")
            elif v is not None and v != "":
                argv.append(str(v))
        try:
            out = legacy_handler(ctx, argv)
            return CommandResult.success(out=list(out))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="handler-error")

    return _wrapped


def build_server_console(server: Any) -> Console:
    """
    Build a minimal typed server console for dedicated/host processes.

    Commands: help, echo, exec, cmd_meta. Physics tuning cvars are registered
    for runtime tweaking. MCP discoverability via cmd_meta supports prefix,
    tag, page, page_size filters.
    """
    con = Console()

    def _format_bus_meta(name: str) -> list[str]:
        meta = con.find_command_metadata(name)
        if meta is None:
            return [f"unknown command: {name}"]
        lines = [f"{meta.name}: {meta.summary}", f"route: {meta.route}"]
        if meta.tags:
            lines.append(f"tags: {', '.join(meta.tags)}")
        if meta.args:
            lines.append("args:")
            for a in meta.args:
                req = "required" if bool(a.required and a.default is None) else "optional"
                default = "" if a.default is None else f" default={a.default}"
                choices = "" if not a.choices else f" choices={','.join(a.choices)}"
                lines.append(f"  --{a.name} ({a.typ}, {req}){default}{choices} {a.help}".rstrip())
        return lines

    def _cmd_help(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if argv:
            return _format_bus_meta(str(argv[0]))
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

    def _bus_help(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        cmd = str(args.get("command") or "").strip()
        if cmd:
            return CommandResult.success(out=_format_bus_meta(cmd))
        return CommandResult.success(out=_cmd_help(_ctx, []))

    def _bus_meta(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        prefix = str(args.get("prefix") or "").strip().casefold()
        tag_filter = str(args.get("tag") or "").strip().casefold()
        page = max(1, int(args.get("page") or 1))
        page_size = max(1, min(200, int(args.get("page_size") or 50)))
        rows: list[dict[str, Any]] = []
        for meta in con.list_command_metadata():
            if prefix and prefix not in str(meta.name).casefold():
                continue
            if tag_filter and tag_filter not in (t.casefold() for t in meta.tags):
                continue
            rows.append(
                {
                    "name": meta.name,
                    "summary": meta.summary,
                    "route": meta.route,
                    "tags": list(meta.tags),
                    "args": [
                        {
                            "name": a.name,
                            "type": a.typ,
                            "required": bool(a.required and a.default is None),
                            "default": a.default,
                            "help": a.help,
                            "choices": list(a.choices),
                        }
                        for a in meta.args
                    ],
                }
            )
        rows.sort(key=lambda x: str(x.get("name") or ""))
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = rows[start:end]
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        payload = {
            "commands": page_rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    con.register_bus_command(
        metadata=CommandMetadata(
            name="help",
            summary="List commands and cvars or show command details.",
            route="immediate",
            tags=("discoverability", "server"),
            args=(CommandArgSpec(name="command", typ="str", required=False, default="", help="Optional command name."),),
        ),
        handler=_bus_help,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="cmd_meta",
            summary="Dump typed command metadata as JSON with filtering and pagination.",
            route="immediate",
            tags=("discoverability", "mcp", "server"),
            args=(
                CommandArgSpec(name="prefix", typ="str", required=False, default="", help="Optional name prefix filter."),
                CommandArgSpec(name="tag", typ="str", required=False, default="", help="Optional tag filter."),
                CommandArgSpec(name="page", typ="int", required=False, default=1, minimum=1, help="Page index (1-based)."),
                CommandArgSpec(
                    name="page_size",
                    typ="int",
                    required=False,
                    default=50,
                    minimum=1,
                    maximum=200,
                    help="Items per page (max 200).",
                ),
            ),
        ),
        handler=_bus_meta,
    )

    _echo_meta = CommandMetadata(
        name="echo",
        summary="Print text.",
        route="immediate",
        tags=("utility", "server"),
        args=(CommandArgSpec(name="text", typ="str", required=False, default="", help="Text to print.", greedy=True),),
    )
    con.register_bus_command(metadata=_echo_meta, handler=_legacy_wrap(_cmd_echo, _echo_meta))

    _exec_meta = CommandMetadata(
        name="exec",
        summary="Execute a .cfg-like script file.",
        route="immediate",
        tags=("utility", "server"),
        args=(CommandArgSpec(name="path", typ="str", required=True, help="Path to script file."),),
    )
    con.register_bus_command(metadata=_exec_meta, handler=_legacy_wrap(_cmd_exec, _exec_meta))

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
