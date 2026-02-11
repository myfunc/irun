from __future__ import annotations

from types import SimpleNamespace

from panda3d.core import LVector3f

from ivan.game import combat_system


class _FakeHit:
    def __init__(self, *, has_hit: bool, pos: LVector3f) -> None:
        self._has_hit = bool(has_hit)
        self._pos = LVector3f(pos)

    def hasHit(self) -> bool:
        return bool(self._has_hit)

    def getHitPos(self) -> LVector3f:
        return LVector3f(self._pos)

    def getHitFraction(self) -> float:
        return 0.5


class _FakeCollision:
    def __init__(self, *, hit: _FakeHit) -> None:
        self._hit = hit

    def ray_closest(self, _origin: LVector3f, _end: LVector3f) -> _FakeHit:
        return self._hit


class _FakeCamera:
    def __init__(self, pos: LVector3f) -> None:
        self._pos = LVector3f(pos)

    def getPos(self, _render) -> LVector3f:
        return LVector3f(self._pos)


class _FakePlayer:
    def __init__(self, *, pos: LVector3f, grounded: bool = True) -> None:
        self.pos = LVector3f(pos)
        self.grounded = bool(grounded)
        self.impulses: list[LVector3f] = []

    def add_external_impulse(self, *, impulse: LVector3f, reason: str = "test") -> None:
        _ = reason
        self.impulses.append(LVector3f(impulse))


def _make_host(*, direction: LVector3f, hit_pos: LVector3f, grounded: bool = True):
    return SimpleNamespace(
        _net_connected=False,
        _view_direction=lambda: LVector3f(direction),
        camera=_FakeCamera(LVector3f(0.0, 0.0, 1.7)),
        render=object(),
        collision=_FakeCollision(hit=_FakeHit(has_hit=True, pos=hit_pos)),
        player=_FakePlayer(pos=LVector3f(0.0, 0.0, 1.2), grounded=grounded),
        tuning=SimpleNamespace(player_half_height=1.05),
    )


def test_tick_switches_weapon_slot_from_input() -> None:
    host = _make_host(direction=LVector3f(0.0, 1.0, 0.0), hit_pos=LVector3f(0.0, 6.0, 1.2))
    ev = combat_system.tick(
        host,
        cmd=SimpleNamespace(weapon_slot_select=4, mouse_left_held=False),
        dt=1.0 / 60.0,
    )
    assert ev is None
    assert host._combat_runtime.active_slot == 4


def test_rocket_slot_applies_upward_impulse_near_impact() -> None:
    host = _make_host(direction=LVector3f(0.0, 0.0, -1.0), hit_pos=LVector3f(0.0, 0.0, 0.0))
    ev = combat_system.tick(
        host,
        cmd=SimpleNamespace(weapon_slot_select=3, mouse_left_held=True),
        dt=1.0 / 60.0,
    )
    assert ev is not None
    assert ev.slot == 3
    assert ev.weapon_name == "rocket"
    assert ev.impact_pos is not None
    assert host.player.impulses
    impulse = host.player.impulses[-1]
    assert impulse.z > 0.0


def test_pulse_slot_applies_forward_boost() -> None:
    host = _make_host(direction=LVector3f(0.0, 1.0, 0.0), hit_pos=LVector3f(0.0, 12.0, 1.0))
    ev = combat_system.tick(
        host,
        cmd=SimpleNamespace(weapon_slot_select=4, mouse_left_held=True),
        dt=1.0 / 60.0,
    )
    assert ev is not None
    assert ev.slot == 4
    assert ev.weapon_name == "pulse"
    assert host.player.impulses
    impulse = host.player.impulses[-1]
    assert impulse.y > 0.0
    assert impulse.z > 0.0
