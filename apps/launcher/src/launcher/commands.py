"""Typed command bus used by launcher UI actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


CommandHandler = Callable[[Any], None]


class CommandBus:
    """Minimal typed command bus for launcher callbacks."""

    def __init__(self) -> None:
        self._handlers: dict[type[Any], CommandHandler] = {}

    def register(self, command_type: type[Any], handler: CommandHandler) -> None:
        self._handlers[command_type] = handler

    def dispatch(self, command: Any) -> None:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise LookupError(f"No command handler registered for {type(command).__name__}")
        handler(command)


@dataclass(frozen=True)
class PlayCommand:
    use_advanced: bool


@dataclass(frozen=True)
class StopGameCommand:
    pass


@dataclass(frozen=True)
class PackMapCommand:
    pass


@dataclass(frozen=True)
class EditMapCommand:
    pass
