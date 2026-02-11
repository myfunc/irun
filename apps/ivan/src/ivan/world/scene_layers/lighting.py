from __future__ import annotations

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Fog,
    LVector3f,
    LVector4f,
    PerspectiveLens,
    PointLight,
    Spotlight,
)

from ivan.world.scene_layers.contracts import SceneLayerContract


def build_lighting(scene: SceneLayerContract, *, render) -> None:
    """Create default ambient + directional scene lights."""
    ambient = AmbientLight("ambient")
    ambient.setColor(LVector4f(0.30, 0.30, 0.33, 1))
    scene._ambient_np = render.attachNewNode(ambient)
    render.setLight(scene._ambient_np)

    sun = DirectionalLight("sun")
    sun.setColor(LVector4f(0.95, 0.93, 0.86, 1))
    scene._sun_np = render.attachNewNode(sun)
    scene._sun_np.setHpr(34, -58, 0)
    render.setLight(scene._sun_np)


def apply_fog(scene: SceneLayerContract, *, cfg, render) -> None:
    """Apply baseline fog precedence: map override > run profile > engine default."""
    fog_defaults = {
        "enabled": True,
        "mode": "linear",
        "start": 120.0,
        "end": 360.0,
        "density": 0.02,
        "color": (0.63, 0.67, 0.73),
    }
    run_fog = getattr(cfg, "fog", None)
    source = "engine-default"
    fog_cfg = fog_defaults

    map_fog = None
    if getattr(scene, "_map_payload", None) and isinstance(scene._map_payload, dict):
        map_fog = scene._map_payload.get("fog")

    runtime_override = getattr(scene, "_runtime_fog_override", None)

    if isinstance(runtime_override, dict):
        source = "runtime-console"
        fog_cfg = {**fog_defaults, **runtime_override}
    elif isinstance(map_fog, dict):
        source = "map-override"
        fog_cfg = {**fog_defaults, **map_fog}
    elif isinstance(run_fog, dict):
        source = "run-profile"
        fog_cfg = {**fog_defaults, **run_fog}

    enabled = bool(fog_cfg.get("enabled", fog_defaults["enabled"]))
    mode = str(fog_cfg.get("mode", fog_defaults["mode"])).strip().lower()
    if mode not in ("linear", "exp", "exp2"):
        mode = "linear"
    start = float(fog_defaults["start"])
    end = float(fog_defaults["end"])
    density = float(fog_defaults["density"])
    color = fog_defaults["color"]

    try:
        start = float(fog_cfg.get("start", start))
    except (TypeError, ValueError):
        pass
    try:
        end = float(fog_cfg.get("end", end))
    except (TypeError, ValueError):
        pass
    try:
        density = float(fog_cfg.get("density", density))
    except (TypeError, ValueError):
        pass
    density = max(0.0, density)
    c = fog_cfg.get("color")
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        try:
            color = (float(c[0]), float(c[1]), float(c[2]))
        except (TypeError, ValueError):
            pass

    if end <= start:
        end = start + 1.0

    scene._fog_source = str(source)
    scene._fog_enabled = bool(enabled)
    scene._fog_mode = str(mode)
    scene._fog_density = float(density)
    scene._fog_range = (float(start), float(end))
    scene._fog_color = (float(color[0]), float(color[1]), float(color[2]))

    if not enabled:
        render.clearFog()
        return
    fog = Fog("map-fog")
    if mode == "exp":
        fog.setMode(Fog.M_exponential)
        fog.setExpDensity(float(density))
    elif mode == "exp2":
        fog.setMode(Fog.M_exponential_squared)
        fog.setExpDensity(float(density))
    else:
        fog.setMode(Fog.M_linear)
        fog.setLinearRange(start, end)
    fog.setColor(LVector4f(color[0], color[1], color[2], 1))
    fog_np = render.attachNewNode(fog)
    fog_obj = fog_np.node() if hasattr(fog_np, "node") else fog_np
    render.setFog(fog_obj)


def enhance_map_file_lighting(scene: SceneLayerContract, *, render, lights) -> None:
    """
    Set up bright preview lighting for direct `.map` file loading.
    """
    if scene._ambient_np is not None:
        scene._ambient_np.node().setColor(LVector4f(0.55, 0.55, 0.58, 1))

    has_env_light = False
    for i, le in enumerate(lights):
        cn = le.classname

        if cn == "light_environment":
            has_env_light = True
            r, g, b = le.color
            intensity = le.brightness / 255.0
            if scene._sun_np is not None:
                scene._sun_np.node().setColor(LVector4f(r * intensity, g * intensity, b * intensity, 1))
                yaw = le.angles[1] if abs(le.angles[1]) > 0.01 else 0.0
                pitch = le.pitch if abs(le.pitch) > 0.01 else -60.0
                scene._sun_np.setHpr(yaw, pitch, 0)

        elif cn == "light":
            r, g, b = le.color
            intensity = le.brightness / 255.0
            pl = PointLight(f"hl-light-{i}")
            pl.setColor(LVector4f(r * intensity * 1.2, g * intensity * 1.2, b * intensity * 1.2, 1))
            fade = max(le.fade, 0.1)
            pl.setAttenuation(LVector3f(1.0, 0.0, fade * 8.0))
            pl_np = render.attachNewNode(pl)
            pl_np.setPos(le.origin[0], le.origin[1], le.origin[2])
            render.setLight(pl_np)
        elif cn == "light_spot":
            r, g, b = le.color
            intensity = le.brightness / 255.0
            sl = Spotlight(f"hl-spot-{i}")
            sl.setColor(LVector4f(r * intensity * 1.2, g * intensity * 1.2, b * intensity * 1.2, 1))
            lens = PerspectiveLens()
            outer = float(le.outer_cone) if float(le.outer_cone) > 0.0 else 45.0
            lens.setFov(max(1.0, min(175.0, outer * 2.0)))
            sl.setLens(lens)
            fade = max(le.fade, 0.1)
            sl.setAttenuation(LVector3f(1.0, 0.0, fade * 8.0))
            sl_np = render.attachNewNode(sl)
            sl_np.setPos(le.origin[0], le.origin[1], le.origin[2])
            yaw = le.angles[1] if abs(le.angles[1]) > 0.01 else 0.0
            pitch = le.pitch if abs(le.pitch) > 0.01 else le.angles[0]
            sl_np.setHpr(yaw, pitch, 0.0)
            render.setLight(sl_np)

    if not has_env_light and scene._sun_np is not None:
        scene._sun_np.node().setColor(LVector4f(0.70, 0.68, 0.60, 1))
        scene._sun_np.setHpr(34, -45, 0)

    if not lights:
        fill = PointLight("map-fill")
        fill.setColor(LVector4f(0.50, 0.48, 0.42, 1))
        fill.setAttenuation(LVector3f(1.0, 0.0, 0.2))
        fill_np = render.attachNewNode(fill)
        if scene.spawn_point:
            fill_np.setPos(
                scene.spawn_point.getX(),
                scene.spawn_point.getY(),
                scene.spawn_point.getZ() + 8.0,
            )
        else:
            fill_np.setPos(0, 0, 10)
        render.setLight(fill_np)


def lights_from_payload(*, payload: dict) -> list:
    """
    Parse optional serialized Half-Life light entities from `map.json`.
    """
    raw = payload.get("lights")
    if not isinstance(raw, list) or not raw:
        return []
    from ivan.maps.map_converter import LightEntity

    out: list[LightEntity] = []
    for ent in raw:
        if not isinstance(ent, dict):
            continue
        cn = str(ent.get("classname", "")).strip().lower()
        if cn not in {"light", "light_spot", "light_environment"}:
            continue
        origin_v = ent.get("origin", [0.0, 0.0, 0.0])
        color_v = ent.get("color", [1.0, 1.0, 1.0])
        angles_v = ent.get("angles", [0.0, 0.0, 0.0])
        try:
            if not (
                isinstance(origin_v, (list, tuple))
                and len(origin_v) >= 3
                and isinstance(color_v, (list, tuple))
                and len(color_v) >= 3
                and isinstance(angles_v, (list, tuple))
                and len(angles_v) >= 3
            ):
                continue
            out.append(
                LightEntity(
                    classname=cn,
                    origin=(float(origin_v[0]), float(origin_v[1]), float(origin_v[2])),
                    color=(float(color_v[0]), float(color_v[1]), float(color_v[2])),
                    brightness=float(ent.get("brightness", 200.0)),
                    pitch=float(ent.get("pitch", 0.0)),
                    angles=(float(angles_v[0]), float(angles_v[1]), float(angles_v[2])),
                    inner_cone=float(ent.get("inner_cone", 0.0)),
                    outer_cone=float(ent.get("outer_cone", 0.0)),
                    fade=float(ent.get("fade", 1.0)),
                    falloff=int(ent.get("falloff", 0)),
                    style=int(ent.get("style", 0)),
                )
            )
        except Exception:
            continue
    return out

