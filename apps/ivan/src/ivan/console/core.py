from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any, Callable


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
        self._listeners: list[ConsoleListener] = []

    def register_command(self, *, name: str, handler: CommandHandler, help: str = "") -> None:
        n = str(name or "").strip()
        if not n:
            raise ValueError("command name is required")
        self._cmds[n] = _Command(name=n, help=str(help or ""), handler=handler)

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
        return sorted(((c.name, c.help) for c in self._cmds.values()), key=lambda x: x[0])

    def list_cvars(self) -> list[tuple[str, str, str]]:
        return sorted(((v.name, v.type, v.help) for v in self._cvars.values()), key=lambda x: x[0])

    def register_listener(self, listener: ConsoleListener) -> None:
        self._listeners.append(listener)

    def execute_line(self, *, ctx: CommandContext, line: str) -> list[str]:
        out: list[str] = []
        for raw_cmd in _split_commands(line):
            argv = _parse_argv(raw_cmd)
            if not argv:
                continue
            name = argv[0]

            cvar = self._cvars.get(name)
            if cvar is not None:
                if len(argv) == 1:
                    try:
                        out.append(f'{cvar.name} "{cvar.get_value()}"')
                    except Exception as e:
                        out.append(f"error reading {cvar.name}: {e}")
                    continue
                try:
                    val = _coerce_value(argv[1], typ=cvar.type)
                except Exception as e:
                    out.append(f"error: {cvar.name} expects {cvar.type}: {e}")
                    continue
                try:
                    cvar.set_value(val)
                    out.append(f'{cvar.name} "{cvar.get_value()}"')
                except Exception as e:
                    out.append(f"error setting {cvar.name}: {e}")
                continue

            cmd = self._cmds.get(name)
            if cmd is None:
                out.append(f"unknown command: {name}")
                continue
            try:
                out.extend(cmd.handler(ctx, argv[1:]))
            except Exception as e:
                out.append(f"error in {name}: {e}")
        if self._listeners:
            for it in list(self._listeners):
                try:
                    it(ctx, str(line), list(out))
                except Exception:
                    # Listener failures must never break the console execution path.
                    pass
        return out
