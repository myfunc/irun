from __future__ import annotations

from types import SimpleNamespace

from ivan.game import audio_system


def test_weapon_impact_routes_blink_and_slam_channels(monkeypatch) -> None:
    calls: list[tuple[str, float]] = []

    def _capture(_host, *, key: str, gain: float = 1.0) -> None:
        calls.append((str(key), float(gain)))

    monkeypatch.setattr(audio_system, "_play", _capture)
    host = SimpleNamespace()

    audio_system.on_weapon_impact(host, slot=1, world_hit=True, impact_power=1.2)
    audio_system.on_weapon_impact(host, slot=2, world_hit=True, impact_power=1.2)

    assert calls[0][0] == "weapon_blink_impact"
    assert calls[1][0] == "weapon_slam_impact"
    assert calls[1][1] > calls[0][1]


def test_weapon_impact_world_hit_is_louder_than_miss_for_slots_1_and_2(monkeypatch) -> None:
    calls: list[tuple[str, float]] = []

    def _capture(_host, *, key: str, gain: float = 1.0) -> None:
        calls.append((str(key), float(gain)))

    monkeypatch.setattr(audio_system, "_play", _capture)
    host = SimpleNamespace()

    audio_system.on_weapon_impact(host, slot=1, world_hit=True, impact_power=1.0)
    audio_system.on_weapon_impact(host, slot=1, world_hit=False, impact_power=1.0)
    audio_system.on_weapon_impact(host, slot=2, world_hit=True, impact_power=1.0)
    audio_system.on_weapon_impact(host, slot=2, world_hit=False, impact_power=1.0)

    blink_hit = calls[0][1]
    blink_miss = calls[1][1]
    slam_hit = calls[2][1]
    slam_miss = calls[3][1]

    assert blink_hit > blink_miss > 0.0
    assert slam_hit > slam_miss > 0.0
