from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ivan.state import state_dir


@dataclass
class AudioRuntime:
    enabled: bool = False
    master_volume: float = 0.85
    sfx_volume: float = 0.90
    channels: dict[str, list[Any]] = field(default_factory=dict)
    cursor: dict[str, int] = field(default_factory=dict)
    step_timer_s: float = 0.0


def _runtime(host) -> AudioRuntime:
    st = getattr(host, "_audio_runtime", None)
    if isinstance(st, AudioRuntime):
        return st
    st = AudioRuntime()
    setattr(host, "_audio_runtime", st)
    return st


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _write_wav(path: Path, *, samples: list[float], sample_rate: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        pcm = bytearray()
        for s in samples:
            x = max(-1.0, min(1.0, float(s)))
            pcm.extend(struct.pack("<h", int(x * 32767.0)))
        wf.writeframes(bytes(pcm))


def _tone_sweep(
    *,
    f0: float,
    f1: float,
    duration_s: float,
    amp: float,
    sample_rate: int = 22050,
    noise_mix: float = 0.0,
    seed: int = 1,
) -> list[float]:
    total = max(1, int(float(duration_s) * float(sample_rate)))
    out: list[float] = []
    rng = random.Random(int(seed))
    ph = 0.0
    for i in range(total):
        t = float(i) / float(max(1, total - 1))
        env = math.sin(math.pi * t) ** 1.2
        freq = float(f0) + (float(f1) - float(f0)) * t
        ph += (math.tau * freq) / float(sample_rate)
        tone = math.sin(ph) * env
        noise = (rng.uniform(-1.0, 1.0) * env) if noise_mix > 0.0 else 0.0
        out.append(float(amp) * ((tone * (1.0 - float(noise_mix))) + (noise * float(noise_mix))))
    return out


def _clicky_step(
    *,
    duration_s: float,
    amp: float,
    sample_rate: int = 22050,
    seed: int = 7,
) -> list[float]:
    total = max(1, int(float(duration_s) * float(sample_rate)))
    rng = random.Random(int(seed))
    out: list[float] = []
    lp = 0.0
    for i in range(total):
        t = float(i) / float(max(1, total - 1))
        env = math.exp(-7.4 * t)
        n = rng.uniform(-1.0, 1.0)
        lp = (lp * 0.76) + (n * 0.24)
        click = math.sin(2.0 * math.pi * 180.0 * t) * math.exp(-24.0 * t)
        out.append(float(amp) * ((lp * env * 0.75) + (click * 0.45)))
    return out


def _ensure_assets() -> dict[str, Path]:
    root = state_dir() / "audio_cache" / "sfx_v3"
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "weapon_blink": root / "weapon_blink.wav",
        "weapon_blink_impact": root / "weapon_blink_impact.wav",
        "weapon_slam": root / "weapon_slam.wav",
        "weapon_slam_impact": root / "weapon_slam_impact.wav",
        "weapon_rocket": root / "weapon_rocket.wav",
        "weapon_rocket_impact": root / "weapon_rocket_impact.wav",
        "weapon_pulse": root / "weapon_pulse.wav",
        "weapon_pulse_impact": root / "weapon_pulse_impact.wav",
        "grapple_attach": root / "grapple_attach.wav",
        "grapple_detach": root / "grapple_detach.wav",
        "step_walk": root / "step_walk.wav",
        "step_run": root / "step_run.wav",
        "race_countdown": root / "race_countdown.wav",
        "race_go": root / "race_go.wav",
        "race_checkpoint": root / "race_checkpoint.wav",
        "race_finish": root / "race_finish.wav",
    }
    if not paths["weapon_blink"].exists():
        _write_wav(paths["weapon_blink"], samples=_tone_sweep(f0=700.0, f1=310.0, duration_s=0.16, amp=0.54, noise_mix=0.10))
    if not paths["weapon_blink_impact"].exists():
        _write_wav(
            paths["weapon_blink_impact"],
            samples=_tone_sweep(f0=620.0, f1=240.0, duration_s=0.14, amp=0.52, noise_mix=0.16),
        )
    if not paths["weapon_slam"].exists():
        _write_wav(paths["weapon_slam"], samples=_tone_sweep(f0=280.0, f1=96.0, duration_s=0.24, amp=0.72, noise_mix=0.38))
    if not paths["weapon_slam_impact"].exists():
        _write_wav(
            paths["weapon_slam_impact"],
            samples=_tone_sweep(f0=220.0, f1=72.0, duration_s=0.22, amp=0.76, noise_mix=0.46),
        )
    if not paths["weapon_rocket"].exists():
        _write_wav(paths["weapon_rocket"], samples=_tone_sweep(f0=150.0, f1=62.0, duration_s=0.30, amp=0.80, noise_mix=0.47))
    if not paths["weapon_rocket_impact"].exists():
        _write_wav(
            paths["weapon_rocket_impact"],
            samples=_tone_sweep(f0=92.0, f1=38.0, duration_s=0.36, amp=0.90, noise_mix=0.58),
        )
    if not paths["weapon_pulse"].exists():
        _write_wav(paths["weapon_pulse"], samples=_tone_sweep(f0=520.0, f1=1100.0, duration_s=0.22, amp=0.55, noise_mix=0.08))
    if not paths["weapon_pulse_impact"].exists():
        _write_wav(
            paths["weapon_pulse_impact"],
            samples=_tone_sweep(f0=760.0, f1=210.0, duration_s=0.20, amp=0.64, noise_mix=0.18),
        )
    if not paths["grapple_attach"].exists():
        _write_wav(paths["grapple_attach"], samples=_tone_sweep(f0=960.0, f1=420.0, duration_s=0.11, amp=0.44, noise_mix=0.06))
    if not paths["grapple_detach"].exists():
        _write_wav(paths["grapple_detach"], samples=_tone_sweep(f0=360.0, f1=170.0, duration_s=0.10, amp=0.40, noise_mix=0.10))
    if not paths["step_walk"].exists():
        _write_wav(paths["step_walk"], samples=_clicky_step(duration_s=0.11, amp=0.45))
    if not paths["step_run"].exists():
        _write_wav(paths["step_run"], samples=_clicky_step(duration_s=0.09, amp=0.56, seed=13))
    if not paths["race_countdown"].exists():
        _write_wav(paths["race_countdown"], samples=_tone_sweep(f0=720.0, f1=650.0, duration_s=0.16, amp=0.54, noise_mix=0.06))
    if not paths["race_go"].exists():
        _write_wav(paths["race_go"], samples=_tone_sweep(f0=420.0, f1=940.0, duration_s=0.25, amp=0.62, noise_mix=0.06))
    if not paths["race_checkpoint"].exists():
        _write_wav(paths["race_checkpoint"], samples=_tone_sweep(f0=840.0, f1=1120.0, duration_s=0.16, amp=0.50, noise_mix=0.08))
    if not paths["race_finish"].exists():
        _write_wav(paths["race_finish"], samples=_tone_sweep(f0=560.0, f1=1320.0, duration_s=0.28, amp=0.64, noise_mix=0.08))
    return paths


def _load_channel_voices(host, *, key: str, path: Path, voices: int) -> list[Any]:
    out: list[Any] = []
    for _ in range(max(1, int(voices))):
        try:
            snd = host.loader.loadSfx(path.as_posix())
        except Exception:
            snd = None
        if snd is not None:
            try:
                snd.setLoop(False)
            except Exception:
                pass
            out.append(snd)
    return out


def init_runtime(host, *, master_volume: float, sfx_volume: float) -> None:
    st = _runtime(host)
    st.master_volume = _clamp01(master_volume)
    st.sfx_volume = _clamp01(sfx_volume)
    st.enabled = False
    st.channels.clear()
    st.cursor.clear()
    st.step_timer_s = 0.0
    if bool(getattr(getattr(host, "cfg", None), "smoke", False)):
        return
    if getattr(host, "loader", None) is None:
        return
    try:
        paths = _ensure_assets()
    except Exception:
        return

    voice_counts = {
        "weapon_blink": 4,
        "weapon_blink_impact": 3,
        "weapon_slam": 4,
        "weapon_slam_impact": 3,
        "weapon_rocket": 4,
        "weapon_rocket_impact": 4,
        "weapon_pulse": 4,
        "weapon_pulse_impact": 3,
        "grapple_attach": 2,
        "grapple_detach": 2,
        "step_walk": 3,
        "step_run": 3,
        "race_countdown": 2,
        "race_go": 2,
        "race_checkpoint": 2,
        "race_finish": 2,
    }
    any_loaded = False
    for key, path in paths.items():
        voices = _load_channel_voices(host, key=key, path=path, voices=int(voice_counts.get(key, 2)))
        if voices:
            st.channels[key] = voices
            st.cursor[key] = 0
            any_loaded = True
    st.enabled = bool(any_loaded)


def set_master_volume(host, value: float) -> None:
    st = _runtime(host)
    st.master_volume = _clamp01(value)


def set_sfx_volume(host, value: float) -> None:
    st = _runtime(host)
    st.sfx_volume = _clamp01(value)


def _play(host, *, key: str, gain: float = 1.0) -> None:
    st = _runtime(host)
    if not st.enabled:
        return
    voices = st.channels.get(str(key))
    if not voices:
        return
    idx = int(st.cursor.get(str(key), 0)) % max(1, len(voices))
    st.cursor[str(key)] = idx + 1
    snd = voices[idx]
    if snd is None:
        return
    vol = _clamp01(float(st.master_volume) * float(st.sfx_volume) * max(0.0, float(gain)))
    try:
        snd.stop()
    except Exception:
        pass
    try:
        snd.setVolume(float(vol))
    except Exception:
        pass
    try:
        snd.play()
    except Exception:
        pass


def on_weapon_fire(host, *, slot: int) -> None:
    s = int(slot)
    if s == 1:
        _play(host, key="weapon_blink", gain=0.92)
    elif s == 2:
        _play(host, key="weapon_slam", gain=1.00)
    elif s == 3:
        _play(host, key="weapon_rocket", gain=1.05)
    elif s == 4:
        _play(host, key="weapon_pulse", gain=0.94)


def on_weapon_impact(host, *, slot: int, world_hit: bool, impact_power: float = 1.0) -> None:
    s = int(slot)
    power = _clamp01(0.25 + max(0.0, float(impact_power)) * 0.50)
    if s == 1:
        gain = (0.58 if bool(world_hit) else 0.20) * power
        _play(host, key="weapon_blink_impact", gain=gain)
    elif s == 2:
        gain = (0.74 if bool(world_hit) else 0.26) * power
        _play(host, key="weapon_slam_impact", gain=gain)
    elif s == 3:
        gain = (0.76 if bool(world_hit) else 0.42) * power
        _play(host, key="weapon_rocket_impact", gain=gain)
    elif s == 4:
        gain = (0.62 if bool(world_hit) else 0.32) * power
        _play(host, key="weapon_pulse_impact", gain=gain)


def on_grapple_toggle(host, *, attached: bool) -> None:
    _play(host, key=("grapple_attach" if bool(attached) else "grapple_detach"), gain=0.74)


def on_race_countdown(host, *, value: int) -> None:
    _ = int(value)
    _play(host, key="race_countdown", gain=0.72)


def on_race_go(host) -> None:
    _play(host, key="race_go", gain=0.84)


def on_race_checkpoint(host) -> None:
    _play(host, key="race_checkpoint", gain=0.80)


def on_race_finish(host) -> None:
    _play(host, key="race_finish", gain=0.86)


def update_footsteps(host, *, dt: float) -> None:
    st = _runtime(host)
    if not st.enabled:
        return
    if getattr(host, "_mode", "") != "game":
        st.step_timer_s = 0.0
        return
    if bool(getattr(host, "_pause_menu_open", False)) or bool(getattr(host, "_debug_menu_open", False)):
        st.step_timer_s = 0.0
        return
    player = getattr(host, "player", None)
    if player is None or not bool(getattr(player, "grounded", False)):
        st.step_timer_s = 0.0
        return
    vel = getattr(player, "vel", None)
    if vel is None:
        st.step_timer_s = 0.0
        return
    speed = math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y))
    if speed < 0.85:
        st.step_timer_s = 0.0
        return

    st.step_timer_s -= max(0.0, float(dt))
    if st.step_timer_s > 0.0:
        return
    run_speed = max(1.0, float(getattr(getattr(host, "tuning", None), "max_ground_speed", 6.6)))
    run_ratio = max(0.0, min(2.0, speed / run_speed))
    is_run = run_ratio >= 0.90
    if is_run:
        _play(host, key="step_run", gain=0.45 + min(0.30, run_ratio * 0.15))
    else:
        _play(host, key="step_walk", gain=0.36 + min(0.22, run_ratio * 0.14))
    step_period = (0.29 if is_run else 0.41) / max(0.80, min(1.85, run_ratio))
    st.step_timer_s = max(0.10, float(step_period))


__all__ = [
    "init_runtime",
    "on_grapple_toggle",
    "on_race_checkpoint",
    "on_race_countdown",
    "on_race_finish",
    "on_race_go",
    "on_weapon_fire",
    "on_weapon_impact",
    "set_master_volume",
    "set_sfx_volume",
    "update_footsteps",
]
