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
class EditMapCommand:
    pass


# ── Pack-centric commands ─────────────────────────────────────


@dataclass(frozen=True)
class DiscoverPacksCommand:
    """Refresh pack list from maps directory."""

    pass


@dataclass(frozen=True)
class BuildPackCommand:
    """Build selected .map into .irunmap pack."""

    pass


@dataclass(frozen=True)
class ValidatePackCommand:
    """Run scope05 validation on demo pipeline (builds + validates demo.irunmap)."""

    pass


@dataclass(frozen=True)
class AssignPackToMapCommand:
    """Assign selected pack to selected map for launch (use pack instead of source)."""

    pass


@dataclass(frozen=True)
class SyncTBProfileCommand:
    """Copy IVAN game config to TrenchBroom preferences directory."""

    pass


@dataclass(frozen=True)
class GenerateTBTexturesCommand:
    """Generate TrenchBroom textures/manifest from assets."""

    pass


@dataclass(frozen=True)
class CreateTemplateMapCommand:
    """Create a new map from template and open it in TrenchBroom."""

    pass
