"""Subprocess spawning for launcher actions (game, pack, editor)."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
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
    map_path: str = "",
    *,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Launch TrenchBroom with optional source map."""
    cmd = [trenchbroom_exe]
    if map_path:
        cmd.append(map_path)
    return _spawn("TrenchBroom", cmd, on_line=on_line)


def spawn_validate_pack(
    python: str,
    ivan_root: str,
    *,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Run scope05_rollout_validation.py to validate demo pack pipeline."""
    script = str(Path(ivan_root) / "tools" / "scope05_rollout_validation.py")
    cmd = [python, script]
    return _spawn("Validate Pack", cmd, cwd=ivan_root, on_line=on_line)


def spawn_generate_tb_textures(
    python: str,
    ivan_root: str,
    *,
    on_line: Callable[[str], None] | None = None,
) -> ProcessHandle:
    """Generate TrenchBroom texture outputs from current assets."""
    script = str(Path(ivan_root) / "tools" / "sync_trenchbroom_profile.py")
    cmd = [python, script]
    return _spawn("Generate TB Textures", cmd, cwd=ivan_root, on_line=on_line)


def create_template_map(*, maps_dir: str) -> Path:
    """Create a new Valve220 map from a minimal template under maps_dir."""
    root = Path(maps_dir)
    root.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("m%y%m%d_%H%M%S")
    out_dir = root / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out_map = out_dir / f"{stem}.map"
    template_texture = _pick_template_texture_name(root)
    world_brush = _cube_brush(
        min_x=-256,
        min_y=-256,
        min_z=0,
        max_x=256,
        max_y=256,
        max_z=128,
        texture="__TB_empty",
    )
    sample_brush = _cube_brush(
        min_x=-32,
        min_y=-32,
        min_z=0,
        max_x=32,
        max_y=32,
        max_z=64,
        texture=template_texture,
    )
    # Minimal valid Valve220 map: world brush + sample textured block + player start.
    content = (
        "// Game: IVAN\n"
        "// Format: Valve\n"
        "{\n"
        "\"classname\" \"worldspawn\"\n"
        "\"mapversion\" \"220\"\n"
        f"{world_brush}"
        f"{sample_brush}"
        "}\n"
        "{\n"
        "\"classname\" \"info_player_start\"\n"
        "\"origin\" \"0 0 32\"\n"
        "\"angle\" \"90\"\n"
        "}\n"
    )
    out_map.write_text(content, encoding="utf-8")
    return out_map


def _pick_template_texture_name(maps_root: Path) -> str:
    """Pick a sensible texture for template maps, fallback to __TB_empty."""
    if maps_root.name == "maps":
        assets_root = maps_root.parent
    else:
        assets_root = maps_root
    candidates = [
        assets_root / "textures",
        assets_root.parent / "trenchbroom" / "generated" / "textures",
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tga"}:
                continue
            if p.stem:
                return p.stem
    return "__TB_empty"


def _cube_brush(
    *,
    min_x: int,
    min_y: int,
    min_z: int,
    max_x: int,
    max_y: int,
    max_z: int,
    texture: str,
) -> str:
    """Create a valid Valve220 cuboid brush definition."""
    return (
        "{\n"
        f"( {min_x} {min_y} {min_z} ) ( {min_x} {min_y + 1} {min_z} ) ( {min_x} {min_y} {min_z + 1} ) {texture} [ 0 -1 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
        f"( {min_x} {min_y} {min_z} ) ( {min_x} {min_y} {min_z + 1} ) ( {min_x + 1} {min_y} {min_z} ) {texture} [ 1 0 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
        f"( {min_x} {min_y} {min_z} ) ( {min_x + 1} {min_y} {min_z} ) ( {min_x} {min_y + 1} {min_z} ) {texture} [ -1 0 0 0 ] [ 0 -1 0 0 ] 0 1 1\n"
        f"( {max_x} {max_y} {max_z} ) ( {max_x} {max_y + 1} {max_z} ) ( {max_x + 1} {max_y} {max_z} ) {texture} [ 1 0 0 0 ] [ 0 -1 0 0 ] 0 1 1\n"
        f"( {max_x} {max_y} {max_z} ) ( {max_x + 1} {max_y} {max_z} ) ( {max_x} {max_y} {max_z + 1} ) {texture} [ -1 0 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
        f"( {max_x} {max_y} {max_z} ) ( {max_x} {max_y} {max_z + 1} ) ( {max_x} {max_y + 1} {max_z} ) {texture} [ 0 1 0 0 ] [ 0 0 -1 0 ] 0 1 1\n"
        "}\n"
    )


def sync_trenchbroom_profile(ivan_root: str) -> list[str]:
    """Copy GameConfig.cfg and ivan.fgd to TrenchBroom games directory.

    Returns list of log messages (success/error).
    """
    import os
    import platform
    import shutil

    src_dir = Path(ivan_root) / "trenchbroom"
    if not src_dir.is_dir():
        return [f"TrenchBroom config not found: {src_dir}"]

    # Platform-specific TrenchBroom games dir
    system = platform.system()
    if system == "Windows":
        tb_base = Path(os.environ.get("APPDATA", "")) / "TrenchBroom" / "games"
    elif system == "Darwin":
        tb_base = Path.home() / "Library" / "Application Support" / "TrenchBroom" / "games"
    else:
        tb_base = Path.home() / ".TrenchBroom" / "games"

    dest_dir = tb_base / "IVAN"
    dest_dir.mkdir(parents=True, exist_ok=True)
    messages: list[str] = []
    prefs_path = tb_base.parent / "Preferences.json"

    assets_root = (Path(ivan_root) / "assets").resolve()
    editor_materials = assets_root / "textures_tb"
    editor_materials.mkdir(parents=True, exist_ok=True)

    for name in ("GameConfig.cfg", "ivan.fgd"):
        src = src_dir / name
        if not src.is_file():
            messages.append(f"Skip {name}: not found in {src_dir}")
            continue
        dest = dest_dir / name
        try:
            if name == "GameConfig.cfg":
                cfg_data = json.loads(src.read_text(encoding="utf-8"))
                cfg_data.setdefault("filesystem", {})
                cfg_data["filesystem"]["searchpath"] = "."
                cfg_data.setdefault("materials", {})
                # TrenchBroom rejects absolute materials paths; keep this relative
                # to filesystem searchpath.
                cfg_data["materials"]["root"] = "textures_tb"
                dest.write_text(json.dumps(cfg_data, indent=4), encoding="utf-8")
            else:
                shutil.copy2(src, dest)
            messages.append(f"Copied {name} -> {dest}")
        except OSError as e:
            messages.append(f"Failed to copy {name}: {e}")
        except json.JSONDecodeError as e:
            messages.append(f"Failed to parse {name}: {e}")

    # Ensure IVAN game path is configured so TrenchBroom does not fallback
    # to defaults/assets.
    try:
        prefs_data: dict[str, object]
        if prefs_path.is_file():
            prefs_data = json.loads(prefs_path.read_text(encoding="utf-8"))
            if not isinstance(prefs_data, dict):
                prefs_data = {}
        else:
            prefs_data = {}
        prefs_data["Games/IVAN/Path"] = str(assets_root)
        prefs_path.write_text(json.dumps(prefs_data, indent=4), encoding="utf-8")
        messages.append(f"Configured Games/IVAN/Path -> {assets_root}")
    except OSError as e:
        messages.append(f"Failed to update TrenchBroom preferences: {e}")
    except json.JSONDecodeError as e:
        messages.append(f"Failed to parse TrenchBroom preferences: {e}")

    return messages


