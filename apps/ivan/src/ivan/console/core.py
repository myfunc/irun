from __future__ import annotations

import shlex
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from ivan.console.command_bus import CommandBus, CommandExecution, CommandLineExecution, CommandMetadata

@dataclass(frozen=True)
class CommandContext:
    """
    Execution context for a console command.

    This is intentionally minimal for now. We'll extend it once we start forwarding
    commands over the network / adding permissions.
    """

    role: str  # "client" | "server"
    origin: str  # "local" | "mcp" | ...


CommandHandler = Callable[[CommandContext, list[str]], list[str]]
ConsoleListener = Callable[[CommandContext, str, list[str]], None]


@dataclass
class _Command:
    name: str
    help: str
    handler: CommandHandler


@dataclass
class _Cvar:
    name: str
    help: str
    type: str  # "bool" | "int" | "float" | "str"
    get_value: Callable[[], Any]
    set_value: Callable[[Any], None]


@dataclass
class _LegacyExecution:
    name: str
    ok: bool
    out: list[str]
    data: dict[str, Any]
    error_code: str = ""


def _split_commands(line: str) -> list[str]:
    """
    Split a console input line into commands separated by ';', respecting quotes.
    """

    s = str(line or "")
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    esc = False
    for ch in s:
        if esc:
            buf.append(ch)
            esc = False
            continue
        if ch == "\\":
            esc = True
            buf.append(ch)
            continue
        if quote is not None:
            if ch == quote:
                quote = None
            buf.append(ch)
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch == ";":
            part = "".join(buf).strip()
            if part:
                out.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        out.append(part)
    return out


def _parse_argv(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except Exception:
        # Best-effort fallback: split on whitespace.
        return [p for p in str(cmd or "").strip().split() if p]


def _coerce_value(value_s: str, *, typ: str) -> Any:
    if typ == "bool":
        v = str(value_s or "").strip().lower()
        if v in ("1", "true", "on", "yes", "y"):
            return True
        if v in ("0", "false", "off", "no", "n"):
            return False
        raise ValueError(f"invalid bool: {value_s!r}")
    if typ == "int":
        return int(str(value_s or "").strip())
    if typ == "float":
        return float(str(value_s or "").strip())
    if typ == "str":
        return str(value_s)
    raise ValueError(f"unknown cvar type: {typ!r}")


class Console:
    def __init__(self) -> None:
        self._cmds: dict[str, _Command] = {}
        self._cvars: dict[str, _Cvar] = {}
        self._bus = CommandBus()
        self._listeners: list[ConsoleListener] = []

    def register_command(self, *, name: str, handler: CommandHandler, help: str = "") -> None:
        n = str(name or "").strip()
        if not n:
            raise ValueError("command name is required")
        self._cmds[n] = _Command(name=n, help=str(help or ""), handler=handler)

    def register_bus_command(self, *, metadata: CommandMetadata, handler) -> None:
        self._bus.register(metadata=metadata, handler=handler)

    def register_cvar(
        self,
        *,
        name: str,
        typ: str,
        get_value: Callable[[], Any],
        set_value: Callable[[Any], None],
        help: str = "",
    ) -> None:
        n = str(name or "").strip()
        if not n:
            raise ValueError("cvar name is required")
        t = str(typ or "").strip().lower()
        if t not in ("bool", "int", "float", "str"):
            raise ValueError(f"invalid cvar type: {typ!r}")
        self._cvars[n] = _Cvar(
            name=n,
            help=str(help or ""),
            type=t,
            get_value=get_value,
            set_value=set_value,
        )

    def list_commands(self) -> list[tuple[str, str]]:
        items: dict[str, str] = {}
        for c in self._cmds.values():
            items[c.name] = c.help
        for m in self._bus.list_metadata():
            items[m.name] = m.summary
        return sorted(items.items(), key=lambda x: x[0])

    def list_command_metadata(self) -> list[CommandMetadata]:
        return self._bus.list_metadata()

    def find_command_metadata(self, name: str) -> CommandMetadata | None:
        return self._bus.get_metadata(name)

    def suggest_commands(self, prefix: str, *, limit: int = 8) -> list[tuple[str, str]]:
        p = str(prefix or "").strip().casefold()
        rows = self.list_commands()
        if not p:
            return rows[: max(1, int(limit))]
        out = [it for it in rows if str(it[0]).casefold().startswith(p)]
        return out[: max(1, int(limit))]

    def list_cvars(self) -> list[tuple[str, str, str]]:
        return sorted(((v.name, v.type, v.help) for v in self._cvars.values()), key=lambda x: x[0])

    def register_listener(self, listener: ConsoleListener) -> None:
        self._listeners.append(listener)

    def _exec_legacy(self, *, ctx: CommandContext, name: str, argv: list[str]) -> _LegacyExecution:
        cvar = self._cvars.get(name)
        if cvar is not None:
            if len(argv) == 0:
                try:
                    return _LegacyExecution(
                        name=name,
                        ok=True,
                        out=[f'{cvar.name} "{cvar.get_value()}"'],
                        data={"kind": "cvar"},
                    )
                except Exception as e:
                    return _LegacyExecution(
                        name=name,
                        ok=False,
                        out=[f"error reading {cvar.name}: {e}"],
                        data={"kind": "cvar"},
                        error_code="cvar-read",
                    )
            try:
                val = _coerce_value(argv[0], typ=cvar.type)
            except Exception as e:
                return _LegacyExecution(
                    name=name,
                    ok=False,
                    out=[f"error: {cvar.name} expects {cvar.type}: {e}"],
                    data={"kind": "cvar"},
                    error_code="cvar-parse",
                )
            try:
                cvar.set_value(val)
                return _LegacyExecution(
                    name=name,
                    ok=True,
                    out=[f'{cvar.name} "{cvar.get_value()}"'],
                    data={"kind": "cvar"},
                )
            except Exception as e:
                return _LegacyExecution(
                    name=name,
                    ok=False,
                    out=[f"error setting {cvar.name}: {e}"],
                    data={"kind": "cvar"},
                    error_code="cvar-write",
                )

        cmd = self._cmds.get(name)
        if cmd is None:
            return _LegacyExecution(name=name, ok=False, out=[f"unknown command: {name}"], data={}, error_code="unknown-command")
        try:
            return _LegacyExecution(name=name, ok=True, out=list(cmd.handler(ctx, argv)), data={})
        except Exception as e:
            return _LegacyExecution(name=name, ok=False, out=[f"error in {name}: {e}"], data={}, error_code="handler-error")

    def execute_line_detailed(self, *, ctx: CommandContext, line: str) -> CommandLineExecution:
        t0 = perf_counter()
        out: list[str] = []
        executions: list[CommandExecution] = []
        for raw_cmd in _split_commands(line):
            argv = _parse_argv(raw_cmd)
            if not argv:
                continue
            name = str(argv[0])
            if self._bus.has(name):
                ex = self._bus.dispatch(ctx=ctx, name=name, argv=argv[1:])
                executions.append(ex)
                out.extend(ex.out)
                continue
            lg = self._exec_legacy(ctx=ctx, name=name, argv=argv[1:])
            ex = CommandExecution(
                name=lg.name,
                ok=lg.ok,
                out=list(lg.out),
                data=dict(lg.data),
                elapsed_ms=0.0,
                error_code=str(lg.error_code),
            )
            executions.append(ex)
            out.extend(ex.out)
        result = CommandLineExecution(
            ok=all(x.ok for x in executions) if executions else True,
            out=out,
            executions=executions,
            elapsed_ms=(perf_counter() - t0) * 1000.0,
        )
        if self._listeners:
            for it in list(self._listeners):
                try:
                    it(ctx, str(line), list(result.out))
                except Exception:
                    # Listener failures must never break the console execution path.
                    pass
        return result

    def execute_line(self, *, ctx: CommandContext, line: str) -> list[str]:
        return list(self.execute_line_detailed(ctx=ctx, line=line).out)
