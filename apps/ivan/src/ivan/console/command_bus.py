from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable


CommandData = dict[str, Any]
CommandHandler = Callable[[Any, CommandData], "CommandResult"]


@dataclass(frozen=True)
class CommandArgSpec:
    name: str
    typ: str = "str"  # str | int | float | bool
    required: bool = False
    default: Any = None
    help: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class CommandMetadata:
    name: str
    summary: str
    route: str = "game-thread"  # game-thread | immediate
    tags: tuple[str, ...] = ()
    args: tuple[CommandArgSpec, ...] = ()


@dataclass
class CommandResult:
    ok: bool
    out: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""

    @staticmethod
    def success(*, out: list[str] | None = None, data: dict[str, Any] | None = None) -> "CommandResult":
        return CommandResult(ok=True, out=list(out or []), data=dict(data or {}), error_code="")

    @staticmethod
    def failure(
        message: str,
        *,
        error_code: str = "command-error",
        out: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> "CommandResult":
        lines = list(out or [])
        if message:
            lines.append(f"error: {message}")
        return CommandResult(ok=False, out=lines, data=dict(data or {}), error_code=str(error_code))


@dataclass
class CommandExecution:
    name: str
    ok: bool
    out: list[str]
    data: dict[str, Any]
    elapsed_ms: float
    error_code: str = ""


@dataclass
class CommandLineExecution:
    ok: bool
    out: list[str]
    executions: list[CommandExecution]
    elapsed_ms: float


def _coerce_bool(value: str) -> bool:
    v = str(value or "").strip().lower()
    if v in ("1", "true", "on", "yes", "y"):
        return True
    if v in ("0", "false", "off", "no", "n"):
        return False
    raise ValueError(f"invalid bool: {value!r}")


def _coerce_with_spec(value: str, spec: CommandArgSpec) -> Any:
    typ = str(spec.typ or "str").strip().lower()
    if typ == "str":
        out: Any = str(value)
    elif typ == "int":
        out = int(str(value).strip())
    elif typ == "float":
        out = float(str(value).strip())
    elif typ == "bool":
        out = _coerce_bool(value)
    else:
        raise ValueError(f"unsupported arg type: {spec.typ}")

    if spec.choices:
        raw = str(out)
        if raw not in spec.choices:
            raise ValueError(f"must be one of: {', '.join(spec.choices)}")
    if isinstance(out, (int, float)):
        if spec.minimum is not None and float(out) < float(spec.minimum):
            raise ValueError(f"must be >= {spec.minimum}")
        if spec.maximum is not None and float(out) > float(spec.maximum):
            raise ValueError(f"must be <= {spec.maximum}")
    return out


class CommandBus:
    """
    Typed command registry with argument schema validation and discoverability metadata.
    """

    def __init__(self) -> None:
        self._registry: dict[str, tuple[CommandMetadata, CommandHandler]] = {}

    def register(self, *, metadata: CommandMetadata, handler: CommandHandler) -> None:
        name = str(metadata.name or "").strip()
        if not name:
            raise ValueError("command name is required")
        if name in self._registry:
            raise ValueError(f"duplicate command: {name}")
        self._registry[name] = (metadata, handler)

    def has(self, name: str) -> bool:
        return str(name) in self._registry

    def list_metadata(self) -> list[CommandMetadata]:
        return [self._registry[k][0] for k in sorted(self._registry.keys())]

    def get_metadata(self, name: str) -> CommandMetadata | None:
        row = self._registry.get(str(name))
        return row[0] if row is not None else None

    def _parse_argv(self, *, meta: CommandMetadata, argv: list[str]) -> CommandData:
        out: dict[str, Any] = {}
        positional: list[str] = []
        named: dict[str, str] = {}
        i = 0
        while i < len(argv):
            tok = str(argv[i])
            if tok.startswith("--"):
                body = tok[2:]
                if "=" in body:
                    k, v = body.split("=", 1)
                    named[str(k).strip()] = str(v)
                else:
                    key = str(body).strip()
                    if i + 1 < len(argv) and not str(argv[i + 1]).startswith("--"):
                        i += 1
                        named[key] = str(argv[i])
                    else:
                        named[key] = "true"
            else:
                positional.append(tok)
            i += 1

        pos_idx = 0
        for spec in meta.args:
            raw: str | None = None
            if spec.name in named:
                raw = named.pop(spec.name)
            elif pos_idx < len(positional):
                raw = positional[pos_idx]
                pos_idx += 1
            if raw is None:
                if spec.required and spec.default is None:
                    raise ValueError(f"missing required argument: {spec.name}")
                out[spec.name] = spec.default
                continue
            out[spec.name] = _coerce_with_spec(raw, spec)

        unknown_extra = positional[pos_idx:]
        if named:
            raise ValueError(f"unknown option(s): {', '.join(sorted(named.keys()))}")
        if unknown_extra:
            raise ValueError(f"unexpected argument(s): {' '.join(unknown_extra)}")
        return out

    def dispatch(self, *, ctx: Any, name: str, argv: list[str]) -> CommandExecution:
        row = self._registry.get(str(name))
        if row is None:
            return CommandExecution(
                name=str(name),
                ok=False,
                out=[f"unknown command: {name}"],
                data={},
                elapsed_ms=0.0,
                error_code="unknown-command",
            )
        meta, handler = row
        t0 = perf_counter()
        try:
            args = self._parse_argv(meta=meta, argv=argv)
            result = handler(ctx, args)
            if not isinstance(result, CommandResult):
                result = CommandResult.failure("handler returned invalid result type", error_code="handler-contract")
        except Exception as e:
            result = CommandResult.failure(str(e), error_code="validation-error")
        return CommandExecution(
            name=meta.name,
            ok=bool(result.ok),
            out=list(result.out),
            data=dict(result.data),
            elapsed_ms=(perf_counter() - t0) * 1000.0,
            error_code=str(result.error_code or ""),
        )

