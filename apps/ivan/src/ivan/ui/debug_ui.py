from __future__ import annotations

from dataclasses import dataclass

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase import ShowBaseGlobal
from panda3d.core import TextNode

from irun_ui_kit.theme import Theme
from irun_ui_kit.widgets.button import Button
from irun_ui_kit.widgets.checkbox import Checkbox
from irun_ui_kit.widgets.collapsible import CollapsiblePanel
from irun_ui_kit.widgets.dropdown import Dropdown
from irun_ui_kit.widgets.numeric_control import NumericControl
from irun_ui_kit.widgets.scrolled import Scrolled
from irun_ui_kit.widgets.tooltip import Tooltip
from irun_ui_kit.widgets.window import Window

from ivan.physics.tuning import PhysicsTuning


@dataclass
class _GroupUI:
    panel: CollapsiblePanel
    numeric: dict[str, NumericControl]
    toggles: dict[str, Checkbox]


class DebugUI:
    # Keep these lists as stable wiring contracts (tests rely on them).
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
        ("jump_buffer_time", 0.0, 0.35),
        ("noclip_speed", 1.0, 35.0),
        ("grapple_fire_range", 10.0, 400.0),
        ("grapple_attach_boost", 0.0, 40.0),
        ("grapple_attach_shorten_speed", 0.0, 80.0),
        ("grapple_attach_shorten_time", 0.0, 0.80),
        ("grapple_pull_strength", 0.0, 160.0),
        ("grapple_min_length", 0.5, 10.0),
        ("grapple_max_length", 5.0, 300.0),
        ("grapple_rope_half_width", 0.002, 0.08),
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
        "enable_jump_buffer",
        "autojump_enabled",
        "noclip_enabled",
        "surf_enabled",
        "walljump_enabled",
        "wallrun_enabled",
        "vault_enabled",
        "crouch_enabled",
        "grapple_enabled",
        "vis_culling_enabled",
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
                "jump_buffer_time",
                "vault_jump_multiplier",
                "vault_forward_boost",
                "vault_min_ledge_height",
                "vault_max_ledge_height",
                "vault_cooldown",
                "grapple_fire_range",
                "grapple_attach_boost",
                "grapple_attach_shorten_speed",
                "grapple_attach_shorten_time",
                "grapple_pull_strength",
                "grapple_min_length",
                "grapple_max_length",
                "grapple_rope_half_width",
            ],
            ["enable_jump_buffer", "autojump_enabled", "vault_enabled"],
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
                "course_marker_half_extent_xy",
                "course_marker_half_extent_z",
                "crouch_speed_multiplier",
                "crouch_half_height",
                "crouch_eye_height",
                "noclip_speed",
            ],
            ["crouch_enabled", "noclip_enabled", "grapple_enabled"],
        ),
        (
            "Rendering / Visibility",
            [],
            ["vis_culling_enabled"],
        ),
    ]

    FIELD_LABELS: dict[str, str] = {
        "max_ground_speed": "ground accel target speed",
        "max_air_speed": "air accel target speed",
        "jump_accel": "air accel strength",
        "air_counter_strafe_brake": "air reverse brake",
        "surf_accel": "surf accel strength",
        "surf_gravity_scale": "surf gravity scale",
        "grapple_fire_range": "grapple fire range",
        "grapple_attach_boost": "grapple attach boost",
        "grapple_attach_shorten_speed": "grapple auto-shorten speed",
        "grapple_attach_shorten_time": "grapple auto-shorten time",
        "grapple_pull_strength": "grapple rope pull strength",
        "grapple_min_length": "grapple min rope length",
        "grapple_max_length": "grapple max rope length",
        "grapple_rope_half_width": "grapple rope width",
    }

    # Tooltips (tests rely on Lower/Higher guidance strings).
    FIELD_HELP: dict[str, str] = {
        "gravity": "Lower: floatier movement and longer airtime. Higher: faster fall and snappier landings.",
        "jump_height": "Lower: shorter hop height. Higher: higher jump apex and longer time before landing.",
        "max_ground_speed": "Lower: lower ground acceleration target speed. Higher: higher target speed (not a strict hard cap).",
        "max_air_speed": "Lower: lower air acceleration target speed. Higher: higher target speed (momentum can still exceed it).",
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
        "jump_buffer_time": "Lower: tighter jump timing before landing. Higher: more forgiving early jump presses.",
        "noclip_speed": "Lower: slower free-fly movement in noclip mode. Higher: faster noclip traversal speed.",
        "grapple_fire_range": "Lower: shorter grapple reach from crosshair. Higher: longer grapple reach.",
        "grapple_attach_boost": "Lower: weaker one-time pull toward anchor on attach. Higher: stronger attach boost.",
        "grapple_attach_shorten_speed": "Lower: less rope shortening after attach. Higher: faster post-attach rope shortening.",
        "grapple_attach_shorten_time": "Lower: shorter auto-shorten window after attach. Higher: longer auto-shorten window.",
        "grapple_pull_strength": "Lower: softer rope correction when taut. Higher: stronger pull toward rope length.",
        "grapple_min_length": "Lower: allows tighter rope radius. Higher: keeps a larger minimum swing radius.",
        "grapple_max_length": "Lower: limits how far rope can extend. Higher: allows longer rope extension.",
        "grapple_rope_half_width": "Lower: thinner visible rope. Higher: thicker visible rope.",
        "max_ground_slope_deg": "Lower: fewer slopes count as walkable. Higher: steeper slopes remain walkable.",
        "step_height": "Lower: smaller obstacles can be stepped over. Higher: taller steps are auto-climbed.",
        "ground_snap_dist": "Lower: less ground sticking on small drops. Higher: stronger snap to nearby walkable ground.",
        "player_radius": "Lower: narrower collision capsule. Higher: wider body collision.",
        "player_half_height": "Lower: shorter collision capsule. Higher: taller collision capsule.",
        "player_eye_height": "Lower: camera sits lower. Higher: camera sits higher.",
        "course_marker_half_extent_xy": "Lower: smaller Start/Finish trigger volumes (harder to hit). Higher: larger trigger volumes (easier to hit).",
        "course_marker_half_extent_z": "Lower: shorter Start/Finish trigger volumes (harder to hit). Higher: taller trigger volumes (easier to hit).",
        "enable_jump_buffer": "Lower (OFF): no jump input buffering. Higher (ON): buffered jump before landing.",
        "autojump_enabled": "Lower (OFF): jump on press only. Higher (ON): holding jump re-queues only while grounded.",
        "noclip_enabled": "Lower (OFF): normal collision movement. Higher (ON): collision-free noclip movement.",
        "surf_enabled": "Lower (OFF): slanted-surface surfing disabled. Higher (ON): surf ramps work with strafe hold.",
        "walljump_enabled": "Lower (OFF): wall-jumps disabled. Higher (ON): wall-jumps enabled.",
        "wallrun_enabled": "Lower (OFF): wallrun disabled. Higher (ON): side wallrun enabled.",
        "vault_enabled": "Lower (OFF): ledge vault disabled. Higher (ON): second-jump ledge vault enabled.",
        "crouch_enabled": "Lower (OFF): crouch input ignored. Higher (ON): hold C to crouch.",
        "grapple_enabled": "Lower (OFF): grapple hook disabled. Higher (ON): LMB click attach/detach.",
        "vis_culling_enabled": "Lower (OFF): disable GoldSrc PVS culling (stable visuals). Higher (ON): enable visibility culling (may pop).",
    }

    def __init__(
        self,
        *,
        aspect2d,
        theme: Theme,
        tuning: PhysicsTuning,
        on_tuning_change,
        on_profile_select,
        on_profile_save,
    ) -> None:
        self._theme = theme
        self._tuning = tuning
        self._on_tuning_change = on_tuning_change
        self._on_profile_select = on_profile_select
        self._on_profile_save = on_profile_save

        self._profiles: list[str] = []
        self._active_profile: str = ""

        aspect_ratio = 16.0 / 9.0
        if getattr(ShowBaseGlobal, "base", None) is not None:
            try:
                aspect_ratio = float(ShowBaseGlobal.base.getAspectRatio())
            except Exception:
                pass

        panel_left = -aspect_ratio + 0.05
        panel_right = min(panel_left + 2.22, aspect_ratio - 0.04)
        panel_top = 0.95
        panel_bottom = -0.86

        w = panel_right - panel_left
        h = panel_top - panel_bottom

        self._window = Window(
            aspect2d=aspect2d,
            theme=theme,
            title="DEBUG / PHYSICS (`)  -  GoldSrc style",
            x=panel_left,
            y=panel_bottom,
            w=w,
            h=h,
        )
        self.debug_root = self._window.root

        # HUD elements (do not touch crosshair/log/error UI behavior).
        # Speed chip: keep it out of the way of menus (top-right corner).
        chip_w = 0.46
        chip_h = 0.10
        chip_x = aspect_ratio - 0.06 - chip_w
        chip_y = 0.90
        self.speed_hud_root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, chip_w, 0.0, chip_h),
            pos=(chip_x, 0.0, chip_y),
        )
        DirectFrame(
            parent=self.speed_hud_root,
            frameColor=(theme.panel2[0], theme.panel2[1], theme.panel2[2], theme.panel2[3] * 0.90),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, chip_w - theme.outline_w, theme.outline_w, chip_h - theme.outline_w),
        )
        self.speed_hud_label = DirectLabel(
            parent=self.speed_hud_root,
            text="SPEED 0",
            text_scale=0.042,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0, chip_h * 0.32),
        )
        self.speed_hud_root.hide()
        # Health chip: top-left corner.
        hp_w = 0.42
        hp_h = 0.10
        hp_x = -aspect_ratio + 0.06
        hp_y = 0.90
        self.health_hud_root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, hp_w, 0.0, hp_h),
            pos=(hp_x, 0.0, hp_y),
        )
        DirectFrame(
            parent=self.health_hud_root,
            frameColor=(theme.panel2[0], theme.panel2[1], theme.panel2[2], theme.panel2[3] * 0.90),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, hp_w - theme.outline_w, theme.outline_w, hp_h - theme.outline_w),
        )
        self.health_hud_label = DirectLabel(
            parent=self.health_hud_root,
            text="HP 100",
            text_scale=0.040,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0, hp_h * 0.32),
        )
        self.health_hud_root.hide()
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

        # Classic HL/CS-style thin crosshair with a small center gap.
        self._crosshair_parts: list[DirectFrame] = []
        gap = 0.010
        arm = 0.020
        thick = 0.0015
        color = (0.92, 0.95, 0.88, 0.85)
        cross_specs = [
            (-gap - arm, -gap, -thick, thick),  # left
            (gap, gap + arm, -thick, thick),  # right
            (-thick, thick, gap, gap + arm),  # up
            (-thick, thick, -gap - arm, -gap),  # down
        ]
        for fs in cross_specs:
            part = DirectFrame(
                parent=aspect2d,
                frameColor=color,
                frameSize=fs,
                relief=DGG.FLAT,
                pos=(0.0, 0.0, 0.0),
            )
            self._crosshair_parts.append(part)

        # Bottom status bar (movement state summary). Kept visible during gameplay and hidden while debug menu is open.
        bar_pad = 0.06
        bar_w = max(0.60, (aspect_ratio * 2.0) - (bar_pad * 2.0))
        bar_h = 0.11
        bar_x = -aspect_ratio + bar_pad
        bar_y = -0.97
        self.status_root = DirectFrame(
            parent=aspect2d,
            frameColor=theme.outline,
            relief=DGG.FLAT,
            frameSize=(0.0, bar_w, 0.0, bar_h),
            pos=(bar_x, 0.0, bar_y),
        )
        DirectFrame(
            parent=self.status_root,
            frameColor=(theme.panel[0], theme.panel[1], theme.panel[2], 0.86),
            relief=DGG.FLAT,
            frameSize=(theme.outline_w, bar_w - theme.outline_w, theme.outline_w, bar_h - theme.outline_w),
        )
        self.status_label = DirectLabel(
            parent=self.status_root,
            text="",
            text_scale=0.036,
            text_align=TextNode.ALeft,
            text_fg=theme.text,
            frameColor=(0, 0, 0, 0),
            pos=(theme.outline_w + theme.pad * 0.50, 0, bar_h * 0.34),
            text_wordwrap=70,
        )

        # Layout inside the window (local coordinates 0..w/0..h).
        header_total_h = theme.header_h + (theme.outline_w * 2)
        top_controls_h = 0.13
        tooltip_h = 0.10

        # Profile dropdown + save.
        dd_w = min(0.86, w * 0.62)
        dd_h = 0.095
        dd_x = w - theme.pad - dd_w
        dd_y = h - header_total_h - theme.pad - dd_h
        self._profile_dropdown = Dropdown.build(
            parent=self.debug_root,
            theme=theme,
            x=dd_x,
            y=dd_y,
            w=dd_w,
            h=dd_h,
            visible=6,
            prefix="profile",
            on_select=self._on_profile_select_click,
        )

        save_w = min(0.26, w * 0.18)
        self._save_button = Button.build(
            parent=self.debug_root,
            theme=theme,
            x=w - theme.pad - save_w / 2.0,
            y=dd_y + dd_h / 2.0,
            w=save_w,
            h=dd_h,
            label="save",
            on_click=self._on_profile_save_click,
        )

        # Tooltip label anchored at the bottom of the window.
        self._tooltip = Tooltip.build(
            parent=self.debug_root,
            theme=theme,
            x=theme.pad,
            y=theme.pad,
            w=w - theme.pad * 2,
            wordwrap=54,
        )

        # Scrollable groups area.
        scroll_x = theme.pad
        scroll_y = theme.pad + tooltip_h + theme.gap
        scroll_w = w - theme.pad * 2
        scroll_h = max(0.25, h - header_total_h - theme.pad * 3 - top_controls_h - tooltip_h - theme.gap)
        self._scroll = Scrolled.build(
            parent=self.debug_root,
            theme=theme,
            x=scroll_x,
            y=scroll_y,
            w=scroll_w,
            h=scroll_h,
            canvas_h=scroll_h,
        )
        # Redundant wheel binding: some platforms deliver wheel events more reliably via DirectGUI regions.
        try:
            self._scroll.frame.bind(DGG.WHEELUP, lambda _evt: self.scroll_wheel(+1))
            self._scroll.frame.bind(DGG.WHEELDOWN, lambda _evt: self.scroll_wheel(-1))
        except Exception:
            pass
        scroll_content_w = self._scroll.content_w()

        self._numeric_ranges = {name: (low, high) for name, low, high in self.NUMERIC_CONTROLS}
        self._group_order: list[str] = []
        self._groups: dict[str, _GroupUI] = {}

        for group_name, numeric_fields, toggle_fields in self.GROUPS:
            self._build_group(group_name, numeric_fields, toggle_fields, scroll_w=scroll_content_w)

        self._relayout_groups()

        self.debug_root.hide()
        self.set_crosshair_visible(False)
        self._profile_dropdown.set_items([], active="")

    def set_profiles(self, profile_names: list[str], active_profile: str) -> None:
        self._profiles = list(profile_names or [])
        self._active_profile = str(active_profile or "")
        self._profile_dropdown.set_items(self._profiles, active=self._active_profile)
        self.sync_from_tuning()

    def sync_from_tuning(self) -> None:
        for g in self._groups.values():
            for field, ctrl in g.numeric.items():
                value = float(getattr(self._tuning, field))
                ctrl.set_value(value, emit=False)
            for field, cb in g.toggles.items():
                cb.set_checked(bool(getattr(self._tuning, field)))

    def _build_group(self, group_name: str, numeric_fields: list[str], toggle_fields: list[str], *, scroll_w: float) -> None:
        # Precompute height so CollapsiblePanel has stable geometry.
        row_h = 0.115
        n_numeric = sum(1 for f in numeric_fields if f in self._numeric_ranges)
        n_toggle = len(toggle_fields)
        content_rows = n_numeric + n_toggle
        content_h = max(0.16, content_rows * row_h + self._theme.pad * 2)
        expanded_h = content_h + (self._theme.header_h + (self._theme.outline_w * 2))

        panel = CollapsiblePanel.build(
            parent=self._scroll.canvas,
            theme=self._theme,
            x=0.0,
            y=0.0,
            w=scroll_w,
            expanded_h=expanded_h,
            title=group_name,
            expanded=True,
            on_toggle=self._relayout_groups,
        )

        numeric: dict[str, NumericControl] = {}
        toggles: dict[str, Checkbox] = {}

        y_cursor = content_h - self._theme.pad - row_h
        x0 = self._theme.pad
        row_w = scroll_w - self._theme.pad * 2

        for field in numeric_fields:
            if field not in self._numeric_ranges:
                continue
            low, high = self._numeric_ranges[field]
            ctrl = NumericControl.build(
                parent=panel.content,
                theme=self._theme,
                x=x0,
                y=y_cursor,
                w=row_w,
                label=self._label_for_field(field),
                value=float(getattr(self._tuning, field)),
                minimum=low,
                maximum=high,
                on_change=lambda val, f=field: self._set_tuning(f, float(val)),
                normalized_slider=True,
                normalized_entry=True,
                precision=3 if high <= 3.0 else 2,
            )
            numeric[field] = ctrl
            tip = self.FIELD_HELP.get(field)
            if tip:
                self._tooltip.bind(ctrl.label, tip)
                self._tooltip.bind(ctrl.slider, tip)
                self._tooltip.bind(ctrl.entry.frame, tip)
                self._tooltip.bind(ctrl.entry.entry, tip)
            y_cursor -= row_h

        for field in toggle_fields:
            cb = Checkbox.build(
                parent=panel.content,
                theme=self._theme,
                x=x0 + row_w / 2.0,
                y=y_cursor + row_h / 2.0,
                w=row_w,
                h=row_h * 0.70,
                label=self._label_for_field(field),
                checked=bool(getattr(self._tuning, field)),
                on_change=lambda checked, f=field: self._set_bool_field(f, bool(checked)),
            )
            toggles[field] = cb
            tip = self.FIELD_HELP.get(field)
            if tip:
                self._tooltip.bind(cb.button, tip)
            y_cursor -= row_h

        self._group_order.append(group_name)
        self._groups[group_name] = _GroupUI(panel=panel, numeric=numeric, toggles=toggles)

    def _relayout_groups(self) -> None:
        # Stack from top to bottom in the scrolled canvas.
        total = self._theme.gap
        for group_name in self._group_order:
            total += self._groups[group_name].panel.current_h() + self._theme.gap
        canvas_h = max(self._scroll.h, total)
        self._scroll.set_canvas_h(canvas_h)

        y_top = canvas_h - self._theme.gap
        for group_name in self._group_order:
            p = self._groups[group_name].panel
            y_top -= p.current_h()
            p.set_pos(y=y_top)
            y_top -= self._theme.gap

    def show(self) -> None:
        self.debug_root.show()
        self.status_root.hide()
        self._tooltip.hide()
        self._profile_dropdown.set_open(False)

    def hide(self) -> None:
        self.debug_root.hide()
        self.status_root.show()
        self._tooltip.hide()
        self._profile_dropdown.set_open(False)

    def set_speed_hud_visible(self, visible: bool) -> None:
        if visible:
            self.speed_hud_root.show()
            self.health_hud_root.show()
        else:
            self.speed_hud_root.hide()
            self.health_hud_root.hide()

    def set_speed(self, hspeed: float) -> None:
        self.speed_hud_label["text"] = f"SPEED {int(hspeed)}"

    def set_health(self, hp: int) -> None:
        self.health_hud_label["text"] = f"HP {max(0, int(hp))}"

    def set_time_trial_hud(self, text: str | None) -> None:
        if text is None or not str(text).strip():
            self.time_trial_hud_label.hide()
            self.time_trial_hud_label["text"] = ""
            return
        self.time_trial_hud_label["text"] = str(text)
        self.time_trial_hud_label.show()

    def set_status(self, text: str) -> None:
        self.status_label["text"] = str(text)

    def set_crosshair_visible(self, visible: bool) -> None:
        for part in self._crosshair_parts:
            if visible:
                part.show()
            else:
                part.hide()

    def scroll_wheel(self, direction: int) -> None:
        if self._profile_dropdown.open:
            self._profile_dropdown.scroll_wheel(direction)
            return
        self._scroll.scroll_wheel(direction)

    def _set_tuning(self, field: str, value: float) -> None:
        setattr(self._tuning, field, float(value))
        self._on_tuning_change(field)

    def _set_bool_field(self, field: str, checked: bool) -> None:
        setattr(self._tuning, field, bool(checked))
        self._on_tuning_change(field)

    def _label_for_field(self, field: str) -> str:
        if field in self.FIELD_LABELS:
            return self.FIELD_LABELS[field]
        return field.replace("_", " ")

    def _on_profile_select_click(self, name: str) -> None:
        self._on_profile_select(str(name))

    def _on_profile_save_click(self) -> None:
        self._on_profile_save()
