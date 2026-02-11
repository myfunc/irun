"""Subprocess spawning for launcher actions (game, pack, editor)."""

from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class ProcessHandle:
    """Tracks a running subprocess and its log output."""

    label: str
    proc: subprocess.Popen
    log_lines: deque[str] = field(default_factory=lambda: deque(maxlen=2000))
    _readers: list[threading.Thread] = field(default_factory=list)

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def kill(self) -> None:
        if self.alive:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _stream_reader(stream, lines: deque[str], on_line: Callable[[str], None] | None) -> None:
    """Read lines from a subprocess stream and append to the shared deque."""
    try:
        for raw in iter(stream.readline, ""):
            if not raw:
                break
            line = raw.rstrip("\n\r")
            lines.append(f"[{_ts()}] {line}")
            if on_line:
                on_line(line)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _spawn(
    label: str,
    cmd: list[str],
    *,
    cwd: str | None = None,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Launch a subprocess with stdout/stderr captured to a ProcessHandle."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        bufsize=1,
    )
    handle = ProcessHandle(label=label, proc=proc)
    handle.log_lines.append(f"[{_ts()}] --- {label} (PID {proc.pid}) ---")
    handle.log_lines.append(f"[{_ts()}] > {' '.join(cmd)}")

    t = threading.Thread(target=_stream_reader, args=(proc.stdout, handle.log_lines, on_line), daemon=True)
    t.start()
    handle._readers.append(t)
    return handle


# ── public actions ───────────────────────────────────────────


def spawn_game(
    python: str,
    ivan_root: str,
    map_path: str = "",
    *,
    watch: bool = True,
    map_profile: str = "auto",
    runtime_lighting: bool = False,
    hl_root: str = "",
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Launch ``python -m ivan`` with optional map/run options."""
    cmd = [python, "-m", "ivan"]
    if map_path:
        cmd.extend(["--map", map_path])
        if map_profile:
            cmd.extend(["--map-profile", map_profile])
        if watch:
            cmd.append("--watch")
    if hl_root:
        cmd.extend(["--hl-root", hl_root])
    if runtime_lighting:
        cmd.append("--runtime-lighting")
    return _spawn("IVAN Game", cmd, cwd=ivan_root, on_line=on_line)


def spawn_pack(
    python: str,
    ivan_root: str,
    map_path: str,
    *,
    profile: str = "dev-fast",
    wad_dirs: list[str] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Run ``python tools/pack_map.py --map <map> --output <out> [--wad-dirs ...]``."""
    script = str(Path(ivan_root) / "tools" / "pack_map.py")
    map_p = Path(map_path)
    output = map_p.with_suffix(".irunmap")
    cmd = [python, script, "--map", map_path, "--output", str(output)]
    if profile:
        cmd.extend(["--profile", profile])
    if wad_dirs:
        cmd.append("--wad-dirs")
        cmd.extend(wad_dirs)
    return _spawn("Pack Map", cmd, cwd=ivan_root, on_line=on_line)


def spawn_trenchbroom(
    trenchbroom_exe: str,
    map_path: str,
    *,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Launch TrenchBroom with the selected source map."""
    cmd = [trenchbroom_exe, map_path]
    return _spawn("TrenchBroom", cmd, on_line=on_line)


