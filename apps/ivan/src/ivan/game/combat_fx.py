from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from panda3d.core import LVector3f, NodePath, PNMImage, Texture

from .combat_system import CombatFireEvent


@dataclass(frozen=True)
class _AnimSpec:
    duration_s: float
    back: float
    up: float
    roll_deg: float
    pitch_deg: float


@dataclass(frozen=True)
class _ColorSpec:
    r: float
    g: float
    b: float


@dataclass
class _Particle:
    np: NodePath
    vel: LVector3f
    life_s: float
    color: _ColorSpec
    start_scale: float
    end_scale: float
    gravity: float
    drag: float
    spin_deg_per_s: float
    age_s: float = 0.0


@dataclass
class _Tracer:
    np: NodePath
    start: LVector3f
    end: LVector3f
    life_s: float
    color: _ColorSpec
    start_scale: float
    end_scale: float
    age_s: float = 0.0


@dataclass
class _Shockwave:
    np: NodePath
    pos: LVector3f
    life_s: float
    color: _ColorSpec
    start_scale: float
    end_scale: float
    thickness: float
    spin_deg_per_s: float
    age_s: float = 0.0


@dataclass
class CombatFxRuntime:
    root_np: NodePath | None = None
    particles_np: NodePath | None = None
    view_np: NodePath | None = None
    weapon_np: NodePath | None = None
    weapon_generic_np: NodePath | None = None
    weapon_rocket_np: NodePath | None = None
    weapon_rocket_metal_parts: list[NodePath] = field(default_factory=list)
    weapon_rocket_wood_parts: list[NodePath] = field(default_factory=list)
    weapon_rocket_accent_parts: list[NodePath] = field(default_factory=list)
    particle_template_np: NodePath | None = None
    tracer_template_np: NodePath | None = None
    shockwave_template_np: NodePath | None = None
    particles: list[_Particle] = field(default_factory=list)
    tracers: list[_Tracer] = field(default_factory=list)
    shockwaves: list[_Shockwave] = field(default_factory=list)
    anim_slot: int = 1
    anim_left_s: float = 0.0
    anim_duration_s: float = 0.0
    view_punch_left_s: float = 0.0
    view_punch_duration_s: float = 0.0
    view_punch_amp: float = 0.0
    view_punch_phase: float = 0.0
    rng: random.Random = field(default_factory=random.Random)


_BASE_WEAPON_POS = LVector3f(0.36, 0.98, -0.27)
_BASE_WEAPON_HPR = (0.0, -2.0, 0.0)
_BASE_VIEW_POS = LVector3f(0.0, 0.0, 0.0)
_BASE_VIEW_HPR = (0.0, 0.0, 0.0)

_ROCKET_METAL_COLOR = _ColorSpec(0.58, 0.56, 0.52)
_ROCKET_METAL_DARK = _ColorSpec(0.42, 0.37, 0.32)
_ROCKET_WOOD_COLOR = _ColorSpec(0.54, 0.33, 0.17)
_ROCKET_WOOD_DARK = _ColorSpec(0.33, 0.20, 0.11)
_ROCKET_ACCENT_COLOR = _ColorSpec(0.20, 0.19, 0.18)

_SLOT_COLORS: dict[int, _ColorSpec] = {
    1: _ColorSpec(0.16, 0.92, 1.0),   # blink
    2: _ColorSpec(1.0, 0.67, 0.20),   # slam
    3: _ColorSpec(1.0, 0.30, 0.14),   # rocket
    4: _ColorSpec(0.38, 1.0, 0.56),   # pulse
}

_ANIM_SPECS: dict[int, _AnimSpec] = {
    1: _AnimSpec(duration_s=0.13, back=0.09, up=0.022, roll_deg=7.8, pitch_deg=8.0),
    2: _AnimSpec(duration_s=0.16, back=0.12, up=0.036, roll_deg=10.8, pitch_deg=11.5),
    3: _AnimSpec(duration_s=0.17, back=0.11, up=0.030, roll_deg=7.5, pitch_deg=9.4),
    4: _AnimSpec(duration_s=0.18, back=0.06, up=0.040, roll_deg=10.0, pitch_deg=5.4),
}


def _make_weapon_texture() -> Texture:
    img = PNMImage(256, 128, 4)
    for y in range(128):
        for x in range(256):
            u = float(x) / 255.0
            v = float(y) / 127.0
            band = 0.12 * math.sin((u * 19.0) + (v * 11.0))
            stripe = 0.18 if (x // 14) % 2 == 0 else -0.06
            panel = 0.08 if (y // 24) % 2 == 0 else -0.03
            g = max(0.0, min(1.0, 0.38 + band + stripe + panel))
            b = max(0.0, min(1.0, 0.30 + band * 0.55 + stripe * 0.45))
            r = max(0.0, min(1.0, 0.30 + band * 0.40 + panel * 0.50))
            a = 0.98
            img.setXelA(x, y, r, g, b, a)
    tex = Texture("combat-weapon-tech")
    tex.load(img)
    tex.setWrapU(Texture.WMRepeat)
    tex.setWrapV(Texture.WMRepeat)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _make_weapon_metal_texture() -> Texture:
    img = PNMImage(256, 128, 4)
    for y in range(128):
        for x in range(256):
            u = float(x) / 255.0
            v = float(y) / 127.0
            grain = 0.10 * math.sin((u * 28.0) + (v * 2.8))
            brushed = 0.07 * math.sin((u * 74.0) + (v * 1.7))
            weld = 0.09 if (x % 57) < 2 else 0.0
            val = max(0.0, min(1.0, 0.48 + grain + brushed - weld))
            cool = max(0.0, min(1.0, val * 0.94))
            warm = max(0.0, min(1.0, val * 0.88))
            img.setXelA(x, y, warm, cool, cool * 0.95, 0.98)
    tex = Texture("combat-weapon-metal")
    tex.load(img)
    tex.setWrapU(Texture.WMRepeat)
    tex.setWrapV(Texture.WMRepeat)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _make_weapon_wood_texture() -> Texture:
    img = PNMImage(256, 128, 4)
    for y in range(128):
        for x in range(256):
            u = float(x) / 255.0
            v = float(y) / 127.0
            rings = 0.11 * math.sin((u * 17.0) + (v * 4.6))
            fibers = 0.07 * math.sin((u * 55.0) + (v * 3.1) + 0.7)
            knot = 0.06 * math.cos((u * 9.0) - (v * 5.0))
            base = max(0.0, min(1.0, 0.42 + rings + fibers + knot))
            r = max(0.0, min(1.0, base * 1.18))
            g = max(0.0, min(1.0, base * 0.78))
            b = max(0.0, min(1.0, base * 0.46))
            img.setXelA(x, y, r, g, b, 0.98)
    tex = Texture("combat-weapon-wood")
    tex.load(img)
    tex.setWrapU(Texture.WMRepeat)
    tex.setWrapV(Texture.WMRepeat)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _make_particle_texture() -> Texture:
    size = 64
    img = PNMImage(size, size, 4)
    cx = (size - 1) * 0.5
    cy = (size - 1) * 0.5
    max_d = math.sqrt((cx * cx) + (cy * cy))
    for y in range(size):
        for x in range(size):
            dx = float(x) - cx
            dy = float(y) - cy
            d = math.sqrt((dx * dx) + (dy * dy)) / max_d
            ring = max(0.0, 1.0 - abs((d * 1.45) - 0.48) * 2.3)
            core = max(0.0, 1.0 - (d * 2.1))
            alpha = max(0.0, min(1.0, (core * 0.82) + (ring * 0.58)))
            val = max(0.0, min(1.0, (core * 0.95) + (ring * 0.65)))
            img.setXelA(x, y, val, val, val, alpha)
    tex = Texture("combat-particle")
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _make_tracer_texture() -> Texture:
    w = 128
    h = 32
    img = PNMImage(w, h, 4)
    for y in range(h):
        v = abs((float(y) / float(max(1, h - 1))) - 0.5) * 2.0
        row_fall = max(0.0, 1.0 - (v * v))
        for x in range(w):
            u = float(x) / float(max(1, w - 1))
            head = max(0.0, 1.0 - ((1.0 - u) * 4.2))
            tail = max(0.0, min(1.0, u * 1.4))
            alpha = max(0.0, min(1.0, row_fall * (head * 0.88 + tail * 0.34)))
            val = max(0.0, min(1.0, 0.45 + head * 0.55))
            img.setXelA(x, y, val, val, val, alpha)
    tex = Texture("combat-tracer")
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _make_shockwave_texture() -> Texture:
    size = 128
    img = PNMImage(size, size, 4)
    center = (size - 1) * 0.5
    max_d = math.sqrt((center * center) + (center * center))
    for y in range(size):
        for x in range(size):
            dx = float(x) - center
            dy = float(y) - center
            d = math.sqrt((dx * dx) + (dy * dy)) / max_d
            ring_outer = max(0.0, 1.0 - abs((d * 1.50) - 0.80) * 5.2)
            ring_inner = max(0.0, 1.0 - abs((d * 1.70) - 0.53) * 6.0)
            core_hole = max(0.0, min(1.0, (d - 0.13) * 7.0))
            alpha = max(0.0, min(1.0, (ring_outer * 0.80 + ring_inner * 0.45) * core_hole))
            val = max(0.0, min(1.0, 0.45 + ring_outer * 0.50 + ring_inner * 0.30))
            img.setXelA(x, y, val, val, val, alpha)
    tex = Texture("combat-shockwave")
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _runtime(host) -> CombatFxRuntime:
    st = getattr(host, "_combat_fx_runtime", None)
    if isinstance(st, CombatFxRuntime):
        return st
    st = CombatFxRuntime()
    setattr(host, "_combat_fx_runtime", st)
    return st


def _setup_weapon_piece(np: NodePath, *, texture: Texture | None) -> None:
    np.setTransparency(True)
    np.setDepthTest(False)
    np.setDepthWrite(False)
    np.setBin("fixed", 35)
    np.setLightOff(1)
    np.setTwoSided(True)
    if texture is not None:
        np.setTexture(texture)


def _spawn_weapon_piece(
    *,
    template: NodePath,
    parent: NodePath,
    pos: tuple[float, float, float],
    scale: tuple[float, float, float],
    color: _ColorSpec,
    texture: Texture | None,
    hpr: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> NodePath:
    np = template.copyTo(parent)
    np.show()
    np.setPos(float(pos[0]), float(pos[1]), float(pos[2]))
    np.setHpr(float(hpr[0]), float(hpr[1]), float(hpr[2]))
    np.setScale(float(scale[0]), float(scale[1]), float(scale[2]))
    _setup_weapon_piece(np, texture=texture)
    np.setColor(float(color.r), float(color.g), float(color.b), 0.97)
    return np


def _build_rocket_launcher_view(
    *,
    st: CombatFxRuntime,
    template: NodePath,
    weapon_root: NodePath,
    metal_tex: Texture,
    wood_tex: Texture,
) -> None:
    rocket = weapon_root.attachNewNode("combat-fx-weapon-rocket")
    rocket.setPos(0.01, 0.03, -0.004)
    rocket.setHpr(-3.0, 0.0, 0.0)
    st.weapon_rocket_np = rocket
    st.weapon_rocket_metal_parts.clear()
    st.weapon_rocket_wood_parts.clear()
    st.weapon_rocket_accent_parts.clear()

    def add_metal(
        *,
        pos: tuple[float, float, float],
        scale: tuple[float, float, float],
        color: _ColorSpec = _ROCKET_METAL_COLOR,
        hpr: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        part = _spawn_weapon_piece(
            template=template,
            parent=rocket,
            pos=pos,
            scale=scale,
            color=color,
            texture=metal_tex,
            hpr=hpr,
        )
        st.weapon_rocket_metal_parts.append(part)

    def add_wood(
        *,
        pos: tuple[float, float, float],
        scale: tuple[float, float, float],
        color: _ColorSpec = _ROCKET_WOOD_COLOR,
        hpr: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        part = _spawn_weapon_piece(
            template=template,
            parent=rocket,
            pos=pos,
            scale=scale,
            color=color,
            texture=wood_tex,
            hpr=hpr,
        )
        st.weapon_rocket_wood_parts.append(part)

    def add_accent(
        *,
        pos: tuple[float, float, float],
        scale: tuple[float, float, float],
        color: _ColorSpec = _ROCKET_ACCENT_COLOR,
        hpr: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        part = _spawn_weapon_piece(
            template=template,
            parent=rocket,
            pos=pos,
            scale=scale,
            color=color,
            texture=metal_tex,
            hpr=hpr,
        )
        st.weapon_rocket_accent_parts.append(part)

    # Tube + sleeve body.
    add_metal(pos=(0.0, -0.03, 0.0), scale=(0.11, 0.84, 0.09))
    add_metal(pos=(0.0, 0.31, 0.0), scale=(0.12, 0.30, 0.095), color=_ROCKET_METAL_DARK)
    add_metal(pos=(0.0, 0.58, 0.0), scale=(0.10, 0.11, 0.08), color=_ROCKET_METAL_DARK)
    add_metal(pos=(0.0, -0.50, -0.01), scale=(0.12, 0.03, 0.09), color=_ROCKET_METAL_DARK)

    # Muzzle guard ring and struts.
    add_accent(pos=(0.0, 0.72, 0.0), scale=(0.12, 0.012, 0.09))
    add_accent(pos=(0.052, 0.67, 0.032), scale=(0.009, 0.10, 0.009))
    add_accent(pos=(-0.052, 0.67, 0.032), scale=(0.009, 0.10, 0.009))
    add_accent(pos=(0.052, 0.67, -0.032), scale=(0.009, 0.10, 0.009))
    add_accent(pos=(-0.052, 0.67, -0.032), scale=(0.009, 0.10, 0.009))

    # Iron sights and trigger guard accents.
    add_accent(pos=(0.0, -0.06, 0.066), scale=(0.016, 0.024, 0.016))
    add_accent(pos=(0.0, 0.41, 0.066), scale=(0.012, 0.020, 0.014))
    add_accent(pos=(0.0, 0.00, -0.103), scale=(0.047, 0.016, 0.010))

    # Wood furniture similar to the reference silhouette.
    add_wood(pos=(-0.018, -0.18, -0.123), scale=(0.045, 0.11, 0.10), hpr=(0.0, 20.0, 0.0))
    add_wood(pos=(-0.012, 0.10, -0.123), scale=(0.040, 0.10, 0.095), hpr=(0.0, 24.0, 0.0))
    add_wood(pos=(0.073, 0.02, -0.102), scale=(0.020, 0.30, 0.13), color=_ROCKET_WOOD_DARK)

    rocket.hide()


def init_runtime(host) -> None:
    st = _runtime(host)
    if st.root_np is not None:
        return
    st.root_np = host.render.attachNewNode("combat-fx-root")
    st.particles_np = st.root_np.attachNewNode("combat-fx-particles")
    st.view_np = host.camera.attachNewNode("combat-fx-view")

    template = host.loader.loadModel("models/box")
    template.reparentTo(st.root_np)
    template.hide()
    template.setLightOff(1)
    template.setTwoSided(True)
    template.setTexture(_make_particle_texture())
    st.particle_template_np = template

    tracer = host.loader.loadModel("models/box")
    tracer.reparentTo(st.root_np)
    tracer.hide()
    tracer.setLightOff(1)
    tracer.setTwoSided(True)
    tracer.setTexture(_make_tracer_texture())
    tracer.setTransparency(True)
    tracer.setDepthWrite(False)
    tracer.setBin("fixed", 24)
    st.tracer_template_np = tracer

    shockwave = host.loader.loadModel("models/box")
    shockwave.reparentTo(st.root_np)
    shockwave.hide()
    shockwave.setLightOff(1)
    shockwave.setTwoSided(True)
    shockwave.setTexture(_make_shockwave_texture())
    shockwave.setTransparency(True)
    shockwave.setDepthWrite(False)
    shockwave.setBin("fixed", 22)
    shockwave.setBillboardPointEye()
    st.shockwave_template_np = shockwave

    weapon_template = host.loader.loadModel("models/box")
    weapon_template.reparentTo(st.root_np)
    weapon_template.hide()
    weapon_template.setLightOff(1)
    weapon_template.setTwoSided(True)

    weapon_root = st.view_np.attachNewNode("combat-fx-weapon")
    weapon_root.setPos(_BASE_WEAPON_POS)
    weapon_root.setHpr(*_BASE_WEAPON_HPR)
    st.weapon_np = weapon_root

    generic_weapon = _spawn_weapon_piece(
        template=weapon_template,
        parent=weapon_root,
        pos=(0.0, 0.0, 0.0),
        scale=(0.16, 0.56, 0.12),
        color=_SLOT_COLORS[1],
        texture=_make_weapon_texture(),
    )
    st.weapon_generic_np = generic_weapon

    _build_rocket_launcher_view(
        st=st,
        template=weapon_template,
        weapon_root=weapon_root,
        metal_tex=_make_weapon_metal_texture(),
        wood_tex=_make_weapon_wood_texture(),
    )

    st.view_np.setPos(_BASE_VIEW_POS)
    st.view_np.setHpr(*_BASE_VIEW_HPR)
    st.view_punch_phase = st.rng.uniform(0.0, math.tau)
    _apply_weapon_color(host, slot=1)


def reset_runtime(host, *, keep_weapon_slot: bool = True) -> None:
    st = _runtime(host)
    slot = int(st.anim_slot) if keep_weapon_slot else 1
    st.anim_slot = slot if slot in _ANIM_SPECS else 1
    st.anim_left_s = 0.0
    st.anim_duration_s = 0.0
    st.view_punch_left_s = 0.0
    st.view_punch_duration_s = 0.0
    st.view_punch_amp = 0.0
    st.view_punch_phase = st.rng.uniform(0.0, math.tau)
    _clear_particles(st=st)
    _clear_tracers(st=st)
    _clear_shockwaves(st=st)
    _set_weapon_transform(st=st, spec=None, strength=0.0)
    _set_view_transform(st=st, strength=0.0, dt=0.0)
    _apply_weapon_color(host, slot=int(st.anim_slot))


def _clear_particles(*, st: CombatFxRuntime) -> None:
    for p in st.particles:
        try:
            p.np.removeNode()
        except Exception:
            pass
    st.particles.clear()


def _clear_tracers(*, st: CombatFxRuntime) -> None:
    for tr in st.tracers:
        try:
            tr.np.removeNode()
        except Exception:
            pass
    st.tracers.clear()


def _clear_shockwaves(*, st: CombatFxRuntime) -> None:
    for sw in st.shockwaves:
        try:
            sw.np.removeNode()
        except Exception:
            pass
    st.shockwaves.clear()


def _apply_weapon_color(host, *, slot: int) -> None:
    st = _runtime(host)
    if st.weapon_np is None:
        return
    s = int(slot)
    is_rocket = s == 3
    if st.weapon_generic_np is not None:
        if is_rocket:
            st.weapon_generic_np.hide()
        else:
            st.weapon_generic_np.show()
            c = _SLOT_COLORS.get(s, _SLOT_COLORS[1])
            st.weapon_generic_np.setColor(float(c.r), float(c.g), float(c.b), 0.94)
    if st.weapon_rocket_np is not None:
        if is_rocket:
            st.weapon_rocket_np.show()
        else:
            st.weapon_rocket_np.hide()


def _set_weapon_transform(*, st: CombatFxRuntime, spec: _AnimSpec | None, strength: float) -> None:
    if st.weapon_np is None:
        return
    amt = max(0.0, min(1.0, float(strength)))
    if spec is None or amt <= 0.0:
        st.weapon_np.setPos(_BASE_WEAPON_POS)
        st.weapon_np.setHpr(*_BASE_WEAPON_HPR)
        return
    back = float(spec.back) * amt
    up = float(spec.up) * amt
    roll = float(spec.roll_deg) * amt
    pitch = float(spec.pitch_deg) * amt
    st.weapon_np.setPos(
        float(_BASE_WEAPON_POS.x),
        float(_BASE_WEAPON_POS.y - back),
        float(_BASE_WEAPON_POS.z + up),
    )
    st.weapon_np.setHpr(
        float(_BASE_WEAPON_HPR[0]),
        float(_BASE_WEAPON_HPR[1] - pitch),
        float(_BASE_WEAPON_HPR[2] + roll),
    )


def _set_view_transform(*, st: CombatFxRuntime, strength: float, dt: float) -> None:
    if st.view_np is None:
        return
    amp = max(0.0, min(2.5, float(strength)))
    if amp <= 0.0:
        st.view_np.setPos(_BASE_VIEW_POS)
        st.view_np.setHpr(*_BASE_VIEW_HPR)
        return
    step = max(0.0, float(dt))
    st.view_punch_phase += step * (18.0 + amp * 15.0)
    phase = float(st.view_punch_phase)
    jitter_a = math.sin(phase * 1.8)
    jitter_b = math.sin(phase * 2.7 + 1.9)
    jitter_c = math.sin(phase * 3.9 + 4.2)
    pos_x = 0.018 * amp * jitter_a
    pos_y = -0.008 * amp * abs(jitter_b)
    pos_z = 0.016 * amp * jitter_c
    h = 2.1 * amp * jitter_b
    p = -1.9 * amp * abs(jitter_c)
    r = 3.6 * amp * jitter_a
    st.view_np.setPos(
        float(_BASE_VIEW_POS.x + pos_x),
        float(_BASE_VIEW_POS.y + pos_y),
        float(_BASE_VIEW_POS.z + pos_z),
    )
    st.view_np.setHpr(
        float(_BASE_VIEW_HPR[0] + h),
        float(_BASE_VIEW_HPR[1] + p),
        float(_BASE_VIEW_HPR[2] + r),
    )


def _basis_from_forward(direction: LVector3f) -> tuple[LVector3f, LVector3f, LVector3f]:
    fwd = LVector3f(direction)
    if fwd.lengthSquared() <= 1e-12:
        fwd = LVector3f(0.0, 1.0, 0.0)
    else:
        fwd.normalize()
    up = LVector3f(0.0, 0.0, 1.0)
    right = LVector3f(fwd.cross(up))
    if right.lengthSquared() <= 1e-12:
        right = LVector3f(fwd.cross(LVector3f(1.0, 0.0, 0.0)))
    if right.lengthSquared() <= 1e-12:
        right = LVector3f(1.0, 0.0, 0.0)
    right.normalize()
    up2 = LVector3f(right.cross(fwd))
    if up2.lengthSquared() <= 1e-12:
        up2 = LVector3f(0.0, 0.0, 1.0)
    else:
        up2.normalize()
    return (fwd, right, up2)


def _emit_particle(
    host,
    *,
    pos: LVector3f,
    vel: LVector3f,
    color: _ColorSpec,
    life_s: float,
    start_scale: float,
    end_scale: float,
    gravity: float = 0.0,
    drag: float = 0.0,
    spin_deg_per_s: float = 0.0,
) -> None:
    st = _runtime(host)
    if st.particle_template_np is None or st.particles_np is None:
        return
    np = st.particle_template_np.copyTo(st.particles_np)
    np.show()
    np.setPos(LVector3f(pos))
    np.setScale(float(start_scale))
    np.setColor(float(color.r), float(color.g), float(color.b), 0.96)
    np.setTransparency(True)
    np.setLightOff(1)
    np.setDepthWrite(False)
    np.setBin("fixed", 25)
    st.particles.append(
        _Particle(
            np=np,
            vel=LVector3f(vel),
            life_s=max(0.01, float(life_s)),
            color=color,
            start_scale=max(0.001, float(start_scale)),
            end_scale=max(0.0, float(end_scale)),
            gravity=max(0.0, float(gravity)),
            drag=max(0.0, float(drag)),
            spin_deg_per_s=float(spin_deg_per_s),
        )
    )


def _emit_tracer(
    host,
    *,
    start: LVector3f,
    end: LVector3f,
    color: _ColorSpec,
    speed: float,
    start_scale: float,
    end_scale: float,
) -> None:
    st = _runtime(host)
    if st.tracer_template_np is None or st.particles_np is None:
        return
    span = LVector3f(end - start)
    dist = float(span.length())
    if dist <= 0.02:
        return
    life_s = max(0.04, min(0.42, dist / max(0.1, float(speed))))
    np = st.tracer_template_np.copyTo(st.particles_np)
    np.show()
    np.setPos(LVector3f(start))
    np.setScale(max(0.001, float(start_scale)))
    np.setColor(float(color.r), float(color.g), float(color.b), 0.94)
    st.tracers.append(
        _Tracer(
            np=np,
            start=LVector3f(start),
            end=LVector3f(end),
            life_s=float(life_s),
            color=color,
            start_scale=max(0.001, float(start_scale)),
            end_scale=max(0.0, float(end_scale)),
        )
    )


def _emit_shockwave(
    host,
    *,
    pos: LVector3f,
    color: _ColorSpec,
    life_s: float,
    start_scale: float,
    end_scale: float,
    thickness: float,
    spin_deg_per_s: float = 0.0,
) -> None:
    st = _runtime(host)
    if st.shockwave_template_np is None or st.particles_np is None:
        return
    np = st.shockwave_template_np.copyTo(st.particles_np)
    np.show()
    np.setPos(LVector3f(pos))
    np.setScale(max(0.0001, float(start_scale)), max(0.0001, float(start_scale)), max(0.0001, float(thickness)))
    np.setColor(float(color.r), float(color.g), float(color.b), 0.95)
    st.shockwaves.append(
        _Shockwave(
            np=np,
            pos=LVector3f(pos),
            life_s=max(0.03, float(life_s)),
            color=color,
            start_scale=max(0.0001, float(start_scale)),
            end_scale=max(0.0001, float(end_scale)),
            thickness=max(0.0001, float(thickness)),
            spin_deg_per_s=float(spin_deg_per_s),
        )
    )


def _trigger_view_punch(st: CombatFxRuntime, *, amp: float, duration_s: float) -> None:
    strength = max(0.0, float(amp))
    if strength <= 0.0:
        return
    dur = max(0.01, float(duration_s))
    if dur >= float(st.view_punch_left_s):
        st.view_punch_left_s = dur
        st.view_punch_duration_s = dur
    st.view_punch_amp = max(float(st.view_punch_amp), strength)
    st.view_punch_phase += st.rng.uniform(0.8, 2.6)


def _impact_near_factor(host, *, impact_pos: LVector3f, radius: float) -> float:
    player = getattr(host, "player", None)
    if player is None:
        return 0.0
    half_h = float(getattr(getattr(host, "tuning", None), "player_half_height", 1.0))
    center = LVector3f(float(player.pos.x), float(player.pos.y), float(player.pos.z) + half_h * 0.40)
    dist = float((LVector3f(impact_pos) - center).length())
    return max(0.0, min(1.0, 1.0 - (dist / max(1e-6, float(radius)))))


def _emit_blink_impact(host, *, st: CombatFxRuntime, impact: LVector3f, power: float) -> None:
    intensity = max(0.25, min(2.2, float(power)))
    near = _impact_near_factor(host, impact_pos=impact, radius=11.5)
    _trigger_view_punch(
        st,
        amp=0.10 + 0.13 * intensity + 0.12 * near,
        duration_s=0.08 + 0.03 * intensity,
    )
    _emit_particle(
        host,
        pos=impact,
        vel=LVector3f(0.0, 0.0, 0.0),
        color=_ColorSpec(0.54, 1.0, 1.0),
        life_s=0.09 + 0.02 * intensity,
        start_scale=0.11 + 0.06 * intensity,
        end_scale=0.0,
        drag=5.5,
    )
    _emit_shockwave(
        host,
        pos=impact,
        color=_ColorSpec(0.34, 0.96, 1.0),
        life_s=0.14 + 0.04 * intensity,
        start_scale=0.10,
        end_scale=0.62 + 0.22 * intensity,
        thickness=0.018 + 0.004 * intensity,
        spin_deg_per_s=st.rng.uniform(-170.0, 170.0),
    )
    for _ in range(int(12 + 7 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        rise = st.rng.uniform(-0.10, 0.70)
        vel = LVector3f(math.cos(ang), math.sin(ang), rise) * st.rng.uniform(4.6, 9.0 + 1.4 * intensity)
        _emit_particle(
            host,
            pos=impact,
            vel=vel,
            color=_ColorSpec(0.34, 0.94, 1.0),
            life_s=st.rng.uniform(0.10, 0.22),
            start_scale=st.rng.uniform(0.014, 0.030),
            end_scale=0.0,
            gravity=2.0,
            drag=1.8,
            spin_deg_per_s=st.rng.uniform(-360.0, 360.0),
        )
    for _ in range(int(3 + 2 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        ray = LVector3f(math.cos(ang), math.sin(ang), st.rng.uniform(-0.02, 0.26))
        if ray.lengthSquared() > 1e-12:
            ray.normalize()
        _emit_tracer(
            host,
            start=impact + ray * 0.03,
            end=impact + ray * st.rng.uniform(1.3, 2.6 + 0.7 * intensity),
            color=_ColorSpec(0.56, 1.0, 1.0),
            speed=24.0 + 10.0 * intensity,
            start_scale=0.010 + 0.003 * intensity,
            end_scale=0.002,
        )


def _emit_slam_impact(host, *, st: CombatFxRuntime, impact: LVector3f, power: float) -> None:
    intensity = max(0.30, min(2.4, float(power)))
    near = _impact_near_factor(host, impact_pos=impact, radius=12.5)
    _trigger_view_punch(
        st,
        amp=0.13 + 0.18 * intensity + 0.16 * near,
        duration_s=0.10 + 0.04 * intensity,
    )
    _emit_particle(
        host,
        pos=impact,
        vel=LVector3f(0.0, 0.0, 0.0),
        color=_ColorSpec(1.0, 0.84, 0.42),
        life_s=0.10 + 0.03 * intensity,
        start_scale=0.15 + 0.08 * intensity,
        end_scale=0.0,
        drag=5.2,
    )
    _emit_shockwave(
        host,
        pos=impact,
        color=_ColorSpec(1.0, 0.66, 0.24),
        life_s=0.16 + 0.05 * intensity,
        start_scale=0.11,
        end_scale=0.76 + 0.32 * intensity,
        thickness=0.022 + 0.005 * intensity,
        spin_deg_per_s=st.rng.uniform(-210.0, 210.0),
    )
    for _ in range(int(18 + 11 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        rise = st.rng.uniform(-0.16, 0.95)
        vel = LVector3f(math.cos(ang), math.sin(ang), rise) * st.rng.uniform(5.2, 11.8 + 2.0 * intensity)
        _emit_particle(
            host,
            pos=impact,
            vel=vel,
            color=_ColorSpec(1.0, 0.70, 0.22),
            life_s=st.rng.uniform(0.12, 0.26),
            start_scale=st.rng.uniform(0.016, 0.034),
            end_scale=0.0,
            gravity=3.2,
            drag=1.4,
            spin_deg_per_s=st.rng.uniform(-420.0, 420.0),
        )
    for _ in range(int(8 + 5 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        ray = LVector3f(math.cos(ang), math.sin(ang), st.rng.uniform(0.00, 0.36))
        if ray.lengthSquared() > 1e-12:
            ray.normalize()
        _emit_tracer(
            host,
            start=impact + ray * 0.04,
            end=impact + ray * st.rng.uniform(1.4, 3.6 + 0.8 * intensity),
            color=_ColorSpec(1.0, 0.78, 0.32),
            speed=22.0 + 8.0 * intensity,
            start_scale=0.012 + 0.004 * intensity,
            end_scale=0.002,
        )


def _emit_blaster(host, *, event: CombatFireEvent) -> None:
    st = _runtime(host)
    fwd, right, up = _basis_from_forward(event.direction)
    muzzle = LVector3f(event.origin + fwd * 0.72)
    c = _SLOT_COLORS[1]
    power = max(0.25, min(2.0, float(event.impact_power) if float(event.impact_power) > 0.0 else 0.9))
    _emit_particle(
        host,
        pos=muzzle,
        vel=fwd * 0.2,
        color=c,
        life_s=0.06,
        start_scale=0.09,
        end_scale=0.01,
        drag=4.5,
    )
    for _ in range(8):
        spread_r = st.rng.uniform(-0.35, 0.35)
        spread_u = st.rng.uniform(-0.28, 0.28)
        speed = st.rng.uniform(9.5, 16.5)
        vel = fwd * speed + right * spread_r * speed + up * spread_u * speed
        _emit_particle(
            host,
            pos=muzzle,
            vel=vel,
            color=c,
            life_s=st.rng.uniform(0.11, 0.21),
            start_scale=st.rng.uniform(0.018, 0.032),
            end_scale=0.0,
            drag=3.0,
        )
    for i in range(6):
        trail_pos = muzzle - fwd * (i * 0.26)
        _emit_particle(
            host,
            pos=trail_pos,
            vel=fwd * (2.2 + i * 0.35),
            color=c,
            life_s=0.09 + i * 0.02,
            start_scale=0.020 + i * 0.004,
            end_scale=0.0,
            drag=2.8,
        )
    if event.impact_pos is not None:
        impact = LVector3f(event.impact_pos)
        _emit_tracer(
            host,
            start=muzzle,
            end=impact,
            color=_ColorSpec(0.28, 0.96, 1.0),
            speed=96.0,
            start_scale=0.036,
            end_scale=0.004,
        )
        if bool(event.world_hit):
            _emit_blink_impact(host, st=st, impact=impact, power=power)


def _emit_scatter(host, *, event: CombatFireEvent) -> None:
    st = _runtime(host)
    fwd, right, up = _basis_from_forward(event.direction)
    muzzle = LVector3f(event.origin + fwd * 0.66)
    c = _SLOT_COLORS[2]
    power = max(0.25, min(2.4, float(event.impact_power) if float(event.impact_power) > 0.0 else 1.0))
    _emit_particle(
        host,
        pos=muzzle,
        vel=fwd * 0.4,
        color=c,
        life_s=0.07,
        start_scale=0.12,
        end_scale=0.01,
        drag=4.8,
    )
    for _ in range(20):
        spread_r = st.rng.uniform(-0.95, 0.95)
        spread_u = st.rng.uniform(-0.60, 0.60)
        speed = st.rng.uniform(6.8, 13.8)
        vel = fwd * speed + right * spread_r * speed + up * spread_u * speed
        _emit_particle(
            host,
            pos=muzzle,
            vel=vel,
            color=c,
            life_s=st.rng.uniform(0.16, 0.29),
            start_scale=st.rng.uniform(0.016, 0.030),
            end_scale=0.0,
            gravity=2.5,
            drag=1.5,
            spin_deg_per_s=st.rng.uniform(-320.0, 320.0),
        )
    for _ in range(16):
        ang = st.rng.uniform(0.0, math.tau)
        ring = right * math.cos(ang) + up * math.sin(ang)
        vel = ring * st.rng.uniform(3.2, 7.4) + fwd * st.rng.uniform(1.0, 2.2)
        _emit_particle(
            host,
            pos=muzzle + ring * st.rng.uniform(0.01, 0.08),
            vel=vel,
            color=c,
            life_s=st.rng.uniform(0.18, 0.28),
            start_scale=st.rng.uniform(0.020, 0.040),
            end_scale=0.0,
            gravity=1.8,
            drag=1.6,
        )
    if event.impact_pos is not None:
        impact = LVector3f(event.impact_pos)
        _emit_tracer(
            host,
            start=muzzle,
            end=impact,
            color=_ColorSpec(1.0, 0.72, 0.22),
            speed=74.0,
            start_scale=0.048,
            end_scale=0.006,
        )
        if bool(event.world_hit):
            _emit_slam_impact(host, st=st, impact=impact, power=power)


def _emit_rocket(host, *, event: CombatFireEvent) -> None:
    st = _runtime(host)
    fwd, right, up = _basis_from_forward(event.direction)
    muzzle = LVector3f(event.origin + fwd * 0.75)
    power = max(0.35, min(2.4, float(event.impact_power) if float(event.impact_power) > 0.0 else 1.0))
    flame = _ColorSpec(1.0, 0.47, 0.16)
    ember = _ColorSpec(1.0, 0.78, 0.22)
    smoke = _ColorSpec(0.52, 0.52, 0.52)

    for _ in range(int(10 + 4 * power)):
        spread_r = st.rng.uniform(-0.35, 0.35)
        spread_u = st.rng.uniform(-0.35, 0.35)
        speed = st.rng.uniform(3.5, 9.0 + 1.8 * power)
        vel = fwd * speed + right * spread_r * speed + up * spread_u * speed
        _emit_particle(
            host,
            pos=muzzle,
            vel=vel,
            color=flame,
            life_s=st.rng.uniform(0.11, 0.22),
            start_scale=st.rng.uniform(0.028, 0.062),
            end_scale=0.0,
            drag=2.3,
        )
    for _ in range(int(8 + 2 * power)):
        spread_r = st.rng.uniform(-0.45, 0.45)
        spread_u = st.rng.uniform(-0.45, 0.45)
        speed = st.rng.uniform(2.0, 6.2)
        vel = fwd * speed + right * spread_r * speed + up * spread_u * speed + LVector3f(0.0, 0.0, 0.4)
        _emit_particle(
            host,
            pos=muzzle,
            vel=vel,
            color=smoke,
            life_s=st.rng.uniform(0.24, 0.48),
            start_scale=st.rng.uniform(0.042, 0.082),
            end_scale=st.rng.uniform(0.018, 0.038),
            drag=0.78,
        )
    if event.impact_pos is not None:
        impact = LVector3f(event.impact_pos)
        _emit_tracer(
            host,
            start=muzzle,
            end=impact,
            color=_ColorSpec(1.0, 0.38, 0.14),
            speed=42.0 + 12.0 * power,
            start_scale=0.062 + 0.010 * power,
            end_scale=0.014,
        )
        path = LVector3f(impact - muzzle)
        path_len = float(path.length())
        if path_len > 0.06:
            path_dir = LVector3f(path / max(1e-6, path_len))
            trail_count = max(6, min(28, int(path_len * (0.45 + 0.12 * power))))
            for i in range(trail_count):
                t = (float(i) + st.rng.uniform(0.0, 0.7)) / float(max(1, trail_count))
                base = muzzle + path_dir * (path_len * t)
                jitter = right * st.rng.uniform(-0.08, 0.08) + up * st.rng.uniform(-0.08, 0.08)
                _emit_particle(
                    host,
                    pos=base + jitter,
                    vel=(-path_dir * st.rng.uniform(0.4, 2.4)) + up * st.rng.uniform(0.0, 0.8),
                    color=smoke,
                    life_s=st.rng.uniform(0.16, 0.34),
                    start_scale=st.rng.uniform(0.028, 0.052),
                    end_scale=st.rng.uniform(0.010, 0.024),
                    drag=1.3,
                )
                if (i % 2) == 0:
                    _emit_particle(
                        host,
                        pos=base + jitter * 0.5,
                        vel=path_dir * st.rng.uniform(0.6, 2.0) + up * st.rng.uniform(-0.2, 0.5),
                        color=ember,
                        life_s=st.rng.uniform(0.07, 0.16),
                        start_scale=st.rng.uniform(0.010, 0.021),
                        end_scale=0.0,
                        drag=2.2,
                    )

    if event.impact_pos is None:
        _trigger_view_punch(st, amp=0.24 + 0.12 * power, duration_s=0.11)
        return
    impact = LVector3f(event.impact_pos)
    player = getattr(host, "player", None)
    near_boost = 0.0
    if player is not None:
        half_h = float(getattr(getattr(host, "tuning", None), "player_half_height", 1.0))
        player_center = LVector3f(float(player.pos.x), float(player.pos.y), float(player.pos.z) + half_h * 0.40)
        dist_to_player = float((player_center - impact).length())
        near_boost = max(0.0, min(1.0, 1.0 - (dist_to_player / 13.5)))
    intensity = power * (1.0 if bool(event.world_hit) else 0.65)
    _trigger_view_punch(
        st,
        amp=0.42 + 0.42 * intensity + 0.78 * near_boost,
        duration_s=0.20 + 0.09 * intensity,
    )
    _emit_particle(
        host,
        pos=impact,
        vel=LVector3f(0.0, 0.0, 0.0),
        color=_ColorSpec(1.0, 0.86, 0.52),
        life_s=0.10 + 0.05 * intensity,
        start_scale=0.18 + 0.14 * intensity,
        end_scale=0.0,
        drag=5.0,
    )
    _emit_shockwave(
        host,
        pos=impact,
        color=_ColorSpec(1.0, 0.64, 0.28),
        life_s=0.18 + 0.08 * intensity,
        start_scale=0.14,
        end_scale=0.92 + 0.70 * intensity,
        thickness=0.032 + 0.012 * intensity,
        spin_deg_per_s=st.rng.uniform(-170.0, 170.0),
    )
    _emit_shockwave(
        host,
        pos=impact,
        color=_ColorSpec(1.0, 0.40, 0.16),
        life_s=0.22 + 0.09 * intensity,
        start_scale=0.18,
        end_scale=1.24 + 0.92 * intensity,
        thickness=0.026 + 0.009 * intensity,
        spin_deg_per_s=st.rng.uniform(-240.0, 240.0),
    )
    for _ in range(int(28 + 22 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        vz = st.rng.uniform(0.15, 1.15)
        vr = st.rng.uniform(6.8, 17.8 + 5.0 * intensity)
        vel = LVector3f(math.cos(ang) * vr, math.sin(ang) * vr, vz * vr)
        _emit_particle(
            host,
            pos=impact,
            vel=vel,
            color=flame,
            life_s=st.rng.uniform(0.15, 0.36),
            start_scale=st.rng.uniform(0.032, 0.070),
            end_scale=0.0,
            gravity=4.8,
            drag=1.0,
        )
    for _ in range(int(20 + 16 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        rise = st.rng.uniform(-0.18, 0.95)
        vr = st.rng.uniform(4.8, 12.5 + 3.5 * intensity)
        vel = LVector3f(math.cos(ang) * vr, math.sin(ang) * vr, rise * vr)
        _emit_particle(
            host,
            pos=impact,
            vel=vel,
            color=ember,
            life_s=st.rng.uniform(0.12, 0.26),
            start_scale=st.rng.uniform(0.010, 0.024),
            end_scale=0.0,
            gravity=3.0,
            drag=1.8,
        )
    for _ in range(int(22 + 16 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        vr = st.rng.uniform(2.4, 8.4 + 2.8 * intensity)
        vel = LVector3f(math.cos(ang) * vr, math.sin(ang) * vr, st.rng.uniform(0.8, 5.2))
        _emit_particle(
            host,
            pos=impact,
            vel=vel,
            color=smoke,
            life_s=st.rng.uniform(0.36, 0.72),
            start_scale=st.rng.uniform(0.052, 0.108),
            end_scale=st.rng.uniform(0.020, 0.052),
            gravity=1.5,
            drag=0.54,
        )
    for _ in range(int(5 + 5 * intensity)):
        ang = st.rng.uniform(0.0, math.tau)
        rise = st.rng.uniform(0.02, 0.9)
        d = LVector3f(math.cos(ang), math.sin(ang), rise)
        if d.lengthSquared() > 1e-12:
            d.normalize()
        _emit_tracer(
            host,
            start=impact + d * 0.08,
            end=impact + d * st.rng.uniform(2.8, 7.2 + 2.0 * intensity),
            color=_ColorSpec(1.0, 0.54, 0.22),
            speed=30.0 + 16.0 * intensity,
            start_scale=0.020 + 0.010 * intensity,
            end_scale=0.004,
        )


def _emit_pulse(host, *, event: CombatFireEvent) -> None:
    st = _runtime(host)
    fwd, right, up = _basis_from_forward(event.direction)
    muzzle = LVector3f(event.origin + fwd * 0.70)
    c = _SLOT_COLORS[4]
    power = max(0.30, min(2.0, float(event.impact_power) if float(event.impact_power) > 0.0 else 0.9))
    for _ in range(22):
        ang = st.rng.uniform(0.0, math.tau)
        ring_r = st.rng.uniform(0.0, 1.0)
        side = right * math.cos(ang) + up * math.sin(ang)
        speed = st.rng.uniform(6.5, 13.0)
        vel = fwd * (speed * 0.75) + side * (ring_r * speed)
        _emit_particle(
            host,
            pos=muzzle + side * st.rng.uniform(0.0, 0.06),
            vel=vel,
            color=c,
            life_s=st.rng.uniform(0.16, 0.28),
            start_scale=st.rng.uniform(0.018, 0.038),
            end_scale=0.0,
            drag=1.8,
            spin_deg_per_s=st.rng.uniform(-420.0, 420.0),
        )
    if event.impact_pos is not None:
        _emit_tracer(
            host,
            start=muzzle,
            end=LVector3f(event.impact_pos),
            color=_ColorSpec(0.40, 1.0, 0.60),
            speed=62.0 + power * 12.0,
            start_scale=0.050 + power * 0.007,
            end_scale=0.010,
        )
    if event.impact_pos is not None and bool(event.world_hit):
        impact = LVector3f(event.impact_pos)
        intensity = power * 0.85
        _trigger_view_punch(
            st,
            amp=0.26 + 0.28 * intensity,
            duration_s=0.14 + 0.05 * intensity,
        )
        _emit_shockwave(
            host,
            pos=impact,
            color=_ColorSpec(0.44, 1.0, 0.62),
            life_s=0.18 + 0.04 * intensity,
            start_scale=0.12,
            end_scale=0.76 + 0.36 * intensity,
            thickness=0.022 + 0.006 * intensity,
            spin_deg_per_s=st.rng.uniform(-210.0, 210.0),
        )
        for _ in range(14):
            ang = st.rng.uniform(0.0, math.tau)
            vel = LVector3f(math.cos(ang), math.sin(ang), st.rng.uniform(-0.2, 0.8)) * st.rng.uniform(4.0, 9.0)
            _emit_particle(
                host,
                pos=impact,
                vel=vel,
                color=c,
                life_s=st.rng.uniform(0.18, 0.34),
                start_scale=st.rng.uniform(0.022, 0.042),
                end_scale=0.0,
                gravity=2.0,
                drag=1.2,
            )
        for _ in range(int(8 + 5 * intensity)):
            ang = st.rng.uniform(0.0, math.tau)
            ray = LVector3f(math.cos(ang), math.sin(ang), st.rng.uniform(-0.08, 0.42))
            if ray.lengthSquared() > 1e-12:
                ray.normalize()
            _emit_tracer(
                host,
                start=impact + ray * 0.05,
                end=impact + ray * st.rng.uniform(1.5, 4.2 + intensity * 0.9),
                color=_ColorSpec(0.52, 1.0, 0.68),
                speed=24.0 + 6.0 * intensity,
                start_scale=0.012 + 0.004 * intensity,
                end_scale=0.003,
            )


def on_fire(host, *, event: CombatFireEvent) -> None:
    st = _runtime(host)
    slot = int(event.slot)
    spec = _ANIM_SPECS.get(slot, _ANIM_SPECS[1])
    st.anim_slot = slot
    st.anim_left_s = max(float(st.anim_left_s), float(spec.duration_s))
    st.anim_duration_s = float(spec.duration_s)
    _apply_weapon_color(host, slot=slot)

    if slot == 1:
        _trigger_view_punch(st, amp=0.10, duration_s=0.08)
        _emit_blaster(host, event=event)
    elif slot == 2:
        _trigger_view_punch(st, amp=0.15, duration_s=0.10)
        _emit_scatter(host, event=event)
    elif slot == 3:
        _trigger_view_punch(st, amp=0.22, duration_s=0.11)
        _emit_rocket(host, event=event)
    elif slot == 4:
        _trigger_view_punch(st, amp=0.16, duration_s=0.10)
        _emit_pulse(host, event=event)


def _update_weapon_visible(host, *, st: CombatFxRuntime) -> None:
    if st.view_np is None:
        return
    is_visible = (
        getattr(host, "_mode", "") == "game"
        and not bool(getattr(host, "_pause_menu_open", False))
        and not bool(getattr(host, "_debug_menu_open", False))
        and not bool(getattr(host, "_console_open", False))
        and not bool(getattr(host, "_replay_browser_open", False))
        and not bool(getattr(host, "_feel_capture_open", False))
    )
    if is_visible:
        st.view_np.show()
    else:
        st.view_np.hide()


def _update_particles(*, st: CombatFxRuntime, dt: float) -> None:
    step = max(0.0, float(dt))
    if step <= 0.0:
        return
    alive: list[_Particle] = []
    for p in st.particles:
        p.age_s += step
        if p.age_s >= float(p.life_s):
            try:
                p.np.removeNode()
            except Exception:
                pass
            continue
        p.vel *= max(0.0, 1.0 - float(p.drag) * step)
        p.vel.z -= float(p.gravity) * step
        p.np.setPos(p.np.getPos() + p.vel * step)
        if abs(float(p.spin_deg_per_s)) > 1e-6:
            p.np.setH(float(p.np.getH()) + float(p.spin_deg_per_s) * step)
        t = max(0.0, min(1.0, float(p.age_s) / max(1e-6, float(p.life_s))))
        scale = float(p.start_scale) + (float(p.end_scale) - float(p.start_scale)) * t
        alpha = (1.0 - t) * (1.0 - (t * t * 0.35))
        p.np.setScale(max(0.0001, scale))
        p.np.setColor(float(p.color.r), float(p.color.g), float(p.color.b), max(0.0, min(1.0, alpha)))
        alive.append(p)
    st.particles = alive


def _update_tracers(*, st: CombatFxRuntime, dt: float) -> None:
    step = max(0.0, float(dt))
    if step <= 0.0:
        return
    alive: list[_Tracer] = []
    for tr in st.tracers:
        tr.age_s += step
        if tr.age_s >= float(tr.life_s):
            try:
                tr.np.removeNode()
            except Exception:
                pass
            continue
        t = max(0.0, min(1.0, float(tr.age_s) / max(1e-6, float(tr.life_s))))
        pos = tr.start + (tr.end - tr.start) * t
        tr.np.setPos(LVector3f(pos))
        look = LVector3f(tr.end - tr.start)
        if look.lengthSquared() > 1e-12:
            tr.np.lookAt(pos + look)
        scale = float(tr.start_scale) + (float(tr.end_scale) - float(tr.start_scale)) * t
        alpha = max(0.0, min(1.0, (1.0 - t) * 0.95))
        tr.np.setScale(max(0.0001, scale), max(0.0001, scale * 2.8), max(0.0001, scale))
        tr.np.setColor(float(tr.color.r), float(tr.color.g), float(tr.color.b), alpha)
        alive.append(tr)
    st.tracers = alive


def _update_shockwaves(*, st: CombatFxRuntime, dt: float) -> None:
    step = max(0.0, float(dt))
    if step <= 0.0:
        return
    alive: list[_Shockwave] = []
    for sw in st.shockwaves:
        sw.age_s += step
        if sw.age_s >= float(sw.life_s):
            try:
                sw.np.removeNode()
            except Exception:
                pass
            continue
        t = max(0.0, min(1.0, float(sw.age_s) / max(1e-6, float(sw.life_s))))
        scale = float(sw.start_scale) + (float(sw.end_scale) - float(sw.start_scale)) * t
        thickness = float(sw.thickness) * (1.0 + 0.35 * t)
        alpha = max(0.0, min(1.0, (1.0 - t) ** 1.55))
        if abs(float(sw.spin_deg_per_s)) > 1e-6:
            sw.np.setR(float(sw.np.getR()) + float(sw.spin_deg_per_s) * step)
        sw.np.setScale(max(0.0001, scale), max(0.0001, scale), max(0.0001, thickness))
        sw.np.setColor(float(sw.color.r), float(sw.color.g), float(sw.color.b), alpha)
        alive.append(sw)
    st.shockwaves = alive


def _update_view_punch(*, st: CombatFxRuntime, dt: float) -> None:
    if st.view_np is None:
        return
    step = max(0.0, float(dt))
    if step <= 0.0:
        _set_view_transform(st=st, strength=0.0, dt=0.0)
        return
    if float(st.view_punch_left_s) <= 0.0:
        st.view_punch_amp = max(0.0, float(st.view_punch_amp) - step * 9.0)
        _set_view_transform(st=st, strength=0.0, dt=step)
        return
    st.view_punch_left_s = max(0.0, float(st.view_punch_left_s) - step)
    t = 1.0 - (float(st.view_punch_left_s) / max(1e-6, float(st.view_punch_duration_s)))
    envelope = (1.0 - max(0.0, min(1.0, t))) ** 0.34
    amp = max(0.0, float(st.view_punch_amp)) * envelope
    _set_view_transform(st=st, strength=amp, dt=step)
    if float(st.view_punch_left_s) <= 0.0:
        st.view_punch_amp = max(0.0, float(st.view_punch_amp) * 0.55)


def update(host, *, dt: float) -> None:
    st = _runtime(host)
    _update_weapon_visible(host, st=st)

    active_slot = int(getattr(getattr(host, "_combat_runtime", None), "active_slot", st.anim_slot))
    _apply_weapon_color(host, slot=active_slot)
    spec = _ANIM_SPECS.get(int(st.anim_slot), _ANIM_SPECS[1])

    if st.anim_left_s > 0.0 and st.anim_duration_s > 0.0:
        st.anim_left_s = max(0.0, float(st.anim_left_s) - max(0.0, float(dt)))
        p = 1.0 - (float(st.anim_left_s) / max(1e-6, float(st.anim_duration_s)))
        # Punchy out-and-return envelope.
        envelope = math.sin(math.pi * max(0.0, min(1.0, p)))
        _set_weapon_transform(st=st, spec=spec, strength=float(envelope))
    else:
        _set_weapon_transform(st=st, spec=None, strength=0.0)

    _update_particles(st=st, dt=dt)
    _update_tracers(st=st, dt=dt)
    _update_shockwaves(st=st, dt=dt)
    _update_view_punch(st=st, dt=dt)


__all__ = ["init_runtime", "on_fire", "reset_runtime", "update"]
