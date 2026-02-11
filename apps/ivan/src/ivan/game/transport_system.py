from __future__ import annotations

from dataclasses import dataclass
import math

from panda3d.core import LVector3f

from ivan.physics.motion.intent import MotionIntent


TRANSPORT_SLOT_PLANER = 5
TRANSPORT_SLOT_SKATEBOARD = 6
_TRANSPORT_SLOTS = {TRANSPORT_SLOT_PLANER, TRANSPORT_SLOT_SKATEBOARD}


@dataclass
class TransportRuntimeState:
    active_slot: int = 0
    planer_speed: float = 12.5
    planer_roll_deg: float = 0.0
    planer_stall_left: float = 0.0


def _state(host) -> TransportRuntimeState:
    st = getattr(host, "_transport_runtime", None)
    if isinstance(st, TransportRuntimeState):
        return st
    st = TransportRuntimeState()
    setattr(host, "_transport_runtime", st)
    return st


def init_runtime(host) -> None:
    _state(host)


def reset_runtime(host) -> None:
    st = _state(host)
    st.active_slot = 0
    st.planer_speed = 12.5
    st.planer_roll_deg = 0.0
    st.planer_stall_left = 0.0


def _clamp(v: float, lo: float, hi: float) -> float:
    if float(v) < float(lo):
        return float(lo)
    if float(v) > float(hi):
        return float(hi)
    return float(v)


def _axis(*, neg: bool, pos: bool) -> float:
    return float(int(bool(pos)) - int(bool(neg)))


def _view_direction(*, yaw_deg: float, pitch_deg: float) -> LVector3f:
    h = math.radians(float(yaw_deg))
    p = math.radians(float(pitch_deg))
    out = LVector3f(
        -math.sin(h) * math.cos(p),
        math.cos(h) * math.cos(p),
        math.sin(p),
    )
    if out.lengthSquared() > 1e-12:
        out.normalize()
    return out


def _horizontal_unit(v: LVector3f) -> LVector3f:
    out = LVector3f(float(v.x), float(v.y), 0.0)
    if out.lengthSquared() > 1e-12:
        out.normalize()
    return out


def _activate_planer(host, *, st: TransportRuntimeState) -> None:
    st.active_slot = TRANSPORT_SLOT_PLANER
    st.planer_roll_deg = 0.0
    st.planer_stall_left = 0.0
    player = getattr(host, "player", None)
    if player is not None:
        hspeed = math.sqrt(float(player.vel.x) * float(player.vel.x) + float(player.vel.y) * float(player.vel.y))
        st.planer_speed = _clamp(max(8.5, hspeed + 1.6), 8.5, 30.0)
        player.detach_grapple()
    host._pitch = _clamp(float(getattr(host, "_pitch", 0.0)), -52.0, 35.0)


def _activate_skateboard(host, *, st: TransportRuntimeState) -> None:
    st.active_slot = TRANSPORT_SLOT_SKATEBOARD
    st.planer_roll_deg = 0.0
    st.planer_stall_left = 0.0
    player = getattr(host, "player", None)
    if player is not None:
        player.detach_grapple()


def handle_slot_select(host, *, slot: int) -> None:
    st = _state(host)
    s = int(slot)
    if s == TRANSPORT_SLOT_PLANER:
        _activate_planer(host, st=st)
        return
    if s == TRANSPORT_SLOT_SKATEBOARD:
        _activate_skateboard(host, st=st)
        return
    if s in (1, 2, 3, 4):
        st.active_slot = 0
        st.planer_roll_deg = 0.0
        st.planer_stall_left = 0.0


def active_slot(host) -> int:
    return int(_state(host).active_slot)


def _tick_planer(host, *, cmd, dt: float) -> None:
    st = _state(host)
    player = getattr(host, "player", None)
    if player is None:
        return
    step_dt = max(0.0, float(dt))
    if step_dt <= 0.0:
        return

    throttle = _axis(neg=bool(getattr(cmd, "key_s_held", False)), pos=bool(getattr(cmd, "key_w_held", False)))
    turn = _axis(neg=bool(getattr(cmd, "key_a_held", False)), pos=bool(getattr(cmd, "key_d_held", False)))
    yaw_arrow = _axis(neg=bool(getattr(cmd, "arrow_left_held", False)), pos=bool(getattr(cmd, "arrow_right_held", False)))
    pitch_input = _axis(neg=bool(getattr(cmd, "arrow_down_held", False)), pos=bool(getattr(cmd, "arrow_up_held", False)))
    roll_input = _axis(neg=bool(getattr(cmd, "key_q_held", False)), pos=bool(getattr(cmd, "key_e_held", False)))

    speed = float(st.planer_speed)
    speed += throttle * 19.0 * step_dt
    cruise = 14.5
    speed += (cruise - speed) * min(1.0, step_dt * 0.45)
    speed = _clamp(speed, 6.5, 32.0)
    st.planer_speed = speed

    yaw_rate = 44.0 + speed * 0.85
    yaw_input = (turn * 0.70) + yaw_arrow
    host._yaw += float(yaw_input) * yaw_rate * step_dt

    pitch_rate = 58.0
    host._pitch = _clamp(float(host._pitch) + (pitch_input * pitch_rate * step_dt), -55.0, 40.0)

    target_roll = (roll_input * 52.0) + (turn * 22.0)
    st.planer_roll_deg += (target_roll - float(st.planer_roll_deg)) * min(1.0, step_dt * 4.7)
    host._yaw += float(st.planer_roll_deg) * 0.22 * step_dt

    forward = _view_direction(yaw_deg=float(host._yaw), pitch_deg=float(host._pitch))
    speed_t = _clamp((speed - 7.0) / 10.0, 0.0, 1.0)
    lift = (2.6 + speed_t * 8.2) * max(0.08, 1.0 - max(0.0, float(forward.z)))
    sink = 7.6 - (speed_t * 4.6)
    vel = LVector3f(forward * speed)
    vel.z += lift - sink

    if speed < 9.0 and float(host._pitch) > 10.0:
        vel.z -= (9.0 - speed) * 1.25
        st.planer_stall_left = _clamp(float(st.planer_stall_left) + step_dt, 0.0, 0.65)
    else:
        st.planer_stall_left = _clamp(float(st.planer_stall_left) - step_dt * 0.70, 0.0, 0.65)
    if float(st.planer_stall_left) > 0.0:
        vel.z -= float(st.planer_stall_left) * 2.2

    player.set_external_velocity(vel=LVector3f(vel), reason="transport.planer")
    player.pos += player.vel * step_dt
    player.grounded = False


def _tick_skateboard(host, *, cmd, dt: float) -> None:
    player = getattr(host, "player", None)
    if player is None:
        return
    step_dt = max(0.0, float(dt))
    if step_dt <= 0.0:
        return

    move_forward = int(getattr(cmd, "move_forward", 0))
    move_right = int(getattr(cmd, "move_right", 0))
    wish = host._wish_direction_from_axes(move_forward=move_forward, move_right=move_right)
    jump_requested = bool(getattr(cmd, "jump_pressed", False))
    if bool(getattr(host.tuning, "autojump_enabled", False)) and bool(getattr(cmd, "jump_held", False)) and bool(player.grounded):
        jump_requested = True
    player.step_with_intent(
        dt=step_dt,
        intent=MotionIntent(
            wish_dir=LVector3f(wish),
            jump_requested=bool(jump_requested),
            slide_requested=bool(getattr(cmd, "slide_pressed", False)),
        ),
        yaw_deg=float(host._yaw),
        pitch_deg=float(host._pitch),
    )

    hvel = LVector3f(float(player.vel.x), float(player.vel.y), 0.0)
    hspeed = math.sqrt(float(hvel.x) * float(hvel.x) + float(hvel.y) * float(hvel.y))
    moving = move_forward != 0 or move_right != 0

    if moving:
        steer = _horizontal_unit(LVector3f(wish))
        if steer.lengthSquared() <= 1e-12:
            steer = _horizontal_unit(LVector3f(hvel))
        if steer.lengthSquared() > 1e-12:
            target_speed = max(2.0, float(host.tuning.max_ground_speed)) * 1.60
            accel = 20.0 if bool(player.grounded) else 9.0
            gain = min(max(0.0, target_speed - hspeed), accel * step_dt)
            hvel += steer * gain
    elif bool(player.grounded):
        # Keep skateboard coasting readable, but still controllable on release.
        hvel *= max(0.0, 1.0 - (step_dt * 0.40))

    player.set_external_velocity(vel=LVector3f(float(hvel.x), float(hvel.y), float(player.vel.z)), reason="transport.skateboard")


def tick(host, *, cmd, dt: float) -> bool:
    st = _state(host)
    slot = int(st.active_slot)
    if slot == TRANSPORT_SLOT_PLANER:
        _tick_planer(host, cmd=cmd, dt=float(dt))
        return True
    if slot == TRANSPORT_SLOT_SKATEBOARD:
        _tick_skateboard(host, cmd=cmd, dt=float(dt))
        return True
    return False


def status_fragment(host) -> str:
    st = _state(host)
    slot = int(st.active_slot)
    if slot == TRANSPORT_SLOT_PLANER:
        return f"transport: planer spd:{float(st.planer_speed):.1f} roll:{float(st.planer_roll_deg):.0f}"
    if slot == TRANSPORT_SLOT_SKATEBOARD:
        return "transport: skateboard"
    return "transport: none"


def is_transport_slot(slot: int) -> bool:
    return int(slot) in _TRANSPORT_SLOTS


__all__ = [
    "TransportRuntimeState",
    "TRANSPORT_SLOT_PLANER",
    "TRANSPORT_SLOT_SKATEBOARD",
    "active_slot",
    "handle_slot_select",
    "init_runtime",
    "is_transport_slot",
    "reset_runtime",
    "status_fragment",
    "tick",
]
