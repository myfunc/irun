from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import TextNode

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.number_control import NumberControl


class DebugUI:
    def __init__(
        self,
        *,
        aspect2d,
        tuning: PhysicsTuning,
        on_tuning_change,
    ) -> None:
        self._tuning = tuning
        self._on_tuning_change = on_tuning_change

        self.debug_root = DirectFrame(
            parent=aspect2d,
            frameColor=(0.08, 0.08, 0.08, 0.80),
            frameSize=(-1.30, -0.12, -0.95, 0.95),
            pos=(0, 0, 0),
            relief=DGG.FLAT,
        )

        DirectLabel(
            parent=self.debug_root,
            text="Debug / Physics Tuning (ESC)",
            text_scale=0.055,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-1.22, 0, 0.88),
        )

        self.speed_hud_label = DirectLabel(
            parent=aspect2d,
            text="Speed: 0 u/s",
            text_scale=0.042,
            text_align=TextNode.ACenter,
            text_fg=(0.94, 0.94, 0.94, 0.95),
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, 0.93),
        )

        controls = [
            ("gravity", 8.0, 60.0),
            ("jump_speed", 3.0, 25.0),
            ("max_ground_speed", 3.0, 40.0),
            ("max_air_speed", 3.0, 45.0),
            ("ground_accel", 5.0, 140.0),
            ("air_accel", 1.0, 90.0),
            ("friction", 0.0, 25.0),
            ("air_control", 0.0, 1.0),
            ("air_counter_strafe_brake", 5.0, 90.0),
            ("sprint_multiplier", 1.0, 2.0),
            ("mouse_sensitivity", 0.02, 0.40),
            ("wall_jump_boost", 1.0, 20.0),
            ("coyote_time", 0.0, 0.35),
            ("jump_buffer_time", 0.0, 0.35),
            ("max_ground_slope_deg", 20.0, 70.0),
            ("step_height", 0.0, 1.2),
            ("ground_snap_dist", 0.0, 0.6),
            ("player_radius", 0.20, 0.80),
            ("player_half_height", 0.70, 1.60),
            ("player_eye_height", 0.20, 1.30),
        ]

        self._number_controls: dict[str, NumberControl] = {}
        x = -1.22
        y = 0.72
        step = 0.105

        for name, minimum, maximum in controls:
            ctrl = NumberControl(
                parent=self.debug_root,
                name=name,
                x=x,
                y=y,
                value=float(getattr(self._tuning, name)),
                minimum=minimum,
                maximum=maximum,
                on_change=lambda val, field=name: self._set_tuning(field, val),
            )
            self._number_controls[name] = ctrl
            y -= step

        self._toggle_buttons: dict[str, DirectButton] = {}
        self._make_toggle_button("enable_coyote", -1.22, -0.68)
        self._make_toggle_button("enable_jump_buffer", -0.90, -0.68)
        self._make_toggle_button("walljump_enabled", -1.22, -0.78)
        self._make_toggle_button("wallrun_enabled", -0.90, -0.78)
        self._make_toggle_button("vault_enabled", -1.22, -0.88)
        self._make_toggle_button("grapple_enabled", -0.90, -0.88)

        self.status_label = DirectLabel(
            parent=self.debug_root,
            text="",
            text_scale=0.047,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-1.22, 0, -0.58),
        )

        self.debug_root.hide()

    def show(self) -> None:
        self.debug_root.show()

    def hide(self) -> None:
        self.debug_root.hide()

    def set_speed(self, hspeed: float) -> None:
        self.speed_hud_label["text"] = f"Speed: {int(hspeed)} u/s"

    def set_status(self, text: str) -> None:
        self.status_label["text"] = text

    def _set_tuning(self, field: str, value: float) -> None:
        setattr(self._tuning, field, value)
        self._on_tuning_change(field)

    def _make_toggle_button(self, field: str, x: float, y: float) -> None:
        button = DirectButton(
            parent=self.debug_root,
            text="",
            text_scale=0.036,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.20, 0.20, 0.20, 0.95),
            relief=DGG.FLAT,
            command=self._toggle_bool_field,
            extraArgs=[field],
            scale=0.07,
            frameSize=(-2.1, 2.1, -0.55, 0.55),
            pos=(x, 0, y),
        )
        self._toggle_buttons[field] = button
        self._refresh_toggle_button(field)

    def _refresh_toggle_button(self, field: str) -> None:
        value = bool(getattr(self._tuning, field))
        state = "ON" if value else "OFF"
        self._toggle_buttons[field]["text"] = f"{field}: {state}"

    def _toggle_bool_field(self, field: str) -> None:
        setattr(self._tuning, field, not bool(getattr(self._tuning, field)))
        self._refresh_toggle_button(field)
        self._on_tuning_change(field)

