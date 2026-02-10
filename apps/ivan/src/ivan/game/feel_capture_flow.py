from __future__ import annotations

import json

from ivan.replays.compare import compare_latest_route_exports, compare_latest_replays
from ivan.replays.telemetry import export_replay_telemetry

from .feel_feedback import apply_adjustments as _apply_feedback_adjustments
from .feel_feedback import suggest_adjustments as _suggest_feel_adjustments


def _route_tag(tag: str | None) -> str:
    t = str(tag or "").strip().upper()
    return t if t in {"A", "B", "C"} else "A"


def _status(host, text: str) -> None:
    msg = str(text)
    host.ui.set_status(msg)
    try:
        host.pause_ui.set_feel_status(msg)
    except Exception:
        pass
    try:
        host.feel_capture_ui.set_status(msg)
    except Exception:
        pass


def open_feel_capture(host) -> None:
    if host._mode != "game":
        return
    if host._playback_active:
        host.ui.set_status("Replay lock: press R to exit replay.")
        return
    if host._pause_menu_open or host._debug_menu_open or host._replay_browser_open or host._console_open:
        host._close_all_game_menus()
    host._feel_capture_open = True
    host.feel_capture_ui.show()
    host._set_pointer_lock(False)
    _status(host, "Feel capture: choose route + notes, then Save + Export.")


def close_feel_capture(host) -> None:
    host._feel_capture_open = False
    try:
        host.feel_capture_ui.hide()
    except Exception:
        pass
    if not (host._pause_menu_open or host._debug_menu_open or host._replay_browser_open or host._console_open):
        host._set_pointer_lock(True)


def toggle_feel_capture(host) -> None:
    if bool(getattr(host, "_feel_capture_open", False)):
        close_feel_capture(host)
    else:
        open_feel_capture(host)


def _save_and_export_current_run(
    host,
    *,
    route_tag: str,
    route_name: str,
    run_note: str,
    feedback_text: str,
):
    out = host._save_current_demo()
    if out is None:
        return None, None, "Save skipped (no active run yet)."

    try:
        exported = export_replay_telemetry(
            replay_path=out,
            route_tag=route_tag,
            route_name=route_name or None,
            run_note=run_note or None,
            feedback_text=feedback_text or None,
            comment=run_note or None,
        )
    except Exception as e:
        return None, None, f"Feel export failed: {e}"

    comp_note = "compare pending"
    try:
        comp = compare_latest_route_exports(route_tag=route_tag, latest_summary=exported.summary_path)
        comp_note = (
            f"compare +{comp.improved_count}/-{comp.regressed_count}/={comp.equal_count} "
            f"(runs={comp.history_run_count})"
        )
    except Exception as e:
        comp_note = f"compare pending ({e})"

    latest_summary = None
    try:
        latest_summary = json.loads(exported.summary_path.read_text(encoding="utf-8"))
    except Exception:
        latest_summary = None

    return exported, latest_summary, comp_note


def submit_feel_capture_export(
    host,
    *,
    route_tag: str,
    route_name: str,
    run_note: str,
    feedback_text: str,
    apply_feedback: bool,
) -> None:
    if host._mode != "game":
        return
    if host._playback_active:
        _status(host, "Replay lock: press R to exit replay.")
        return

    tag = _route_tag(route_tag)
    route_label = str(route_name or "").strip()
    note = str(run_note or "").strip()
    feedback = str(feedback_text or "").strip()

    exported, latest_summary, compare_note = _save_and_export_current_run(
        host,
        route_tag=tag,
        route_name=route_label,
        run_note=note,
        feedback_text=feedback,
    )
    if exported is None:
        _status(host, compare_note)
        return

    apply_note = ""
    if apply_feedback:
        if not feedback:
            apply_note = "feedback empty"
        else:
            adjustments = _suggest_feel_adjustments(
                feedback_text=feedback,
                tuning=host.tuning,
                latest_summary=(latest_summary if isinstance(latest_summary, dict) else None),
            )
            if not adjustments:
                apply_note = "no tuning changes"
            else:
                _apply_feedback_adjustments(tuning=host.tuning, adjustments=adjustments)
                for adj in adjustments:
                    host._on_tuning_change(str(adj.field))
                apply_note = f"applied {len(adjustments)} tweak(s)"
                try:
                    host.feel_capture_ui.clear_feedback()
                except Exception:
                    pass
                try:
                    host.pause_ui.clear_feel_feedback()
                except Exception:
                    pass

    # Roll to a fresh recording so each run/export maps to one replay file.
    if not host._playback_active:
        host._start_new_demo_recording()

    suffix = f"; {apply_note}" if apply_note else ""
    msg = f"Saved + exported [{tag}] {exported.summary_path.name} ({compare_note}{suffix})"
    _status(host, msg)


def feel_export_latest(host, route_tag: str, feedback_text: str) -> None:
    submit_feel_capture_export(
        host,
        route_tag=route_tag,
        route_name="",
        run_note=feedback_text,
        feedback_text=feedback_text,
        apply_feedback=False,
    )


def feel_apply_feedback(host, route_tag: str, feedback_text: str) -> None:
    text = str(feedback_text or "").strip()
    tag = _route_tag(route_tag)
    if not text:
        _status(host, "Feel feedback is empty.")
        return

    latest_summary: dict | None = None
    compare_note = "compare skipped"
    try:
        comp = compare_latest_replays(route_tag=tag, latest_comment=text or None)
        latest_summary = json.loads(comp.latest_export.summary_path.read_text(encoding="utf-8"))
        compare_note = f"compare +{comp.improved_count}/-{comp.regressed_count}/={comp.equal_count}"
    except Exception as compare_err:
        try:
            exported, latest_summary, compare_note = _save_and_export_current_run(
                host,
                route_tag=tag,
                route_name="",
                run_note=text,
                feedback_text=text,
            )
            if exported is None:
                _status(host, f"Feel export failed: {compare_note}")
                return
            compare_note = f"{compare_note}; fallback after compare error: {compare_err}"
        except Exception as export_err:
            _status(host, f"Feel export failed: {export_err}")
            return

    adjustments = _suggest_feel_adjustments(
        feedback_text=text,
        tuning=host.tuning,
        latest_summary=latest_summary,
    )
    if not adjustments:
        _status(host, "No tuning adjustments suggested for this feedback.")
        return

    _apply_feedback_adjustments(tuning=host.tuning, adjustments=adjustments)
    for adj in adjustments:
        host._on_tuning_change(str(adj.field))
    preview = ", ".join(f"{a.field} {float(a.before):.3f}->{float(a.after):.3f}" for a in adjustments[:4])
    if len(adjustments) > 4:
        preview += f", +{len(adjustments) - 4} more"
    try:
        host.pause_ui.clear_feel_feedback()
    except Exception:
        pass
    try:
        host.feel_capture_ui.clear_feedback()
    except Exception:
        pass
    _status(host, f"Applied {len(adjustments)} tweak(s) [{tag}] ({compare_note}): {preview}")


__all__ = [
    "close_feel_capture",
    "feel_apply_feedback",
    "feel_export_latest",
    "open_feel_capture",
    "submit_feel_capture_export",
    "toggle_feel_capture",
]
