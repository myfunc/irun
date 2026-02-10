from __future__ import annotations

from panda3d.core import AmbientLight, DirectionalLight, Fog, LVector3f, LVector4f, PointLight

from ivan.app_config import MAP_PROFILE_DEV_FAST


def build_lighting(scene, *, render) -> None:
    ambient = AmbientLight("ambient")
    ambient.setColor(LVector4f(0.30, 0.30, 0.33, 1))
    scene._ambient_np = render.attachNewNode(ambient)
    render.setLight(scene._ambient_np)

    sun = DirectionalLight("sun")
    sun.setColor(LVector4f(0.95, 0.93, 0.86, 1))
    scene._sun_np = render.attachNewNode(sun)
    scene._sun_np.setHpr(34, -58, 0)
    render.setLight(scene._sun_np)


def apply_fog(scene, *, cfg, render) -> None:
    fog_cfg = getattr(cfg, "fog", None)
    profile = getattr(cfg, "map_profile", "") or "prod-baked"
    enabled = False
    start = 80.0
    end = 200.0
    color = (0.65, 0.68, 0.72)
    if isinstance(fog_cfg, dict):
        enabled = bool(fog_cfg.get("enabled", False))
        try:
            start = float(fog_cfg.get("start", start))
        except (TypeError, ValueError):
            pass
        try:
            end = float(fog_cfg.get("end", end))
        except (TypeError, ValueError):
            pass
        c = fog_cfg.get("color")
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            try:
                color = (float(c[0]), float(c[1]), float(c[2]))
            except (TypeError, ValueError):
                pass
    elif profile != MAP_PROFILE_DEV_FAST:
        # prod-baked: conservative default fog for large maps (off by default, enable via run.json).
        pass
    if not enabled:
        render.clearFog()
        return
    fog = Fog("map-fog")
    fog.setMode(Fog.M_linear)
    fog.setColor(LVector4f(color[0], color[1], color[2], 1))
    fog.setLinearRange(start, end)
    render.setFog(render.attachNewNode(fog))


def enhance_map_file_lighting(scene, *, render, lights) -> None:
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

        elif cn in ("light", "light_spot"):
            r, g, b = le.color
            intensity = le.brightness / 255.0
            pl = PointLight(f"hl-light-{i}")
            pl.setColor(LVector4f(r * intensity * 1.2, g * intensity * 1.2, b * intensity * 1.2, 1))
            fade = max(le.fade, 0.1)
            pl.setAttenuation(LVector3f(1.0, 0.0, fade * 8.0))
            pl_np = render.attachNewNode(pl)
            pl_np.setPos(le.origin[0], le.origin[1], le.origin[2])
            render.setLight(pl_np)

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

