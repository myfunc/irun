from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ErrorItem:
    ts: float
    context: str
    message: str
    tb: str | None
    count: int = 1

    def summary_line(self) -> str:
        base = f"{self.context}: {self.message}".strip()
        if self.count > 1:
            base += f" (x{self.count})"
        return base


class ErrorLog:
    """
    Small in-memory error buffer intended for UI display + stderr logging.

    Goals:
    - never crash the app because of logging
    - keep a short, useful feed of recent failures
    - de-duplicate repeated identical exceptions (common in per-frame update loops)
    """

    def __init__(self, *, max_items: int = 30, persist_path: Path | None = None) -> None:
        self.enabled: bool = True
        self._max_items = max(1, int(max_items))
        self._items: list[ErrorItem] = []
        self._last_key: tuple[str, str] | None = None
        self._persist_path = Path(persist_path) if isinstance(persist_path, Path) else None

    def items(self) -> list[ErrorItem]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._last_key = None

    def log_message(self, *, context: str, message: str) -> None:
        if not self.enabled:
            return
        context = str(context or "unknown")
        message = str(message or "").strip() or "Unknown error"
        self._append(context=context, message=message, tb=None)
        self._persist(context=context, message=message, tb=None)
        try:
            print(f"[ERROR] {context}: {message}", file=sys.stderr)
        except Exception:
            pass

    def log_exception(self, *, context: str, exc: BaseException) -> None:
        if not self.enabled:
            return
        context = str(context or "unknown")
        msg = f"{type(exc).__name__}: {exc}".strip()
        tb = traceback.format_exc()
        self._append(context=context, message=msg, tb=tb)
        self._persist(context=context, message=msg, tb=tb)
        try:
            print(f"[ERROR] {context}: {msg}\n{tb}", file=sys.stderr)
        except Exception:
            pass

    def _append(self, *, context: str, message: str, tb: str | None) -> None:
        ts = time.time()
        key = (context, message)
        if self._items and self._last_key == key:
            self._items[-1].ts = ts
            self._items[-1].count += 1
            # Keep the first traceback for repeated errors; it is usually enough.
            return

        self._items.append(ErrorItem(ts=ts, context=context, message=message, tb=tb, count=1))
        self._last_key = key
        if len(self._items) > self._max_items:
            self._items = self._items[-self._max_items :]

    def _persist(self, *, context: str, message: str, tb: str | None) -> None:
        p = self._persist_path
        if p is None:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            lines = [f"[{ts}] {context}: {message}"]
            if isinstance(tb, str) and tb.strip():
                lines.append(tb.rstrip())
            lines.append("")
            with p.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        except Exception:
            pass
