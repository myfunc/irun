"""Race editor DevTools service: placement, publish, mode picker coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from panda3d.core import LVector3f

from ivan.course.time_trial import make_marker_cylinder
from ivan.course.volumes import CylinderVolume
from ivan.games import ModeItem, RaceCourse

if TYPE_CHECKING:
    pass


class RaceEditorService:
    """
    DevTools service for race authoring: toggle editor, mode picker, place markers, publish.
    Owns draft state; delegates rendering/sync/persist to host.
    """

    def __init__(self) -> None:
        self._enabled: bool = False
        self._mode_id: str | None = None
        self._selection_pos: LVector3f | None = None
        self._draft_start: CylinderVolume | None = None
        self._draft_checkpoints: list[CylinderVolume] = []
        self._draft_finish: CylinderVolume | None = None

    def is_enabled(self) -> bool:
        return self._enabled

    def get_mode_id(self) -> str | None:
        return self._mode_id

    def get_draft_state(
        self,
    ) -> tuple[
        LVector3f | None,
        CylinderVolume | None,
        tuple[CylinderVolume, ...],
        CylinderVolume | None,
    ]:
        """Return (selection_pos, start, checkpoints, finish) for rendering."""
        return (
            self._selection_pos,
            self._draft_start,
            tuple(self._draft_checkpoints),
            self._draft_finish,
        )

    def reset(self) -> None:
        """Clear all editor state (e.g. on map load, disconnect)."""
        self._enabled = False
        self._mode_id = None
        self._selection_pos = None
        self._draft_start = None
        self._draft_checkpoints = []
        self._draft_finish = None

    def toggle(
        self,
        *,
        host: Any,
        can_edit: bool,
        menus_block: bool,
        playback_active: bool,
        marker_radius_half_z: tuple[float, float],
        on_publish: None = None,
    ) -> bool:
        """
        Toggle editor on/off. Returns True if toggle was handled.
        host: app with set_status, _close_game_mode_picker, tuning.noclip_enabled, _sync_race_markers.
        on_publish: optional callback(course) after successful publish.
        """
        if not can_edit:
            host.ui.set_status("Game editor is host-only in multiplayer.")
            return True
        if menus_block:
            return False
        if playback_active:
            host.ui.set_status("Replay lock: press R to exit replay.")
            return True
        if self._enabled:
            self._publish(host=host, marker_radius_half_z=marker_radius_half_z, on_publish=on_publish)
            self._enabled = False
            self._mode_id = None
            host._close_game_mode_picker()
            host.tuning.noclip_enabled = False
            host.ui.set_status("Game editor disabled.")
            return True
        self._enabled = True
        self._mode_id = None
        self._selection_pos = None
        self._draft_start = None
        self._draft_checkpoints = []
        self._draft_finish = None
        host._close_game_mode_picker()
        host.tuning.noclip_enabled = True
        host.ui.set_status("Game editor enabled (noclip). Press F to select game mode.")
        return True

    def on_interact(
        self,
        *,
        host: Any,
        player_pos: LVector3f,
    ) -> bool:
        """
        Handle F in editor mode: open picker or confirm selection.
        Returns True if handled (caller should not process interact further).
        """
        if not self._enabled:
            return False
        if host.game_mode_picker_ui.is_visible():
            host.game_mode_picker_ui.on_enter()
        else:
            self._open_picker(host=host)
        return True

    def _open_picker(self, *, host: Any) -> None:
        rows = [ModeItem(id="race", label="Race")]
        host.game_mode_picker_ui.show(items=rows, status="Select mode to author.")
        host._set_pointer_lock(False)

    def close_picker(self, *, host: Any, should_restore_lock: bool) -> None:
        """Hide picker and optionally restore pointer lock."""
        host.game_mode_picker_ui.hide()
        if should_restore_lock:
            host._set_pointer_lock(True)

    def on_mode_selected(
        self,
        *,
        host: Any,
        mode_id: str,
        player_pos: LVector3f,
    ) -> None:
        self._mode_id = str(mode_id)
        self._selection_pos = LVector3f(player_pos)
        self._draft_start = None
        self._draft_checkpoints = []
        self._draft_finish = None
        self.close_picker(host=host, should_restore_lock=True)
        host.ui.set_status("Race editor: 1 start | 2 checkpoint | 3 finish | V publish")

    def place(
        self,
        *,
        host: Any,
        slot: int,
        player_pos: LVector3f,
        marker_radius_half_z: tuple[float, float],
    ) -> bool:
        """Place marker at slot (1=start, 2=checkpoint, 3=finish). Returns True if placed."""
        if not self._enabled or self._mode_id != "race":
            return False
        radius, half_z = marker_radius_half_z
        marker = make_marker_cylinder(pos=LVector3f(player_pos), radius=radius, half_z=half_z)
        s = int(slot)
        if s == 1:
            self._draft_start = marker
            host.ui.set_status("Race editor: start marker placed.")
        elif s == 2:
            self._draft_checkpoints.append(marker)
            host.ui.set_status(f"Race editor: checkpoint {len(self._draft_checkpoints)} placed.")
        elif s == 3:
            self._draft_finish = marker
            host.ui.set_status("Race editor: finish marker placed.")
        else:
            return False
        return True

    def _publish(
        self,
        *,
        host: Any,
        marker_radius_half_z: tuple[float, float],
        on_publish: None = None,
    ) -> None:
        if self._mode_id != "race":
            return
        if self._selection_pos is None:
            host.ui.set_status("Race editor: no mode selected; nothing published.")
            return
        if self._draft_start is None or self._draft_finish is None:
            host.ui.set_status("Race editor: place start and finish before publishing.")
            return
        radius, half_z = marker_radius_half_z
        mission = make_marker_cylinder(
            pos=LVector3f(self._selection_pos), radius=radius * 1.18, half_z=half_z
        )
        course = RaceCourse(
            mission_marker=mission,
            start=self._draft_start,
            checkpoints=tuple(self._draft_checkpoints),
            finish=self._draft_finish,
        )
        host._race_runtime.set_course(course)
        host._persist_published_race(course=course)
        host.ui.set_status(
            f"Race published. Mission marker set ({1 + len(self._draft_checkpoints)} checkpoints before finish)."
        )
        if on_publish is not None:
            on_publish(course)
