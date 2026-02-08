from __future__ import annotations

import time

from ivan.physics.tuning import PhysicsTuning
from ivan.state import IvanState, update_state


def to_persisted_value(value: object) -> float | bool:
    if isinstance(value, bool):
        return value
    return float(value)


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
            "enable_jump_buffer": True,
            "gravity": 39.6196435546875,
            "jump_height": 1.0108081703186036,
            "max_ground_speed": 6.622355737686157,
            "max_air_speed": 6.845157165527343,
            "ground_accel": 49.44859447479248,
            "jump_accel": 31.738659286499026,
            "friction": 13.672204017639162,
            "air_control": 0.24100000381469727,
            "air_counter_strafe_brake": 23.000001525878908,
            "mouse_sensitivity": 0.09978364143371583,
            "jump_buffer_time": 0.2329816741943359,
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
            "enable_jump_buffer": True,
            "jump_accel": 34.0,
            "max_air_speed": 14.0,
            "air_control": 0.30,
            "air_counter_strafe_brake": 18.0,
            "friction": 4.8,
        }
    )

    surf = dict(snap)
    surf.update(
        {
            "surf_enabled": True,
            "autojump_enabled": False,
            "enable_jump_buffer": False,
            "jump_accel": 10.0,
            "max_air_speed": 22.0,
            "air_control": 0.10,
            "air_counter_strafe_brake": 9.0,
            "surf_accel": 70.0,
            "surf_gravity_scale": 0.82,
            "surf_min_normal_z": 0.05,
            "surf_max_normal_z": 0.76,
            "friction": 3.8,
        }
    )

    surf_sky2_server = dict(snap)
    surf_sky2_server.update(
        {
            # Approximation of publicly listed surf_ski_2/surf_sky_2 server cvars:
            # sv_accelerate 5, sv_airaccelerate 100, sv_friction 4, sv_maxspeed 900, sv_gravity 800.
            "gravity": 24.0,
            "max_ground_speed": 23.90,
            "max_air_speed": 23.90,
            "ground_accel": 5.0,
            "jump_accel": 3.0,
            "friction": 4.0,
            "air_control": 0.10,
            "air_counter_strafe_brake": 8.0,
            "surf_enabled": True,
            "surf_accel": 10.0,
            "surf_gravity_scale": 1.0,
            "surf_min_normal_z": 0.05,
            "surf_max_normal_z": 0.72,
            "autojump_enabled": False,
            "enable_jump_buffer": False,
            "walljump_enabled": False,
            "wallrun_enabled": False,
            "vault_enabled": False,
        }
    )
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

    active = state.active_tuning_profile or "surf_bhop_c2"
    if active not in host._profiles:
        active = "surf_bhop_c2"

    # One-way migration for old state files that only had global tuning_overrides.
    # Apply those values to the chosen active profile once at load time.
    if state.tuning_overrides and not state.tuning_profiles and active in host._profiles:
        fields = set(PhysicsTuning.__annotations__.keys())
        for k, v in state.tuning_overrides.items():
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
    if field in ("player_radius", "player_half_height", "crouch_half_height"):
        if host.player is not None:
            host.player.apply_hull_settings()
    if field == "vis_culling_enabled":
        if host.scene is not None:
            try:
                host.scene.set_visibility_enabled(bool(host.tuning.vis_culling_enabled))
            except Exception:
                pass
    if host._active_profile_name in host._profiles:
        host._profiles[host._active_profile_name][field] = to_persisted_value(getattr(host.tuning, field))
    if not host._suspend_tuning_persist:
        host._persist_tuning_field(field)
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
