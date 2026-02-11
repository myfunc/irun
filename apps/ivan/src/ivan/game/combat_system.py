from __future__ import annotations
from dataclasses import dataclass, field
import math

from panda3d.core import LVector3f


@dataclass(frozen=True)
class WeaponSpec:
    slot: int
    name: str
    cooldown_s: float


WEAPON_SPECS: dict[int, WeaponSpec] = {
    1: WeaponSpec(slot=1, name="blink", cooldown_s=0.12),
    2: WeaponSpec(slot=2, name="slam", cooldown_s=0.22),
    3: WeaponSpec(slot=3, name="rocket", cooldown_s=0.62),
    4: WeaponSpec(slot=4, name="pulse", cooldown_s=0.72),
}

_BLINK_REACH = 94.0
_BLINK_REACH_JUMP = 118.0
_BLINK_MIN_CLEARANCE = 0.44
_BLINK_TRAVEL_REF = 36.0

_SLAM_RAY_REACH = 18.0
_SLAM_REBOUND_RANGE = 17.0
_SLAM_REBOUND_BASE = 2.8
_SLAM_REBOUND_SCALE = 5.8
_SLAM_REBOUND_UP_BASE = 1.0
_SLAM_REBOUND_UP_SCALE = 2.6


@dataclass
class CombatRuntimeState:
    active_slot: int = 1
    cooldown_by_slot: dict[int, float] = field(
        default_factory=lambda: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    )
    recent_event: str = ""
    recent_event_left: float = 0.0
    combo_stacks: int = 0
    combo_left: float = 0.0
    combo_boost_left: float = 0.0


@dataclass(frozen=True)
class CombatFireEvent:
    slot: int
    weapon_name: str
    origin: LVector3f
    direction: LVector3f
    impact_pos: LVector3f | None
    world_hit: bool
    impact_power: float = 0.0


def _state(host) -> CombatRuntimeState:
    st = getattr(host, "_combat_runtime", None)
    if isinstance(st, CombatRuntimeState):
        return st
    st = CombatRuntimeState()
    setattr(host, "_combat_runtime", st)
    return st


def init_runtime(host) -> None:
    _state(host)


def reset_runtime(host, *, keep_active_slot: bool = True) -> None:
    st = _state(host)
    active_slot = int(st.active_slot) if keep_active_slot else 1
    st.active_slot = active_slot if active_slot in WEAPON_SPECS else 1
    st.cooldown_by_slot = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    st.recent_event = ""
    st.recent_event_left = 0.0
    st.combo_stacks = 0
    st.combo_left = 0.0
    st.combo_boost_left = 0.0


def _cooldowns_tick(*, st: CombatRuntimeState, dt: float) -> None:
    dt_s = max(0.0, float(dt))
    for slot in tuple(st.cooldown_by_slot.keys()):
        st.cooldown_by_slot[slot] = max(0.0, float(st.cooldown_by_slot.get(slot, 0.0)) - dt_s)
    st.recent_event_left = max(0.0, float(st.recent_event_left) - dt_s)
    st.combo_left = max(0.0, float(st.combo_left) - dt_s)
    st.combo_boost_left = max(0.0, float(st.combo_boost_left) - dt_s)
    if st.recent_event_left <= 0.0:
        st.recent_event = ""
    if st.combo_left <= 0.0:
        st.combo_stacks = 0


def _set_event(st: CombatRuntimeState, *, text: str, hold_s: float = 0.50) -> None:
    st.recent_event = str(text)
    st.recent_event_left = max(0.0, float(hold_s))


def _view_direction(host) -> LVector3f:
    direction = LVector3f(host._view_direction())
    if direction.lengthSquared() > 1e-12:
        direction.normalize()
    return direction


def _camera_origin(host) -> LVector3f:
    if getattr(host, "camera", None) is None or getattr(host, "render", None) is None:
        return LVector3f(0.0, 0.0, 0.0)
    return LVector3f(host.camera.getPos(host.render))


def _ray_hit_point(host, *, origin: LVector3f, direction: LVector3f, reach: float) -> tuple[LVector3f, bool]:
    if getattr(host, "collision", None) is None:
        return (LVector3f(origin + direction * float(reach)), False)
    end = LVector3f(origin + direction * float(reach))
    hit = host.collision.ray_closest(origin, end)
    if not hit.hasHit():
        return (end, False)
    if hasattr(hit, "getHitPos"):
        return (LVector3f(hit.getHitPos()), True)
    frac = max(0.0, min(1.0, float(hit.getHitFraction())))
    return (LVector3f(origin + (end - origin) * frac), True)


def _apply_impulse(host, *, impulse: LVector3f, reason: str) -> None:
    if getattr(host, "player", None) is None:
        return
    if impulse.lengthSquared() <= 1e-12:
        return
    host.player.add_external_impulse(impulse=LVector3f(impulse), reason=str(reason))


def _horizontal_unit(v: LVector3f) -> LVector3f:
    out = LVector3f(float(v.x), float(v.y), 0.0)
    if out.lengthSquared() > 1e-12:
        out.normalize()
    return out


def _normalized01(v: float, *, ref: float) -> float:
    d = max(1e-6, float(ref))
    return max(0.0, min(1.0, float(v) / d))


def _dash_player(host, *, direction: LVector3f, distance: float, min_clearance: float = 0.32) -> float:
    player = getattr(host, "player", None)
    if player is None:
        return 0.0
    dash_dir = LVector3f(direction)
    if dash_dir.lengthSquared() <= 1e-12:
        return 0.0
    dash_dir.normalize()
    start = LVector3f(player.pos)
    target = LVector3f(start + dash_dir * max(0.0, float(distance)))
    if getattr(host, "collision", None) is not None:
        hit = host.collision.ray_closest(start, target)
        if hit.hasHit():
            if hasattr(hit, "getHitPos"):
                hit_pos = LVector3f(hit.getHitPos())
            else:
                frac = max(0.0, min(1.0, float(hit.getHitFraction())))
                hit_pos = start + (target - start) * frac
            to_hit = LVector3f(hit_pos - start)
            hit_dist = float(to_hit.length())
            travel = max(0.0, hit_dist - max(0.05, float(min_clearance)))
            target = LVector3f(start + dash_dir * travel)
    moved_vec = LVector3f(target - start)
    moved = float(moved_vec.length())
    if moved > 1e-6:
        player.pos = LVector3f(target)
    return moved


def _slam_rebound_factor(*, impact_dist: float, world_hit: bool) -> float:
    if not bool(world_hit):
        return 0.0
    return max(0.0, min(1.0, 1.0 - (max(0.0, float(impact_dist)) / _SLAM_REBOUND_RANGE)))


def _register_combo_shot(st: CombatRuntimeState) -> int:
    if float(st.combo_left) > 0.0:
        st.combo_stacks = min(6, int(st.combo_stacks) + 1)
    else:
        st.combo_stacks = 1
    st.combo_left = 1.35
    st.combo_boost_left = 0.95
    return int(st.combo_stacks)


def _apply_combo_sustain(host, *, st: CombatRuntimeState, dt: float, prefer_dir: LVector3f) -> None:
    if float(st.combo_boost_left) <= 0.0:
        return
    player = getattr(host, "player", None)
    if player is None:
        return
    hvel = _horizontal_unit(player.vel)
    if hvel.lengthSquared() <= 1e-12:
        hvel = _horizontal_unit(prefer_dir)
    if hvel.lengthSquared() <= 1e-12:
        return
    scale = 1.0 + max(0, int(st.combo_stacks) - 1) * 0.28
    _apply_impulse(
        host,
        impulse=hvel * (max(0.0, float(dt)) * 1.70 * scale),
        reason="weapon.combo.sustain",
    )


def _fire_blink(
    host,
    *,
    origin: LVector3f,
    direction: LVector3f,
    jump_held: bool,
    slide_held: bool,
) -> CombatFireEvent:
    # Slot 1: line-of-sight blink teleport to aim point.
    player = getattr(host, "player", None)
    reach = _BLINK_REACH_JUMP if bool(jump_held) else _BLINK_REACH
    impact, world_hit = _ray_hit_point(host, origin=origin, direction=direction, reach=reach)
    target = LVector3f(impact)
    if bool(world_hit):
        target -= LVector3f(direction) * 0.72
    if bool(slide_held):
        target.z -= 0.35

    moved = 0.0
    if player is not None:
        to_target = LVector3f(target - player.pos)
        travel = float(to_target.length())
        if travel > 1e-6:
            moved = _dash_player(
                host,
                direction=to_target,
                distance=travel,
                min_clearance=_BLINK_MIN_CLEARANCE,
            )
        target = LVector3f(player.pos)

    travel_t = _normalized01(moved, ref=_BLINK_TRAVEL_REF)
    impulse = LVector3f(direction) * (0.34 + 0.62 * travel_t)
    impulse.z += 0.10 + 0.24 * travel_t
    if bool(jump_held):
        impulse.z += 0.46 + 0.24 * travel_t
    if moved > 10.0:
        impulse.z += 0.18
    if bool(slide_held):
        strafe = _horizontal_unit(LVector3f(-direction.y, direction.x, 0.0))
        impulse += strafe * (0.36 + 0.30 * travel_t)
    _apply_impulse(host, impulse=impulse, reason="weapon.blink.teleport")
    return CombatFireEvent(
        slot=1,
        weapon_name="blink",
        origin=LVector3f(origin),
        direction=LVector3f(direction),
        impact_pos=LVector3f(target),
        world_hit=bool(world_hit),
        impact_power=0.46 + min(1.00, moved * 0.034),
    )


def _fire_slam(
    host,
    *,
    origin: LVector3f,
    direction: LVector3f,
    jump_held: bool,
    slide_held: bool,
) -> CombatFireEvent:
    # Slot 2: aggressive aim-driven boost shot (great for diagonal jump lines).
    player = getattr(host, "player", None)
    move_speed = 0.0
    if player is not None:
        vel = getattr(player, "vel", None)
        if vel is not None:
            move_speed = math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y))
    carry_bonus = min(2.8, move_speed * 0.16)
    impulse = LVector3f(-direction * (7.8 + carry_bonus))
    impulse.z += 2.8
    if float(direction.z) < -0.25:
        impulse.z += abs(float(direction.z)) * 9.4
    if bool(player is not None and getattr(player, "grounded", False)):
        impulse.z += 2.8
    else:
        impulse.z += 1.1
    if bool(jump_held):
        impulse += LVector3f(direction * 3.1)
        impulse.z += 0.30
    if bool(slide_held):
        impulse += _horizontal_unit(LVector3f(-direction.y, direction.x, 0.0)) * 1.9
    _apply_impulse(host, impulse=impulse, reason="weapon.slam")
    impact, world_hit = _ray_hit_point(host, origin=origin, direction=direction, reach=_SLAM_RAY_REACH)
    impact_dist = float((LVector3f(impact) - LVector3f(origin)).length())
    rebound_t = _slam_rebound_factor(impact_dist=impact_dist, world_hit=world_hit)
    if rebound_t > 0.0:
        rebound = LVector3f(-direction) * (_SLAM_REBOUND_BASE + _SLAM_REBOUND_SCALE * rebound_t)
        rebound.z += _SLAM_REBOUND_UP_BASE + _SLAM_REBOUND_UP_SCALE * rebound_t
        _apply_impulse(host, impulse=rebound, reason="weapon.slam.rebound")
    return CombatFireEvent(
        slot=2,
        weapon_name="slam",
        origin=LVector3f(origin),
        direction=LVector3f(direction),
        impact_pos=LVector3f(impact),
        world_hit=bool(world_hit),
        impact_power=0.78 + max(0.0, min(0.72, abs(float(direction.z)) * 0.70)) + rebound_t * 0.62,
    )


def _fire_rocket(host, *, origin: LVector3f, direction: LVector3f) -> CombatFireEvent:
    player = getattr(host, "player", None)
    if player is None:
        return CombatFireEvent(
            slot=3,
            weapon_name="rocket",
            origin=LVector3f(origin),
            direction=LVector3f(direction),
            impact_pos=None,
            world_hit=False,
            impact_power=0.28,
        )
    impact, world_hit = _ray_hit_point(host, origin=origin, direction=direction, reach=70.0)
    player_center = LVector3f(
        float(player.pos.x),
        float(player.pos.y),
        float(player.pos.z) + float(host.tuning.player_half_height) * 0.40,
    )
    to_player = LVector3f(player_center - impact)
    dist = float(to_player.length())
    blast_radius = 9.6
    if dist > blast_radius:
        if world_hit:
            _apply_impulse(host, impulse=LVector3f(-direction * 1.2), reason="weapon.rocket.recoil")
        return CombatFireEvent(
            slot=3,
            weapon_name="rocket",
            origin=LVector3f(origin),
            direction=LVector3f(direction),
            impact_pos=LVector3f(impact),
            world_hit=bool(world_hit),
            impact_power=(0.68 if bool(world_hit) else 0.26),
        )

    if dist > 1e-9:
        to_player.normalize()
    else:
        to_player = LVector3f(0.0, 0.0, 1.0)
    falloff = max(0.0, 1.0 - (dist / blast_radius))
    impulse = LVector3f(to_player) * (12.0 + 24.0 * falloff)
    impulse.z += 4.4 + 8.8 * falloff
    _apply_impulse(host, impulse=impulse, reason="weapon.rocketjump")
    return CombatFireEvent(
        slot=3,
        weapon_name="rocket",
        origin=LVector3f(origin),
        direction=LVector3f(direction),
        impact_pos=LVector3f(impact),
        world_hit=bool(world_hit),
        impact_power=1.05 + (falloff * 0.95),
    )


def _fire_pulse(host, *, origin: LVector3f, direction: LVector3f) -> CombatFireEvent:
    # Slot 4: burst-dash launcher to quickly re-route movement lines.
    player = getattr(host, "player", None)
    if player is None:
        return CombatFireEvent(
            slot=4,
            weapon_name="pulse",
            origin=LVector3f(origin),
            direction=LVector3f(direction),
            impact_pos=None,
            world_hit=False,
            impact_power=0.34,
        )
    up = 2.8 if bool(player.grounded) else 1.65
    impulse = LVector3f(direction * 9.4)
    impulse.z += up
    _apply_impulse(host, impulse=impulse, reason="weapon.pulse")
    impact, world_hit = _ray_hit_point(host, origin=origin, direction=direction, reach=36.0)
    return CombatFireEvent(
        slot=4,
        weapon_name="pulse",
        origin=LVector3f(origin),
        direction=LVector3f(direction),
        impact_pos=LVector3f(impact),
        world_hit=bool(world_hit),
        impact_power=(0.78 if bool(world_hit) else 0.44),
    )


def _switch_weapon(st: CombatRuntimeState, *, slot: int) -> bool:
    s = int(slot)
    if s not in WEAPON_SPECS:
        return False
    if int(st.active_slot) == s:
        return False
    st.active_slot = s
    return True


def tick(host, *, cmd, dt: float) -> CombatFireEvent | None:
    st = _state(host)
    _cooldowns_tick(st=st, dt=dt)
    selected_slot = int(getattr(cmd, "weapon_slot_select", 0) or 0)
    if _switch_weapon(st, slot=selected_slot):
        _set_event(st, text=f"slot {st.active_slot}: {WEAPON_SPECS[st.active_slot].name}", hold_s=0.65)

    if getattr(host, "player", None) is None:
        return None
    if bool(getattr(host, "_net_connected", False)):
        # Multiplayer is currently authoritative-server-only for gameplay actions.
        return None
    direction = _view_direction(host)
    _apply_combo_sustain(host, st=st, dt=float(dt), prefer_dir=direction)
    if not bool(getattr(cmd, "mouse_left_held", False)):
        return None

    slot = int(st.active_slot)
    spec = WEAPON_SPECS.get(slot)
    if spec is None:
        return None
    if float(st.cooldown_by_slot.get(slot, 0.0)) > 0.0:
        return None

    if direction.lengthSquared() <= 1e-12:
        return None
    origin = _camera_origin(host)
    fired: CombatFireEvent | None = None
    jump_held = bool(getattr(cmd, "jump_held", False))
    slide_held = bool(getattr(cmd, "slide_pressed", False))

    if slot == 1:
        fired = _fire_blink(
            host,
            origin=origin,
            direction=direction,
            jump_held=jump_held,
            slide_held=slide_held,
        )
        _set_event(st, text="blink step")
    elif slot == 2:
        fired = _fire_slam(
            host,
            origin=origin,
            direction=direction,
            jump_held=jump_held,
            slide_held=slide_held,
        )
        if bool(fired.world_hit) and float(fired.impact_power) >= 1.22:
            _set_event(st, text="slam rebound")
        else:
            _set_event(st, text="slam launch")
    elif slot == 3:
        fired = _fire_rocket(host, origin=origin, direction=direction)
        _set_event(st, text="rocket burst")
    elif slot == 4:
        fired = _fire_pulse(host, origin=origin, direction=direction)
        _set_event(st, text="pulse dash")

    st.cooldown_by_slot[slot] = max(0.0, float(spec.cooldown_s))
    combo = _register_combo_shot(st)
    if combo >= 4:
        boost = _horizontal_unit(direction) * (0.55 * float(combo))
        boost.z += 0.18 * float(combo)
        _apply_impulse(host, impulse=boost, reason="weapon.combo.burst")
        _set_event(st, text=f"combo x{combo} burst", hold_s=0.55)
    return fired


def status_fragment(host) -> str:
    st = _state(host)
    slot = int(st.active_slot)
    spec = WEAPON_SPECS.get(slot, WEAPON_SPECS[1])
    cd = max(0.0, float(st.cooldown_by_slot.get(slot, 0.0)))
    out = f"weapon: {slot}-{spec.name} cd:{cd:.2f}s"
    if int(st.combo_stacks) > 0 and float(st.combo_left) > 0.0:
        out = f"{out} combo:x{int(st.combo_stacks)}"
    if st.recent_event:
        out = f"{out} | {st.recent_event}"
    return out


__all__ = [
    "CombatFireEvent",
    "CombatRuntimeState",
    "WEAPON_SPECS",
    "init_runtime",
    "reset_runtime",
    "status_fragment",
    "tick",
]
