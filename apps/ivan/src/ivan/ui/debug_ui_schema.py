from __future__ import annotations

# Keep these structures stable: tests and profile wiring depend on them.
NUMERIC_CONTROLS: list[tuple[str, float, float]] = [
    ("max_ground_speed", 3.0, 40.0),
    ("run_t90", 0.03, 1.20),
    ("ground_stop_t90", 0.03, 1.20),
    ("air_speed_mult", 0.50, 4.00),
    ("air_gain_t90", 0.03, 1.20),
    ("wallrun_sink_t90", 0.03, 1.20),
    ("jump_height", 0.2, 4.0),
    ("jump_apex_time", 0.08, 1.20),
    ("jump_buffer_time", 0.0, 0.35),
    ("coyote_time", 0.0, 0.35),
    ("slide_stop_t90", 0.10, 8.00),
]

TOGGLE_CONTROLS: list[str] = [
    "autojump_enabled",
    "coyote_buffer_enabled",
    "custom_friction_enabled",
    "slide_enabled",
    "wallrun_enabled",
    "harness_camera_smoothing_enabled",
    "harness_animation_root_motion_enabled",
    "surf_enabled",
]

GROUPS: list[tuple[str, list[str], list[str]]] = [
    (
        "Movement Core",
        [
            "max_ground_speed",
            "run_t90",
            "ground_stop_t90",
            "air_speed_mult",
            "air_gain_t90",
            "wallrun_sink_t90",
            "jump_height",
            "jump_apex_time",
            "jump_buffer_time",
            "coyote_time",
            "slide_stop_t90",
        ],
        [
            "autojump_enabled",
            "coyote_buffer_enabled",
            "slide_enabled",
            "custom_friction_enabled",
            "wallrun_enabled",
        ],
    ),
    (
        "Surf",
        [],
        ["surf_enabled"],
    ),
    (
        "Harness",
        [],
        [
            "harness_camera_smoothing_enabled",
            "harness_animation_root_motion_enabled",
        ],
    ),
]

FIELD_LABELS: dict[str, str] = {
    "max_ground_speed": "Vmax (max speed)",
    "run_t90": "run time to 90%",
    "ground_stop_t90": "ground stop time to 90%",
    "air_speed_mult": "air speed multiplier",
    "air_gain_t90": "air gain time to 90%",
    "wallrun_sink_t90": "wallrun sink time to 90%",
    "jump_height": "jump height",
    "jump_apex_time": "jump apex time",
    "jump_buffer_time": "input buffer",
    "coyote_time": "coyote time",
    "slide_stop_t90": "slide stop time to 90%",
}

FIELD_HELP: dict[str, str] = {
    "max_ground_speed": "Lower: lower target run speed. Higher: higher target run speed under held input.",
    "run_t90": "Lower: snappier exponential run response. Higher: slower convergence to target speed.",
    "ground_stop_t90": "Lower: faster slowdown when coasting on ground. Higher: longer inertia before coming to rest.",
    "air_speed_mult": "Lower: tighter air-speed cap relative to Vmax. Higher: allows more carry and bhop top speed.",
    "air_gain_t90": "Lower: faster air speed gain (stronger bhop/strafe gain). Higher: slower air speed build-up.",
    "wallrun_sink_t90": "Lower: wallrun vertical sink stabilizes faster. Higher: slower sink response and floatier wallrun.",
    "jump_height": "Lower: shorter hop height. Higher: higher jump apex.",
    "jump_apex_time": "Lower: shorter time to jump apex (snappier pop). Higher: longer float to apex.",
    "jump_buffer_time": "Lower: tighter jump timing before landing. Higher: more forgiving early jump presses.",
    "coyote_time": "Lower: less late-jump forgiveness after leaving ground. Higher: more forgiving coyote window.",
    "slide_stop_t90": "Lower: slide momentum bleeds faster on ground. Higher: slide preserves carried speed longer before decelerating.",
    "autojump_enabled": "Lower (OFF): jump requires press timing each hop. Higher (ON): holding jump auto-queues grounded hops.",
    "coyote_buffer_enabled": "Lower (OFF): disable coyote + buffered leniency windows. Higher (ON): enable forgiving jump windows.",
    "custom_friction_enabled": "Lower (OFF): skip custom ground friction for isolation tests. Higher (ON): use normal friction model.",
    "slide_enabled": "Lower (OFF): shift slide action disabled. Higher (ON): shift engages powerslide with low profile hull.",
    "wallrun_enabled": "Lower (OFF): wallrun behavior disabled. Higher (ON): run along valid wall contacts with camera tilt + wallrun jump behavior.",
    "surf_enabled": "Lower (OFF): disable surf behavior entirely. Higher (ON): enable surf logic on surfable ramp normals.",
    "harness_camera_smoothing_enabled": "Lower (OFF): disable camera smoothing in harness mode. Higher (ON): enable camera smoothing.",
    "harness_animation_root_motion_enabled": "Lower (OFF): disable animation/root-motion influence. Higher (ON): enable animation/root-motion influence.",
}
