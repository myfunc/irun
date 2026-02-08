from __future__ import annotations

import datetime as _dt
import os
import traceback
from dataclasses import dataclass
from pathlib import Path


def _default_log_path() -> Path:
    root = Path.home() / ".irun" / "baker"
    root.mkdir(parents=True, exist_ok=True)
    return root / "baker.log"


@dataclass
class RuntimeLog:
    path: Path | None = None
    tail_lines: int = 12

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = _default_log_path()

    def log(self, msg: str) -> None:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}\n"
        try:
            assert self.path is not None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Logging must never crash the app.
            pass

    def log_exc(self, context: str) -> None:
        try:
            tb = traceback.format_exc()
            self.log(f"EXC {context}:\n{tb}")
        except Exception:
            pass

    def tail(self) -> str:
        try:
            assert self.path is not None
            if not self.path.exists():
                return ""
            data = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = data[-int(self.tail_lines) :]
            return "\n".join(tail)
        except Exception:
            return ""

