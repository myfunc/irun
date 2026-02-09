from __future__ import annotations

import time
import math

from ivan.physics.tuning import PhysicsTuning
from ivan.state import IvanState, update_state


def to_persisted_value(value: object) -> float | bool:
    if isinstance(value, bool):
        return value
    return float(value)


def _apply_character_scale_lock(tuning: PhysicsTuning) -> None:
    half_h = max(0.15, float(tuning.player_half_height))
    eye_ratio = 0.625 / 1.05
    radius_ratio = 0.42 / 1.05
    step_ratio = 0.55 / 1.05
    tuning.player_eye_height = max(0.10, half_h * eye_ratio)
    tuning.player_radius = max(0.15, min(0.90, half_h * radius_ratio))
    tuning.step_height = max(0.10, min(1.20, half_h * step_ratio))


def _migrate_to_invariants(profile: dict[str, float | bool]) -> dict[str, float | bool]:
    out = dict(profile)
    g = max(
        0.001,
        float(
            out.get(
                "gravity",
                (2.0 * float(out.get("jump_height", 1.48)))
                / (max(1e-4, float(out.get("jump_apex_time", 0.351))) ** 2),
            )
        ),
    )
    h = max(0.01, float(out.get("jump_height", 1.48)))
    ga = max(0.001, float(out.get("ground_accel", math.log(10.0) / max(1e-4, float(out.get("run_t90", 0.24))))))
    gf = max(
        0.001,
        float(out.get("friction", math.log(10.0) / max(1e-4, float(out.get("ground_stop_t90", 0.22))))),
    )
    vmax = max(0.01, float(out.get("max_ground_speed", 6.643)))
    legacy_air_speed = max(0.01, float(out.get("max_air_speed", vmax * float(out.get("air_speed_mult", 1.695)))))
    legacy_air_accel = max(
        0.001,
        float(out.get("jump_accel", 0.9 / max(1e-4, float(out.get("air_gain_t90", 0.24))))),
    )
    out["jump_apex_time"] = math.sqrt((2.0 * h) / g)
    out["run_t90"] = max(0.03, min(1.2, math.log(10.0) / ga))
    out["ground_stop_t90"] = max(0.03, min(1.2, math.log(10.0) / gf))
    out["air_speed_mult"] = max(0.50, min(4.0, legacy_air_speed / vmax))
    out["air_gain_t90"] = max(0.03, min(1.2, 0.9 / legacy_air_accel))
    out["wallrun_sink_t90"] = max(0.03, min(1.2, float(out.get("wallrun_sink_t90", 0.22))))
    legacy_slide_duration = max(1e-4, float(out.get("slide_duration", out.get("dash_duration", 0.24))))
    legacy_slide_stop_t90 = math.log(10.0) / (math.log(2.0) / legacy_slide_duration)
    out["slide_stop_t90"] = max(
        0.10,
        min(8.0, float(out.get("slide_stop_t90", max(2.0, legacy_slide_stop_t90)))),
    )
    if "slide_half_height_mult" not in out:
        crouch_h = float(out.get("crouch_half_height", 0.68))
        stand_h = max(0.15, float(out.get("player_half_height", 1.05)))
        out["slide_half_height_mult"] = max(0.30, min(1.0, crouch_h / stand_h))
    if "slide_eye_height_mult" not in out:
        crouch_eye = float(out.get("crouch_eye_height", 0.42))
        stand_eye = max(0.1, float(out.get("player_eye_height", 0.625)))
        out["slide_eye_height_mult"] = max(0.40, min(1.0, crouch_eye / stand_eye))
    out["slide_enabled"] = bool(out.get("slide_enabled", out.get("dash_enabled", True)))
    out["coyote_buffer_enabled"] = bool(out.get("coyote_buffer_enabled", out.get("enable_jump_buffer", True)))
    out["camera_speed_fov_max_add"] = max(
        0.0,
        min(
            30.0,
            float(out.get("camera_speed_fov_max_add", out.get("camera_speed_fov_gain", 9.0))),
        ),
    )
    legacy_landing_gain = max(0.0, float(out.get("camera_landing_shake_gain", 1.0)))
    legacy_bhop_gain = max(0.0, float(out.get("camera_bhop_pulse_gain", 0.9)))
    out["camera_event_gain"] = max(
        0.0,
        min(3.0, float(out.get("camera_event_gain", (legacy_landing_gain + legacy_bhop_gain) * 0.5))),
    )
    out["camera_tilt_gain"] = max(0.0, min(2.5, float(out.get("camera_tilt_gain", 1.0))))
    legacy_coyote = float(out.get("coyote_time", 0.0))
    legacy_buffer = float(out.get("jump_buffer_time", 0.0))
    out["grace_period"] = max(
        0.0,
        min(0.35, float(out.get("grace_period", max(legacy_coyote, legacy_buffer, 0.120)))),
    )
    out["custom_friction_enabled"] = True
    for legacy in (
        "invariant_motion_enabled",
        "run_tfull",
        "run_use_tfull",
        "gravity",
        "ground_accel",
        "friction",
        "max_air_speed",
        "jump_accel",
        "air_control",
        "air_counter_strafe_brake",
        "dash_distance",
        "dash_duration",
        "dash_enabled",
        "dash_sweep_enabled",
        "slide_duration",
        "slide_speed_mult",
        "enable_jump_buffer",
        "jump_buffer_time",
        "coyote_time",
        "crouch_speed_multiplier",
        "crouch_half_height",
        "crouch_eye_height",
        "crouch_enabled",
        "camera_speed_fov_gain",
        "camera_landing_shake_gain",
        "camera_bhop_pulse_gain",
    ):
        out.pop(legacy, None)
    return out


def build_default_profiles() -> dict[str, dict[str, float | bool]]:
    base = PhysicsTuning()
    field_names = list(PhysicsTuning.__annotations__.keys())
    snap = {
        f: (bool(getattr(base, f)) if isinstance(getattr(base, f), bool) else float(getattr(base, f)))
        for f in field_names
    }

    surf_bhop_c2 = dict(snap)
    surf_bhop_c2.update(
        {
            "surf_enabled": True,
            "autojump_enabled": True,
            "coyote_buffer_enabled": True,
            "jump_height": 1.0108081703186036,
            "jump_apex_time": math.sqrt((2.0 * 1.0108081703186036) / 39.6196435546875),
            "max_ground_speed": 6.622355737686157,
            "run_t90": max(0.03, min(1.2, math.log(10.0) / 49.44859447479248)),
            "ground_stop_t90": max(0.03, min(1.2, math.log(10.0) / 13.672204017639162)),
            "air_speed_mult": 6.845157165527343 / 6.622355737686157,
            "air_gain_t90": 0.9 / 31.738659286499026,
            "wallrun_sink_t90": 0.22,
            "mouse_sensitivity": 0.09978364143371583,
            "grace_period": 0.2329816741943359,
            "wall_jump_cooldown": 0.9972748947143555,
            "surf_accel": 23.521632385253906,
            "surf_gravity_scale": 0.33837084770202636,
            "surf_min_normal_z": 0.05,
            "surf_max_normal_z": 0.72,
            "grapple_enabled": True,
            "grapple_attach_shorten_speed": 7.307412719726562,
            "grapple_attach_shorten_time": 0.35835513305664063,
            "grapple_pull_strength": 30.263092041015625,
            "grapple_min_length": 0.7406494271755218,
            "grapple_rope_half_width": 0.015153287963867187,
        }
    )
    surf_bhop = dict(surf_bhop_c2)

    bhop = dict(snap)
    bhop.update(
        {
            "surf_enabled": False,
            "autojump_enabled": True,
            "coyote_buffer_enabled": True,
            "run_t90": max(0.03, min(1.2, math.log(10.0) / 34.0)),
            "ground_stop_t90": max(0.03, min(1.2, math.log(10.0) / 4.8)),
            "air_speed_mult": 14.0 / float(base.max_ground_speed),
            "air_gain_t90": 0.9 / 34.0,
        }
    )

    surf = dict(snap)
    surf.update(
        {
            "surf_enabled": True,
            "autojump_enabled": False,
            "coyote_buffer_enabled": False,
            "run_t90": max(0.03, min(1.2, math.log(10.0) / 10.0)),
            "ground_stop_t90": max(0.03, min(1.2, math.log(10.0) / 3.8)),
            "air_speed_mult": 22.0 / float(base.max_ground_speed),
            "air_gain_t90": 0.9 / 10.0,
            "surf_accel": 70.0,
            "surf_gravity_scale": 0.82,
            "surf_min_normal_z": 0.05,
            "surf_max_normal_z": 0.76,
        }
    )

    surf_sky2_server = dict(snap)
    surf_sky2_server.update(
        {
            # Approximation of publicly listed surf_ski_2/surf_sky_2 server cvars mapped to invariants.
            "max_ground_speed": 23.90,
            "run_t90": max(0.03, min(1.2, math.log(10.0) / 5.0)),
            "ground_stop_t90": max(0.03, min(1.2, math.log(10.0) / 4.0)),
            "air_speed_mult": 1.0,
            "air_gain_t90": 0.9 / 3.0,
            "surf_enabled": True,
            "surf_accel": 10.0,
            "surf_gravity_scale": 1.0,
            "surf_min_normal_z": 0.05,
            "surf_max_normal_z": 0.72,
            "autojump_enabled": False,
            "coyote_buffer_enabled": False,
            "walljump_enabled": False,
            "wallrun_enabled": False,
            "vault_enabled": False,
        }
    )

    surf_bhop_c2 = _migrate_to_invariants(surf_bhop_c2)
    surf_bhop = _migrate_to_invariants(surf_bhop)
    bhop = _migrate_to_invariants(bhop)
    surf = _migrate_to_invariants(surf)
    surf_sky2_server = _migrate_to_invariants(surf_sky2_server)

    return {
        "surf_bhop_c2": surf_bhop_c2,
        "surf_bhop": surf_bhop,
        "bhop": bhop,
        "surf": surf,
        "surf_sky2_server": surf_sky2_server,
    }


def profile_names(host) -> list[str]:
    ordered = ["surf_bhop_c2", "surf_bhop", "bhop", "surf", "surf_sky2_server"]
    extras = sorted([n for n in host._profiles.keys() if n not in ordered])
    return [n for n in ordered if n in host._profiles] + extras


def load_profiles_from_state(host, state: IvanState) -> None:
    host._profiles = {name: dict(values) for name, values in host._default_profiles.items()}
    for name, values in state.tuning_profiles.items():
        host._profiles[name] = dict(values)

    for profile in host._profiles.values():
        migrated = _migrate_to_invariants(profile)
        profile.clear()
        profile.update(migrated)

    active = state.active_tuning_profile or "surf_bhop_c2"
    if active not in host._profiles:
        active = "surf_bhop_c2"

    # One-way migration for old state files that only had global tuning_overrides.
    # Apply those values to the chosen active profile once at load time.
    if state.tuning_overrides and not state.tuning_profiles and active in host._profiles:
        fields = set(PhysicsTuning.__annotations__.keys())
        migrated_overrides = _migrate_to_invariants(dict(state.tuning_overrides))
        for k, v in migrated_overrides.items():
            if k in fields:
                host._profiles[active][k] = v

    host._active_profile_name = active
    apply_profile_snapshot(host, host._profiles[host._active_profile_name], persist=False)


def persist_profiles_state(host) -> None:
    active_snapshot = host._profiles.get(host._active_profile_name, {})
    update_state(
        tuning_profiles=host._profiles,
        active_tuning_profile=host._active_profile_name,
        tuning_overrides=active_snapshot,
    )


def apply_profile_snapshot(host, values: dict[str, float | bool], *, persist: bool) -> None:
    fields = set(PhysicsTuning.__annotations__.keys())
    host._suspend_tuning_persist = True
    try:
        for field, value in values.items():
            if field not in fields:
                continue
            setattr(host.tuning, field, value)
    finally:
        host._suspend_tuning_persist = False
    if bool(getattr(host.tuning, "character_scale_lock_enabled", False)):
        _apply_character_scale_lock(host.tuning)
    if getattr(host, "player", None) is not None:
        host.player.apply_hull_settings()
    if hasattr(host, "ui") and host.ui is not None:
        host.ui.sync_from_tuning()
    if persist:
        persist_profiles_state(host)


def make_profile_copy_name(host, base_name: str) -> str:
    root = (base_name[:12] if base_name else "profile").strip("_-")
    if not root:
        root = "profile"
    candidate = f"{root}_copy"
    if candidate not in host._profiles:
        return candidate
    for i in range(2, 100):
        name = f"{root}_c{i}"
        if name not in host._profiles:
            return name
    return f"{root}_{len(host._profiles)}"


def save_active_profile(host) -> None:
    snapshot = {field: to_persisted_value(getattr(host.tuning, field)) for field in PhysicsTuning.__annotations__.keys()}

    if host._active_profile_name in host._default_profile_names:
        new_name = make_profile_copy_name(host, host._active_profile_name)
        host._profiles[new_name] = snapshot
        host._active_profile_name = new_name
    else:
        host._profiles[host._active_profile_name] = snapshot
    persist_profiles_state(host)
    host.ui.set_profiles(profile_names(host), host._active_profile_name)


def current_tuning_snapshot(host) -> dict[str, float | bool]:
    return {field: to_persisted_value(getattr(host.tuning, field)) for field in PhysicsTuning.__annotations__.keys()}


def apply_authoritative_tuning(host, *, tuning: dict[str, float | bool], version: int) -> None:
    if not isinstance(tuning, dict):
        return
    host._net_authoritative_tuning = dict(tuning)
    host._net_authoritative_tuning_version = max(int(host._net_authoritative_tuning_version), int(version))
    # Use the host method to allow tests/overrides to hook this behavior.
    host._apply_profile_snapshot(dict(host._net_authoritative_tuning), persist=False)
    if (
        int(host._net_cfg_apply_pending_version) > 0
        and int(host._net_authoritative_tuning_version) >= int(host._net_cfg_apply_pending_version)
    ):
        host._net_cfg_apply_pending_version = 0
        host._net_cfg_apply_sent_at = 0.0
        host.ui.set_status(f"Server config updated (cfg_v={host._net_authoritative_tuning_version}).")


def send_tuning_to_server(host) -> None:
    if not host._net_connected or not host._net_can_configure or host._net_client is None:
        return
    snap = current_tuning_snapshot(host)
    host._net_authoritative_tuning = dict(snap)
    host._net_cfg_apply_pending_version = max(
        int(host._net_cfg_apply_pending_version),
        int(host._net_authoritative_tuning_version) + 1,
    )
    host._net_cfg_apply_sent_at = time.monotonic()
    host._net_client.send_tuning(snap)


def on_tuning_change(host, field: str) -> None:
    if host._net_connected and not host._net_can_configure:
        if host._net_authoritative_tuning:
            host._apply_profile_snapshot(dict(host._net_authoritative_tuning), persist=False)
        host.ui.set_status("Server config is host-only. Local tuning changes are blocked.")
        return
    persist_fields: list[str] = [str(field)]
    if field == "player_half_height":
        # Keep camera framing proportional to hull height while iterating character scale.
        default_eye_ratio = 0.625 / 1.05
        host.tuning.player_eye_height = max(0.10, float(host.tuning.player_half_height) * float(default_eye_ratio))
        persist_fields.append("player_eye_height")

    if field in ("player_half_height", "character_scale_lock_enabled") and bool(host.tuning.character_scale_lock_enabled):
        _apply_character_scale_lock(host.tuning)
        for dep in ("player_eye_height", "player_radius", "step_height"):
            if dep not in persist_fields:
                persist_fields.append(dep)

    if any(f in ("player_radius", "player_half_height", "slide_half_height_mult") for f in persist_fields):
        if host.player is not None:
            host.player.apply_hull_settings()
    if field == "vis_culling_enabled":
        if host.scene is not None:
            try:
                host.scene.set_visibility_enabled(bool(host.tuning.vis_culling_enabled))
            except Exception:
                pass
    if host._active_profile_name in host._profiles:
        for persist_field in persist_fields:
            host._profiles[host._active_profile_name][persist_field] = to_persisted_value(
                getattr(host.tuning, persist_field)
            )
    if not host._suspend_tuning_persist:
        for persist_field in persist_fields:
            host._persist_tuning_field(persist_field)
    if host._net_connected and host._net_can_configure:
        host._send_tuning_to_server()


def apply_profile(host, profile_name: str) -> None:
    if profile_name not in host._profiles:
        return
    if host._net_connected and not host._net_can_configure:
        if host._net_authoritative_tuning:
            host._apply_profile_snapshot(dict(host._net_authoritative_tuning), persist=False)
        host.ui.set_status("Server config is host-only. Profile switch is blocked for this client.")
        host.ui.set_profiles(host._profile_names(), host._active_profile_name)
        return
    host._active_profile_name = profile_name
    host._apply_profile_snapshot(host._profiles[profile_name], persist=True)
    if host._net_connected and host._net_can_configure:
        host._send_tuning_to_server()
        host.ui.set_status(f"Applying profile '{profile_name}' to server...")
    host.ui.set_profiles(host._profile_names(), host._active_profile_name)


__all__ = [
    "apply_authoritative_tuning",
    "apply_profile",
    "apply_profile_snapshot",
    "build_default_profiles",
    "current_tuning_snapshot",
    "load_profiles_from_state",
    "on_tuning_change",
    "persist_profiles_state",
    "profile_names",
    "save_active_profile",
    "send_tuning_to_server",
    "to_persisted_value",
]
