from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class _HookGroup:
    events: list[str] = field(default_factory=list)


class EventHooks:
    """
    Small registry around Panda3D `accept`/`ignore` so we can unbind whole groups
    (e.g. mode-specific hooks) without leaking events across reloads.
    """

    def __init__(self, *, base, safe_call: Callable[[str, Callable[[], None]], None]) -> None:
        self._base = base
        self._safe_call = safe_call
        self._groups: dict[str, _HookGroup] = {}

    def bind(self, *, group: str, event: str, context: str, fn: Callable[[], None]) -> None:
        g = self._groups.setdefault(str(group), _HookGroup())
        evt = str(event)
        # Wrap to ensure hook exceptions never crash the frame loop.
        self._base.accept(evt, lambda: self._safe_call(str(context), fn))
        g.events.append(evt)

    def unbind_group(self, group: str) -> None:
        g = self._groups.pop(str(group), None)
        if g is None:
            return
        for evt in g.events:
            try:
                self._base.ignore(evt)
            except Exception:
                pass


__all__ = ["EventHooks"]

