"""Race orchestration: marker sync, event application, runtime tick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from panda3d.core import LVector3f

from ivan.course.time_trial import make_marker_cylinder
from ivan.games import RaceEvent, RaceRuntime

if TYPE_CHECKING:
    pass


def sync_race_markers(
    *,
    host: Any,
    race_editor: Any,
    race_runtime: RaceRuntime,
    race_markers: Any,
    marker_radius_half_z: tuple[float, float],
) -> None:
    """
    Sync race markers to world. Uses editor draft when in editor mode, else runtime.
    host: app with world_root.
    """
    if host.world_root is None:
        return
    race_markers.attach(world_root=host.world_root)
    if race_editor.is_enabled() and race_editor.get_mode_id() == "race":
        sel_pos, start, checkpoints, finish = race_editor.get_draft_state()
        mission = None
        if sel_pos is not None:
            radius, half_z = marker_radius_half_z
            mission = make_marker_cylinder(pos=LVector3f(sel_pos), radius=radius * 1.18, half_z=half_z)
        race_markers.render(
            mission=mission,
            start=start,
            checkpoints=checkpoints,
            finish=finish,
            show_mission=True,
            show_course=True,
        )
        return
    race_markers.render(
        mission=race_runtime.mission_marker(),
        start=race_runtime.start_marker(),
        checkpoints=race_runtime.checkpoint_markers(),
        finish=race_runtime.finish_marker(),
        show_mission=race_runtime.mission_visible(),
        show_course=race_runtime.checkpoints_visible(),
    )


def apply_race_events(
    *,
    host: Any,
    events: list[RaceEvent],
    now: float,
    local_player_id: int,
    audio_module: Any,
) -> None:
    """Apply race events to UI/audio feedback."""
    if not events:
        return
    for ev in events:
        kind = str(ev.kind)
        if kind == "race_lobby_join":
            if int(ev.player_id) == int(local_player_id):
                host.race_ui_feedback.notice(
                    text="Race lobby: press F again to start.",
                    color=(0.84, 0.92, 1.00, 0.96),
                    now=float(now),
                )
        elif kind == "race_intro":
            host.race_ui_feedback.notice(
                text="Race intro",
                color=(0.90, 0.95, 1.00, 0.96),
                now=float(now),
                duration=1.0,
            )
        elif kind == "race_countdown_tick":
            host.race_ui_feedback.notice(
                text=str(int(ev.countdown_value)),
                color=(1.00, 0.96, 0.76, 0.98),
                now=float(now),
                duration=0.78,
            )
            audio_module.on_race_countdown(host, value=int(ev.countdown_value))
        elif kind == "race_go":
            host.race_ui_feedback.notice(
                text="GO!",
                color=(0.45, 1.00, 0.45, 0.98),
                now=float(now),
                duration=1.0,
            )
            audio_module.on_race_go(host)
        elif kind == "race_checkpoint_collected":
            if int(ev.player_id) == int(local_player_id):
                host.race_ui_feedback.flash(
                    color=(1.00, 0.88, 0.18, 0.34), now=float(now), duration=0.16
                )
                host.race_ui_feedback.notice(
                    text=f"Checkpoint {int(ev.checkpoint_index) + 1}",
                    color=(1.00, 0.92, 0.20, 0.96),
                    now=float(now),
                    duration=0.7,
                )
                audio_module.on_race_checkpoint(host)
        elif kind == "race_finished":
            if int(ev.player_id) == int(local_player_id):
                host.race_ui_feedback.flash(
                    color=(0.22, 1.00, 0.30, 0.40), now=float(now), duration=0.24
                )
                t = float(ev.elapsed_seconds) if ev.elapsed_seconds is not None else 0.0
                host.race_ui_feedback.notice(
                    text=f"Finish {t:0.3f}s",
                    color=(0.30, 1.00, 0.36, 0.98),
                    now=float(now),
                    duration=1.2,
                )
                audio_module.on_race_finish(host)
        elif kind == "race_all_finished":
            host.ui.set_status(
                "Race finished. Enter mission marker and press F to race again."
            )


def tick_race_runtime(
    *,
    host: Any,
    now: float,
    local_player_id: int,
    audio_module: Any,
) -> None:
    """
    Tick local race runtime (single-player only). Skip when net_connected.
    """
    if host.player is None:
        return
    if host._net_connected:
        return
    tp = host._race_runtime.consume_teleport_target(player_id=local_player_id)
    if tp is not None:
        host.player.pos = LVector3f(tp)
        host.player.vel = LVector3f(0.0, 0.0, 0.0)
        host._push_sim_snapshot()
    events = host._race_runtime.tick(
        now=float(now),
        player_positions={int(local_player_id): LVector3f(host.player.pos)},
    )
    if events:
        apply_race_events(
            host=host,
            events=events,
            now=float(now),
            local_player_id=local_player_id,
            audio_module=audio_module,
        )
        sync_race_markers(
            host=host,
            race_editor=host._race_editor,
            race_runtime=host._race_runtime,
            race_markers=host._race_markers,
            marker_radius_half_z=host._marker_radius_half_z(),
        )
