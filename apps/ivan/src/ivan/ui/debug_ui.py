from __future__ import annotations

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.number_control import NumberControl


class DebugUI:
    NUMERIC_CONTROLS: list[tuple[str, float, float]] = [
        ("gravity", 8.0, 60.0),
        ("jump_height", 0.2, 4.0),
        ("max_ground_speed", 3.0, 40.0),
        ("max_air_speed", 3.0, 45.0),
        ("ground_accel", 5.0, 140.0),
        ("jump_accel", 1.0, 90.0),
        ("friction", 0.0, 25.0),
        ("air_control", 0.0, 1.0),
        ("air_counter_strafe_brake", 0.0, 90.0),
        ("mouse_sensitivity", 0.02, 0.40),
        ("wall_jump_boost", 1.0, 20.0),
        ("vault_jump_multiplier", 1.0, 2.5),
        ("vault_forward_boost", 0.0, 6.0),
        ("vault_min_ledge_height", 0.05, 0.8),
        ("vault_max_ledge_height", 0.4, 2.5),
        ("vault_cooldown", 0.0, 1.0),
        ("coyote_time", 0.0, 0.35),
        ("jump_buffer_time", 0.0, 0.35),
        ("max_ground_slope_deg", 20.0, 70.0),
        ("step_height", 0.0, 1.2),
        ("ground_snap_dist", 0.0, 0.6),
        ("player_radius", 0.20, 0.80),
        ("player_half_height", 0.70, 1.60),
        ("player_eye_height", 0.20, 1.30),
    ]
    TOGGLE_CONTROLS: list[str] = [
        "enable_coyote",
        "enable_jump_buffer",
        "walljump_enabled",
        "wallrun_enabled",
        "vault_enabled",
        "grapple_enabled",
    ]

    FIELD_HELP: dict[str, str] = {
        "gravity": "Lower: floatier movement and longer airtime. Higher: faster fall and snappier landings.",
        "jump_height": "Lower: shorter hop height. Higher: higher jump apex and longer time before landing.",
        "max_ground_speed": "Lower: slower top run speed on ground. Higher: faster top run speed on ground.",
        "max_air_speed": "Lower: lower speed cap while airborne. Higher: allows faster airborne travel.",
        "ground_accel": "Lower: slower speed build-up on ground. Higher: faster acceleration to top ground speed.",
        "jump_accel": "Lower: weaker bunnyhop/strafe acceleration in air. Higher: stronger airborne speed gain.",
        "friction": "Lower: keep momentum longer on ground. Higher: lose ground speed faster when input stops.",
        "air_control": "Lower: less steering authority in air. Higher: tighter mid-air steering.",
        "air_counter_strafe_brake": "Lower: softer airborne counter-strafe braking. Higher: much more aggressive speed reduction without reversing.",
        "mouse_sensitivity": "Lower: slower camera turn response. Higher: faster camera turn response.",
        "wall_jump_boost": "Lower: weaker horizontal push from wall jumps. Higher: stronger push away from wall.",
        "vault_jump_multiplier": "Lower: vault jump closer to normal jump height. Higher: vault launches higher.",
        "vault_forward_boost": "Lower: little forward speed added by vault. Higher: stronger vault forward burst.",
        "vault_min_ledge_height": "Lower: vault can trigger on smaller ledges. Higher: requires a taller ledge.",
        "vault_max_ledge_height": "Lower: only low-to-mid ledges are vaultable. Higher: allows vaulting taller ledges.",
        "vault_cooldown": "Lower: vault can retrigger sooner. Higher: longer delay between vaults.",
        "coyote_time": "Lower: less post-edge jump forgiveness. Higher: more time to jump after leaving ground.",
        "jump_buffer_time": "Lower: tighter jump timing before landing. Higher: more forgiving early jump presses.",
        "max_ground_slope_deg": "Lower: fewer slopes count as walkable. Higher: steeper slopes remain walkable.",
        "step_height": "Lower: smaller obstacles can be stepped over. Higher: taller steps are auto-climbed.",
        "ground_snap_dist": "Lower: less ground sticking on small drops. Higher: stronger snap to nearby walkable ground.",
        "player_radius": "Lower: narrower collision capsule. Higher: wider body collision.",
        "player_half_height": "Lower: shorter collision capsule. Higher: taller collision capsule.",
        "player_eye_height": "Lower: camera sits lower. Higher: camera sits higher.",
        "enable_coyote": "Lower (OFF): no coyote-time forgiveness. Higher (ON): edge grace jumps allowed.",
        "enable_jump_buffer": "Lower (OFF): no jump input buffering. Higher (ON): buffered jump before landing.",
        "walljump_enabled": "Lower (OFF): wall-jumps disabled. Higher (ON): wall-jumps enabled.",
        "wallrun_enabled": "Lower (OFF): wallrun disabled. Higher (ON): side wallrun enabled.",
        "vault_enabled": "Lower (OFF): ledge vault disabled. Higher (ON): second-jump ledge vault enabled.",
        "grapple_enabled": "Lower (OFF): grapple impulse disabled. Higher (ON): grapple impulse enabled on LMB.",
    }

    def __init__(
        self,
        *,
        aspect2d,
        tuning: PhysicsTuning,
        on_tuning_change,
    ) -> None:
        self._tuning = tuning
        self._on_tuning_change = on_tuning_change
        self._field_help = dict(self.FIELD_HELP)

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())

        panel_top = 0.95
        # aspect2d vertical span is 2.0 units (-1 to 1); keep debug panel within 2/3 of that.
        panel_height = 2.0 * (2.0 / 3.0)
        panel_bottom = panel_top - panel_height

        panel_left = -aspect_ratio + 0.04
        panel_inner_padding_x = 0.08
        panel_inner_padding_y = 0.08
        column_width = 0.98
        base_row_step = 0.105

        title_y = panel_top - panel_inner_padding_y
        list_top = title_y - 0.18
        status_y = panel_bottom + 0.07
        list_bottom = status_y + 0.14

        list_height = max(0.1, list_top - list_bottom)
        max_rows = max(1, int(math.floor(list_height / base_row_step)) + 1)

        self.debug_root = DirectFrame(
            parent=aspect2d,
            frameColor=(0.08, 0.08, 0.08, 0.80),
            frameSize=(0.0, 1.0, panel_bottom, panel_top),
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
            pos=(panel_left + panel_inner_padding_x, 0, title_y),
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

        self._tooltip_label = DirectLabel(
            parent=self.debug_root,
            text="",
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=(0.98, 0.96, 0.75, 0.95),
            frameColor=(0, 0, 0, 0),
            pos=(panel_left + panel_inner_padding_x, 0, panel_bottom + 0.035),
            text_wordwrap=48,
        )
        self._tooltip_label.hide()

        numeric_controls = list(self.NUMERIC_CONTROLS)
        toggle_controls = list(self.TOGGLE_CONTROLS)

        total_items = len(numeric_controls) + len(toggle_controls)
        desired_columns = max(1, int(math.ceil(total_items / max_rows)))

        right_bound = aspect_ratio - 0.04
        max_panel_width = right_bound - panel_left
        max_columns = max(1, int((max_panel_width - (panel_inner_padding_x * 2.0)) // column_width))
        columns = min(desired_columns, max_columns)
        rows_per_col = int(math.ceil(total_items / columns))
        row_step = list_height / max(1, rows_per_col - 1)
        row_step = min(base_row_step, row_step)

        panel_width = (panel_inner_padding_x * 2.0) + (columns * column_width)
        panel_width = min(panel_width, max_panel_width)

        self.debug_root["frameSize"] = (panel_left, panel_left + panel_width, panel_bottom, panel_top)

        self._number_controls: dict[str, NumberControl] = {}
        item_index = 0

        for name, minimum, maximum in numeric_controls:
            col = item_index // rows_per_col
            row = item_index % rows_per_col
            x = panel_left + panel_inner_padding_x + (col * column_width)
            y = list_top - (row * row_step)
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
            tooltip = self._field_help.get(name)
            if tooltip:
                self._bind_tooltip(ctrl.label, tooltip)
                self._bind_tooltip(ctrl.slider, tooltip)
                self._bind_tooltip(ctrl.entry, tooltip)
            item_index += 1

        self._toggle_buttons: dict[str, DirectButton] = {}
        self._toggle_labels: dict[str, DirectLabel] = {}
        for name in toggle_controls:
            col = item_index // rows_per_col
            row = item_index % rows_per_col
            x = panel_left + panel_inner_padding_x + (col * column_width)
            y = list_top - (row * row_step)
            self._make_toggle_row(name, x, y)
            item_index += 1

        self.status_label = DirectLabel(
            parent=aspect2d,
            text="",
            text_scale=0.040,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-aspect_ratio + 0.06, 0, -0.92),
        )

        self.debug_root.hide()

    def show(self) -> None:
        self.debug_root.show()
        self.status_label.hide()
        self._tooltip_label.hide()

    def hide(self) -> None:
        self.debug_root.hide()
        self.status_label.show()
        self._tooltip_label.hide()

    def set_speed(self, hspeed: float) -> None:
        self.speed_hud_label["text"] = f"Speed: {int(hspeed)} u/s"

    def set_status(self, text: str) -> None:
        self.status_label["text"] = text

    def _set_tuning(self, field: str, value: float) -> None:
        setattr(self._tuning, field, value)
        self._on_tuning_change(field)

    def _make_toggle_row(self, field: str, x: float, y: float) -> None:
        pretty_name = field.replace("_", " ")
        label = DirectLabel(
            parent=self.debug_root,
            text=pretty_name,
            text_scale=0.042,
            text_align=TextNode.ALeft,
            text_fg=(0.93, 0.93, 0.93, 1),
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
        )
        self._toggle_labels[field] = label

        button = DirectButton(
            parent=self.debug_root,
            text=("OFF", "OFF", "OFF", "OFF"),
            text_scale=0.052,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.20, 0.20, 0.20, 0.95),
            relief=DGG.FLAT,
            command=self._toggle_bool_field,
            extraArgs=[field],
            scale=0.060,
            frameSize=(-2.1, 2.1, -0.55, 0.55),
            pos=(x + 0.84, 0, y - 0.01),
        )
        self._toggle_buttons[field] = button
        self._refresh_toggle_button(field)
        tooltip = self._field_help.get(field)
        if tooltip:
            self._bind_tooltip(label, tooltip)
            self._bind_tooltip(button, tooltip)

    def _refresh_toggle_button(self, field: str) -> None:
        value = bool(getattr(self._tuning, field))
        state = "ON" if value else "OFF"
        self._toggle_buttons[field]["text"] = (state, state, state, state)
        if value:
            self._toggle_buttons[field]["frameColor"] = (0.21, 0.44, 0.22, 0.95)
        else:
            self._toggle_buttons[field]["frameColor"] = (0.20, 0.20, 0.20, 0.95)

    def _toggle_bool_field(self, field: str) -> None:
        setattr(self._tuning, field, not bool(getattr(self._tuning, field)))
        self._refresh_toggle_button(field)
        self._on_tuning_change(field)

    def _bind_tooltip(self, widget, text: str) -> None:
        widget.bind(DGG.ENTER, lambda _evt, tip=text: self._show_tooltip(tip))
        widget.bind(DGG.EXIT, lambda _evt: self._hide_tooltip())

    def _show_tooltip(self, text: str) -> None:
        self._tooltip_label["text"] = text
        self._tooltip_label.show()

    def _hide_tooltip(self) -> None:
        self._tooltip_label.hide()
