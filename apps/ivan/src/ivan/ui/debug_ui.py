from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectScrolledFrame
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.number_control import NumberControl


@dataclass
class _GroupUI:
    box: DirectFrame
    header_btn: DirectButton
    content: DirectFrame
    expanded: bool
    content_height: float


class DebugUI:
    NUMERIC_CONTROLS: list[tuple[str, float, float]] = [
        ("gravity", 8.0, 60.0),
        ("jump_height", 0.2, 4.0),
        ("max_ground_speed", 3.0, 40.0),
        ("max_air_speed", 3.0, 45.0),
        ("ground_accel", 5.0, 140.0),
        ("jump_accel", 1.0, 140.0),
        ("friction", 0.0, 25.0),
        ("air_control", 0.0, 1.0),
        ("air_counter_strafe_brake", 0.0, 90.0),
        ("mouse_sensitivity", 0.02, 0.40),
        ("crouch_speed_multiplier", 0.2, 1.0),
        ("crouch_half_height", 0.30, 1.20),
        ("crouch_eye_height", 0.15, 1.20),
        ("wall_jump_boost", 1.0, 20.0),
        ("wall_jump_cooldown", 0.0, 3.0),
        ("surf_accel", 0.0, 120.0),
        ("surf_gravity_scale", 0.0, 2.5),
        ("surf_min_normal_z", 0.01, 0.50),
        ("surf_max_normal_z", 0.20, 0.95),
        ("vault_jump_multiplier", 1.0, 2.5),
        ("vault_forward_boost", 0.0, 6.0),
        ("vault_min_ledge_height", 0.05, 0.8),
        ("vault_max_ledge_height", 0.4, 2.5),
        ("vault_cooldown", 0.0, 1.0),
        ("coyote_time", 0.0, 0.35),
        ("jump_buffer_time", 0.0, 0.35),
        ("noclip_speed", 1.0, 35.0),
        ("max_ground_slope_deg", 20.0, 70.0),
        ("step_height", 0.0, 1.2),
        ("ground_snap_dist", 0.0, 0.6),
        ("player_radius", 0.20, 0.80),
        ("player_half_height", 0.70, 1.60),
        ("player_eye_height", 0.20, 1.30),
        ("course_marker_half_extent_xy", 0.5, 20.0),
        ("course_marker_half_extent_z", 0.25, 20.0),
    ]
    TOGGLE_CONTROLS: list[str] = [
        "enable_coyote",
        "enable_jump_buffer",
        "autojump_enabled",
        "noclip_enabled",
        "surf_enabled",
        "walljump_enabled",
        "wallrun_enabled",
        "vault_enabled",
        "crouch_enabled",
        "grapple_enabled",
    ]

    GROUPS: list[tuple[str, list[str], list[str]]] = [
        (
            "Movement Core",
            [
                "gravity",
                "max_ground_speed",
                "ground_accel",
                "friction",
                "max_air_speed",
                "jump_accel",
                "air_control",
                "air_counter_strafe_brake",
                "mouse_sensitivity",
            ],
            [],
        ),
        (
            "Surf / Air Tech",
            [
                "surf_accel",
                "surf_gravity_scale",
                "surf_min_normal_z",
                "surf_max_normal_z",
                "wall_jump_boost",
                "wall_jump_cooldown",
            ],
            ["surf_enabled", "walljump_enabled", "wallrun_enabled"],
        ),
        (
            "Jump / Vault",
            [
                "jump_height",
                "coyote_time",
                "jump_buffer_time",
                "vault_jump_multiplier",
                "vault_forward_boost",
                "vault_min_ledge_height",
                "vault_max_ledge_height",
                "vault_cooldown",
            ],
            ["enable_coyote", "enable_jump_buffer", "autojump_enabled", "vault_enabled"],
        ),
        (
            "Collision / Hull",
            [
                "max_ground_slope_deg",
                "step_height",
                "ground_snap_dist",
                "player_radius",
                "player_half_height",
                "player_eye_height",
                "crouch_speed_multiplier",
                "crouch_half_height",
                "crouch_eye_height",
                "noclip_speed",
            ],
            ["crouch_enabled", "noclip_enabled", "grapple_enabled"],
        ),
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
        "air_counter_strafe_brake": "Lower: softer airborne counter-strafe braking. Higher: much more aggressive speed reduction.",
        "mouse_sensitivity": "Lower: slower camera turn response. Higher: faster camera turn response.",
        "crouch_speed_multiplier": "Lower: much slower movement while crouched. Higher: crouched speed closer to normal speed.",
        "crouch_half_height": "Lower: shorter crouch collision height. Higher: taller crouch collision height.",
        "crouch_eye_height": "Lower: camera sits lower while crouched. Higher: camera sits higher while crouched.",
        "wall_jump_boost": "Lower: weaker horizontal push from wall jumps. Higher: stronger push away from wall.",
        "wall_jump_cooldown": "Lower: wall-jumps can repeat rapidly. Higher: longer lockout between wall-jumps.",
        "surf_accel": "Lower: weaker strafe-driven gain on surf ramps. Higher: stronger strafe acceleration.",
        "surf_gravity_scale": "Lower: gentler gravity pull while surfing. Higher: stronger gravity pull along the ramp.",
        "surf_min_normal_z": "Lower: allows surfing on flatter ramps. Higher: requires steeper ramps to enter surf state.",
        "surf_max_normal_z": "Lower: only very steep ramps are surfable. Higher: allows less-steep ramps to count as surf.",
        "vault_jump_multiplier": "Lower: vault jump closer to normal jump height. Higher: vault launches higher.",
        "vault_forward_boost": "Lower: little forward speed from vault. Higher: stronger vault forward burst.",
        "vault_min_ledge_height": "Lower: vault can trigger on smaller ledges. Higher: requires a taller ledge.",
        "vault_max_ledge_height": "Lower: only low-to-mid ledges are vaultable. Higher: allows taller ledges.",
        "vault_cooldown": "Lower: vault can retrigger sooner. Higher: longer delay between vaults.",
        "coyote_time": "Lower: less post-edge jump forgiveness. Higher: more time to jump after leaving ground.",
        "jump_buffer_time": "Lower: tighter jump timing before landing. Higher: more forgiving early jump presses.",
        "noclip_speed": "Lower: slower free-fly movement in noclip mode. Higher: faster noclip traversal speed.",
        "max_ground_slope_deg": "Lower: fewer slopes count as walkable. Higher: steeper slopes remain walkable.",
        "step_height": "Lower: smaller obstacles can be stepped over. Higher: taller steps are auto-climbed.",
        "ground_snap_dist": "Lower: less ground sticking on small drops. Higher: stronger snap to nearby walkable ground.",
        "player_radius": "Lower: narrower collision capsule. Higher: wider body collision.",
        "player_half_height": "Lower: shorter collision capsule. Higher: taller collision capsule.",
        "player_eye_height": "Lower: camera sits lower. Higher: camera sits higher.",
        "course_marker_half_extent_xy": "Lower: smaller Start/Finish trigger volumes (harder to hit). Higher: larger trigger volumes (easier to hit).",
        "course_marker_half_extent_z": "Lower: shorter Start/Finish trigger volumes (harder to hit). Higher: taller trigger volumes (easier to hit).",
        "enable_coyote": "Lower (OFF): no coyote-time forgiveness. Higher (ON): edge grace jumps allowed.",
        "enable_jump_buffer": "Lower (OFF): no jump input buffering. Higher (ON): buffered jump before landing.",
        "autojump_enabled": "Lower (OFF): jump on press only. Higher (ON): holding jump repeatedly queues jumps.",
        "noclip_enabled": "Lower (OFF): normal collision movement. Higher (ON): collision-free noclip movement.",
        "surf_enabled": "Lower (OFF): slanted-surface surfing disabled. Higher (ON): surf ramps work with strafe hold.",
        "walljump_enabled": "Lower (OFF): wall-jumps disabled. Higher (ON): wall-jumps enabled.",
        "wallrun_enabled": "Lower (OFF): wallrun disabled. Higher (ON): side wallrun enabled.",
        "vault_enabled": "Lower (OFF): ledge vault disabled. Higher (ON): second-jump ledge vault enabled.",
        "crouch_enabled": "Lower (OFF): crouch input ignored. Higher (ON): hold C to crouch.",
        "grapple_enabled": "Lower (OFF): grapple impulse disabled. Higher (ON): grapple impulse enabled on LMB.",
    }

    def __init__(
        self,
        *,
        aspect2d,
        tuning: PhysicsTuning,
        on_tuning_change,
        on_profile_select,
        on_profile_save,
    ) -> None:
        self._tuning = tuning
        self._on_tuning_change = on_tuning_change
        self._on_profile_select = on_profile_select
        self._on_profile_save = on_profile_save
        self._field_help = dict(self.FIELD_HELP)
        self._profiles: list[str] = []
        self._active_profile: str = ""
        self._profile_dropdown_open = False
        self._profile_dropdown_offset = 0
        self._profile_visible = 6

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())

        panel_left = -aspect_ratio + 0.05
        panel_right = min(panel_left + 2.16, aspect_ratio - 0.04)
        panel_top = 0.95
        panel_bottom = -0.86

        self.debug_root = DirectFrame(
            parent=aspect2d,
            frameColor=(0.03, 0.07, 0.11, 0.95),
            frameSize=(panel_left, panel_right, panel_bottom, panel_top),
            relief=DGG.FLAT,
        )
        DirectFrame(
            parent=self.debug_root,
            frameColor=(0.78, 0.65, 0.32, 0.95),
            frameSize=(panel_left, panel_right, panel_top - 0.08, panel_top),
            relief=DGG.FLAT,
        )
        DirectLabel(
            parent=self.debug_root,
            text="DEBUG / PHYSICS (`)  -  GoldSrc style",
            text_scale=0.044,
            text_align=TextNode.ALeft,
            text_fg=(0.06, 0.06, 0.06, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(panel_left + 0.04, 0, panel_top - 0.053),
        )
        self._profile_button = DirectButton(
            parent=self.debug_root,
            text=("profile: surf_bhop",) * 4,
            text_scale=0.032,
            text_align=TextNode.ALeft,
            text_fg=(0.08, 0.08, 0.08, 1.0),
            frameColor=(0.80, 0.74, 0.56, 0.98),
            relief=DGG.FLAT,
            frameSize=(-0.01, 0.72, -0.04, 0.005),
            pos=(panel_right - 0.90, 0, panel_top - 0.017),
            command=self._toggle_profile_dropdown,
        )
        self._profile_button.setBin("gui-popup", 20)
        self._profile_button.setDepthTest(False)
        self._profile_button.setDepthWrite(False)
        self._profile_save_button = DirectButton(
            parent=self.debug_root,
            text=("save",) * 4,
            text_scale=0.032,
            text_fg=(0.08, 0.08, 0.08, 1.0),
            frameColor=(0.72, 0.82, 0.68, 0.98),
            relief=DGG.FLAT,
            frameSize=(-0.01, 0.21, -0.04, 0.005),
            pos=(panel_right - 0.17, 0, panel_top - 0.017),
            command=self._on_profile_save_click,
        )
        self._profile_save_button.setBin("gui-popup", 20)
        self._profile_save_button.setDepthTest(False)
        self._profile_save_button.setDepthWrite(False)
        self._profile_dropdown_frame = DirectFrame(
            parent=self.debug_root,
            frameColor=(0.08, 0.14, 0.20, 0.98),
            frameSize=(0.0, 0.86, -0.45, 0.0),
            relief=DGG.FLAT,
            pos=(panel_right - 0.90, 0, panel_top - 0.09),
        )
        self._profile_dropdown_frame.setBin("gui-popup", 20)
        self._profile_dropdown_frame.setDepthTest(False)
        self._profile_dropdown_frame.setDepthWrite(False)
        self._profile_dropdown_buttons: list[DirectButton] = []
        for i in range(self._profile_visible):
            y = -0.03 - i * 0.07
            btn = DirectButton(
                parent=self._profile_dropdown_frame,
                text=("-", "-", "-", "-"),
                text_scale=0.030,
                text_align=TextNode.ALeft,
                text_fg=(0.92, 0.92, 0.92, 1.0),
                frameColor=(0.18, 0.22, 0.28, 0.98),
                relief=DGG.FLAT,
                frameSize=(0.02, 0.82, -0.055, -0.005),
                pos=(0.0, 0.0, y),
                command=lambda idx=i: self._select_profile_row(idx),
            )
            btn.setBin("gui-popup", 21)
            btn.setDepthTest(False)
            btn.setDepthWrite(False)
            self._profile_dropdown_buttons.append(btn)
        self._profile_dropdown_frame.hide()

        self.speed_hud_label = DirectLabel(
            parent=aspect2d,
            text="Speed: 0 u/s",
            text_scale=0.042,
            text_align=TextNode.ACenter,
            text_fg=(0.94, 0.94, 0.94, 0.95),
            frameColor=(0, 0, 0, 0),
            pos=(0.0, 0, 0.93),
        )

        self.time_trial_hud_label = DirectLabel(
            parent=aspect2d,
            text="",
            text_scale=0.038,
            text_align=TextNode.ARight,
            text_fg=(0.94, 0.94, 0.94, 0.95),
            frameColor=(0, 0, 0, 0),
            pos=(aspect_ratio - 0.06, 0, 0.90),
        )
        self.time_trial_hud_label.hide()

        self._tooltip_label = DirectLabel(
            parent=self.debug_root,
            text="",
            text_scale=0.028,
            text_align=TextNode.ALeft,
            text_fg=(0.96, 0.94, 0.76, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(panel_left + 0.03, 0, panel_bottom + 0.045),
            text_wordwrap=54,
        )
        self._tooltip_label.hide()

        scroll_top = panel_top - 0.11
        scroll_bottom = panel_bottom + 0.12
        self._scroll_width = (panel_right - panel_left) - 0.06
        self._scroll = DirectScrolledFrame(
            parent=self.debug_root,
            frameColor=(0.05, 0.10, 0.15, 0.85),
            frameSize=(panel_left + 0.02, panel_right - 0.02, scroll_bottom, scroll_top),
            canvasSize=(0.0, self._scroll_width, -1.0, 0.0),
            autoHideScrollBars=False,
            manageScrollBars=True,
            verticalScroll_frameColor=(0.10, 0.10, 0.10, 0.95),
            verticalScroll_thumb_frameColor=(0.72, 0.72, 0.72, 1.0),
            verticalScroll_incButton_frameColor=(0.22, 0.22, 0.22, 1.0),
            verticalScroll_decButton_frameColor=(0.22, 0.22, 0.22, 1.0),
        )
        self._canvas = self._scroll.getCanvas()
        try:
            # Keep this panel vertical-only.
            self._scroll.horizontalScroll.hide()
        except Exception:
            pass

        self._numeric_ranges = {name: (low, high) for name, low, high in self.NUMERIC_CONTROLS}
        self._number_controls: dict[str, NumberControl] = {}
        self._toggle_buttons: dict[str, DirectButton] = {}
        self._group_order: list[str] = []
        self._groups: dict[str, _GroupUI] = {}

        for group_name, numeric_fields, toggle_fields in self.GROUPS:
            self._build_group(group_name, numeric_fields, toggle_fields)
        self._relayout_groups()

        self.status_label = DirectLabel(
            parent=aspect2d,
            text="",
            text_scale=0.038,
            text_align=TextNode.ALeft,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0, 0, 0, 0),
            pos=(-aspect_ratio + 0.06, 0, -0.92),
        )

        self.debug_root.hide()
        self._refresh_profile_dropdown()

    def set_profiles(self, profile_names: list[str], active_profile: str) -> None:
        self._profiles = list(profile_names)
        self._active_profile = active_profile
        if self._active_profile and self._active_profile in self._profiles:
            idx = self._profiles.index(self._active_profile)
            if idx < self._profile_dropdown_offset:
                self._profile_dropdown_offset = idx
            if idx >= self._profile_dropdown_offset + self._profile_visible:
                self._profile_dropdown_offset = idx - self._profile_visible + 1
        self._refresh_profile_dropdown()

    def _build_group(self, group_name: str, numeric_fields: list[str], toggle_fields: list[str]) -> None:
        box = DirectFrame(
            parent=self._canvas,
            frameColor=(0.09, 0.14, 0.20, 0.95),
            frameSize=(0.0, self._scroll_width - 0.05, -0.4, 0.0),
            relief=DGG.FLAT,
        )
        header_btn = DirectButton(
            parent=box,
            text=(f"[-] {group_name}",) * 4,
            text_scale=0.034,
            text_align=TextNode.ALeft,
            text_fg=(0.96, 0.90, 0.66, 1.0),
            frameColor=(0.14, 0.24, 0.35, 0.98),
            relief=DGG.FLAT,
            scale=1.0,
            frameSize=(0.0, self._scroll_width - 0.05, -0.06, 0.0),
            pos=(0.0, 0.0, 0.0),
            command=lambda n=group_name: self._toggle_group(n),
        )
        header_btn.bind("wheel_up", lambda _evt: self.scroll_wheel(+1))
        header_btn.bind("wheel_down", lambda _evt: self.scroll_wheel(-1))
        content = DirectFrame(
            parent=box,
            frameColor=(0.06, 0.10, 0.16, 0.98),
            frameSize=(0.0, self._scroll_width - 0.05, -0.3, 0.0),
            relief=DGG.FLAT,
            pos=(0.0, 0.0, -0.08),
        )
        box.bind("wheel_up", lambda _evt: self.scroll_wheel(+1))
        box.bind("wheel_down", lambda _evt: self.scroll_wheel(-1))
        content.bind("wheel_up", lambda _evt: self.scroll_wheel(+1))
        content.bind("wheel_down", lambda _evt: self.scroll_wheel(-1))

        row = 0
        row_h = 0.10
        for field in numeric_fields:
            if field not in self._numeric_ranges:
                continue
            low, high = self._numeric_ranges[field]
            y = -0.05 - row * row_h
            ctrl = NumberControl(
                parent=content,
                name=field,
                x=0.03,
                y=y,
                value=float(getattr(self._tuning, field)),
                minimum=low,
                maximum=high,
                on_change=lambda val, f=field: self._set_tuning(f, val),
                slider_offset=0.66,
                entry_offset=1.00,
                normalized_slider=True,
                normalized_entry=True,
                slider_scale=0.078,
                entry_scale=0.033,
                precision=3 if high <= 3.0 else 2,
            )
            self._number_controls[field] = ctrl
            tooltip = self._field_help.get(field)
            if tooltip:
                self._bind_tooltip(ctrl.label, tooltip)
                self._bind_tooltip(ctrl.slider, tooltip)
                self._bind_tooltip(ctrl.entry, tooltip)
            row += 1

        for field in toggle_fields:
            y = -0.05 - row * row_h
            self._make_toggle_row(parent=content, field=field, x=0.03, y=y)
            row += 1

        content_height = max(0.12, 0.10 + row * row_h)
        content["frameSize"] = (0.0, self._scroll_width - 0.05, -content_height, 0.0)

        self._group_order.append(group_name)
        self._groups[group_name] = _GroupUI(
            box=box,
            header_btn=header_btn,
            content=content,
            expanded=True,
            content_height=content_height,
        )

    def _toggle_group(self, group_name: str) -> None:
        g = self._groups[group_name]
        g.expanded = not g.expanded
        self._relayout_groups()

    def _relayout_groups(self) -> None:
        y_cursor = -0.02
        for group_name in self._group_order:
            g = self._groups[group_name]
            g.box.setPos(0.01, 0.0, y_cursor)
            header_h = 0.065
            if g.expanded:
                g.content.show()
                total_h = header_h + g.content_height + 0.04
                g.box["frameSize"] = (0.0, self._scroll_width - 0.05, -total_h, 0.0)
                g.content.setPos(0.0, 0.0, -0.09)
                g.header_btn["text"] = (f"[-] {group_name}",) * 4
            else:
                g.content.hide()
                total_h = header_h + 0.02
                g.box["frameSize"] = (0.0, self._scroll_width - 0.05, -total_h, 0.0)
                g.header_btn["text"] = (f"[+] {group_name}",) * 4
            y_cursor -= total_h + 0.03

        self._scroll["canvasSize"] = (0.0, self._scroll_width, y_cursor - 0.02, 0.0)

    def show(self) -> None:
        self.debug_root.show()
        self.status_label.hide()
        self._tooltip_label.hide()
        self._profile_dropdown_frame.hide()

    def hide(self) -> None:
        self.debug_root.hide()
        self.status_label.show()
        self._tooltip_label.hide()
        self._profile_dropdown_open = False
        self._profile_dropdown_frame.hide()

    def set_speed(self, hspeed: float) -> None:
        self.speed_hud_label["text"] = f"Speed: {int(hspeed)} u/s"

    def set_time_trial_hud(self, text: str | None) -> None:
        if text is None or not str(text).strip():
            self.time_trial_hud_label.hide()
            self.time_trial_hud_label["text"] = ""
            return
        self.time_trial_hud_label["text"] = str(text)
        self.time_trial_hud_label.show()

    def set_status(self, text: str) -> None:
        self.status_label["text"] = text

    def _set_tuning(self, field: str, value: float) -> None:
        setattr(self._tuning, field, value)
        self._on_tuning_change(field)

    def _make_toggle_row(self, *, parent, field: str, x: float, y: float) -> None:
        pretty_name = field.replace("_", " ")
        label = DirectLabel(
            parent=parent,
            text=pretty_name,
            text_scale=0.031,
            text_align=TextNode.ALeft,
            text_fg=(0.93, 0.93, 0.93, 1),
            frameColor=(0, 0, 0, 0),
            pos=(x, 0, y),
        )

        button = DirectButton(
            parent=parent,
            text=("OFF", "OFF", "OFF", "OFF"),
            text_scale=0.042,
            text_fg=(0.95, 0.95, 0.95, 1),
            frameColor=(0.20, 0.20, 0.20, 0.95),
            relief=DGG.FLAT,
            command=self._toggle_bool_field,
            extraArgs=[field],
            scale=0.055,
            frameSize=(-1.9, 1.9, -0.42, 0.42),
            pos=(x + 1.02, 0, y - 0.008),
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

    def _toggle_profile_dropdown(self) -> None:
        self._profile_dropdown_open = not self._profile_dropdown_open
        if self._profile_dropdown_open:
            self._profile_dropdown_frame.show()
        else:
            self._profile_dropdown_frame.hide()

    def _on_profile_save_click(self) -> None:
        self._on_profile_save()

    def _refresh_profile_dropdown(self) -> None:
        shown_name = self._active_profile if self._active_profile else "(none)"
        self._profile_button["text"] = (f"profile: {shown_name}",) * 4
        total = len(self._profiles)
        if total <= 0:
            for btn in self._profile_dropdown_buttons:
                btn.hide()
            return
        self._profile_dropdown_offset = max(0, min(self._profile_dropdown_offset, max(0, total - self._profile_visible)))
        for i, btn in enumerate(self._profile_dropdown_buttons):
            idx = self._profile_dropdown_offset + i
            if idx >= total:
                btn.hide()
                continue
            name = self._profiles[idx]
            prefix = "> " if name == self._active_profile else "  "
            btn["text"] = (prefix + name,) * 4
            btn.show()

    def _select_profile_row(self, row_idx: int) -> None:
        idx = self._profile_dropdown_offset + row_idx
        if idx < 0 or idx >= len(self._profiles):
            return
        self._on_profile_select(self._profiles[idx])
        self._profile_dropdown_open = False
        self._profile_dropdown_frame.hide()

    def scroll_wheel(self, direction: int) -> None:
        d = 1 if direction > 0 else -1
        if self._profile_dropdown_open and len(self._profiles) > self._profile_visible:
            self._profile_dropdown_offset -= d
            max_off = max(0, len(self._profiles) - self._profile_visible)
            self._profile_dropdown_offset = max(0, min(max_off, self._profile_dropdown_offset))
            self._refresh_profile_dropdown()
            return
        try:
            bar = self._scroll.verticalScroll
            cur = float(bar["value"])
            bar["value"] = max(0.0, min(1.0, cur - d * 0.016))
        except Exception:
            pass
