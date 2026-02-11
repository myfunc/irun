from __future__ import annotations

import math
from types import SimpleNamespace

from panda3d.core import LVector3f

from ivan.game import transport_system


class _FakePlayer:
    def __init__(self) -> None:
        self.pos = LVector3f(0.0, 0.0, 2.0)
        self.vel = LVector3f(0.0, 0.0, 0.0)
        self.grounded = True
        self.last_reason = ""
        self.detach_count = 0
        self.step_count = 0

    def detach_grapple(self) -> None:
        self.detach_count += 1

    def set_external_velocity(self, *, vel: LVector3f, reason: str = "external") -> None:
        self.vel = LVector3f(vel)
        self.last_reason = str(reason)

    def step_with_intent(self, *, dt: float, intent, yaw_deg: float, pitch_deg: float = 0.0) -> None:
        _ = dt
        _ = yaw_deg
        _ = pitch_deg
        self.step_count += 1
        wish = LVector3f(intent.wish_dir)
        if wish.lengthSquared() > 1e-12:
            wish.normalize()
        self.vel = wish * 4.0
        self.grounded = True


def _make_host() -> SimpleNamespace:
    return SimpleNamespace(
        _yaw=0.0,
        _pitch=0.0,
        player=_FakePlayer(),
        tuning=SimpleNamespace(max_ground_speed=7.0, autojump_enabled=False),
        _wish_direction_from_axes=lambda move_forward, move_right: LVector3f(float(move_right), float(move_forward), 0.0),
    )


def test_handle_slot_select_switches_between_transport_modes() -> None:
    host = _make_host()
    transport_system.init_runtime(host)

    transport_system.handle_slot_select(host, slot=5)
    assert transport_system.active_slot(host) == 5

    transport_system.handle_slot_select(host, slot=6)
    assert transport_system.active_slot(host) == 6

    transport_system.handle_slot_select(host, slot=2)
    assert transport_system.active_slot(host) == 0


def test_planer_tick_applies_flight_velocity_and_uses_qe_roll() -> None:
    host = _make_host()
    transport_system.init_runtime(host)
    transport_system.handle_slot_select(host, slot=5)
    cmd = SimpleNamespace(
        key_w_held=True,
        key_s_held=False,
        key_a_held=False,
        key_d_held=True,
        key_q_held=False,
        key_e_held=True,
        arrow_up_held=True,
        arrow_down_held=False,
        arrow_left_held=False,
        arrow_right_held=True,
        move_forward=0,
        move_right=0,
        jump_pressed=False,
        jump_held=False,
        slide_pressed=False,
    )

    consumed = transport_system.tick(host, cmd=cmd, dt=1.0 / 60.0)

    assert consumed is True
    assert host.player.last_reason == "transport.planer"
    assert host.player.grounded is False
    assert math.sqrt(float(host.player.vel.x) * float(host.player.vel.x) + float(host.player.vel.y) * float(host.player.vel.y)) > 5.0
    assert float(host._pitch) > 0.0


def test_skateboard_tick_boosts_horizontal_speed() -> None:
    host = _make_host()
    transport_system.init_runtime(host)
    transport_system.handle_slot_select(host, slot=6)
    cmd = SimpleNamespace(
        move_forward=1,
        move_right=0,
        jump_pressed=False,
        jump_held=False,
        slide_pressed=False,
    )

    consumed = transport_system.tick(host, cmd=cmd, dt=1.0 / 60.0)

    hspeed = math.sqrt(float(host.player.vel.x) * float(host.player.vel.x) + float(host.player.vel.y) * float(host.player.vel.y))
    assert consumed is True
    assert host.player.step_count == 1
    assert host.player.last_reason == "transport.skateboard"
    assert hspeed > 4.0
