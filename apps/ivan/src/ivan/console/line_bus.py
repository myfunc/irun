from __future__ import annotations

import threading
from collections import deque

from ivan.console.core import CommandContext


class ThreadSafeLineBus:
    def __init__(self, *, max_lines: int = 400) -> None:
        self._lock = threading.Lock()
        self._q: deque[str] = deque(maxlen=max(20, int(max_lines)))

    def push(self, *lines: str) -> None:
        with self._lock:
            for ln in lines:
                s = str(ln)
                if s:
                    self._q.append(s)

    def drain(self) -> list[str]:
        with self._lock:
            if not self._q:
                return []
            out = list(self._q)
            self._q.clear()
            return out

    def listener(self, ctx: CommandContext, line: str, out_lines: list[str]) -> None:
        # Only echo the input line for non-UI origins. UI already prints a local "] <line>".
        if str(ctx.origin) != "ui":
            prefix = str(ctx.origin) if ctx.origin else "console"
            self.push(f"] ({prefix}) {line}")
        self.push(*out_lines)

