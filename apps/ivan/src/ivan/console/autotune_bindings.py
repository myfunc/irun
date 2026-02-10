from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ivan.console.core import CommandContext, Console

if TYPE_CHECKING:
    from ivan.game.autotune import AutotuneEvaluation, GuardrailCheck, RouteContext
    from ivan.game.feel_feedback import TuningAdjustment


def _format_number(value: float | bool) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return f"{float(value):.4f}"


def _format_adjustment(adj: TuningAdjustment) -> str:
    return f"{adj.field}: {_format_number(adj.before)} -> {_format_number(adj.after)} | {adj.reason}"


def _format_check(check: GuardrailCheck) -> str:
    state = "ok" if check.passed else "fail"
    return f"{state}: {check.name} ({check.detail})"


def _parse_out_dir(argv: list[str], idx: int) -> Path | None:
    if len(argv) <= idx:
        return None
    raw = str(argv[idx]).strip()
    return Path(raw).expanduser() if raw else None


def create_tuning_backup(host, *, label: str | None = None, reason: str | None = None) -> Path:
    from ivan.game.tuning_backups import create_tuning_backup as _impl

    return _impl(host, label=label, reason=reason)


def restore_tuning_backup(host, *, backup_ref: str | None = None) -> Path:
    from ivan.game.tuning_backups import restore_tuning_backup as _impl

    return _impl(host, backup_ref=backup_ref)


def autotune_suggest(
    *,
    runner: Any,
    route_tag: str,
    feedback_text: str,
    out_dir: Path | None = None,
) -> tuple[RouteContext, list[TuningAdjustment]]:
    from ivan.game.autotune import load_route_context, suggest_invariant_adjustments

    context = load_route_context(route_tag=route_tag, out_dir=out_dir)
    adjustments = suggest_invariant_adjustments(
        feedback_text=feedback_text,
        tuning=runner.tuning,
        latest_summary=context.latest_summary,
        history_payload=context.history_payload,
    )
    return context, adjustments


def autotune_apply(
    *,
    runner: Any,
    route_tag: str,
    feedback_text: str,
    out_dir: Path | None = None,
) -> tuple[RouteContext, list[TuningAdjustment], Path | None]:
    context, adjustments = autotune_suggest(
        runner=runner,
        route_tag=route_tag,
        feedback_text=feedback_text,
        out_dir=out_dir,
    )
    if not adjustments:
        return context, adjustments, None

    backup_path = create_tuning_backup(
        runner,
        label=f"route-{context.route_tag}",
        reason="pre-autotune-apply",
    )
    on_change = getattr(runner, "_on_tuning_change", None)
    for adj in adjustments:
        field = str(adj.field)
        value: float | bool = bool(adj.after) if isinstance(adj.after, bool) else float(adj.after)
        setattr(runner.tuning, field, value)
        if callable(on_change):
            on_change(field)
    if not callable(on_change):
        persist_fn = getattr(runner, "_persist_profiles_state", None)
        if callable(persist_fn):
            persist_fn()
    return context, adjustments, backup_path


def autotune_eval(*, route_tag: str, out_dir: Path | None = None) -> AutotuneEvaluation:
    from ivan.game.autotune import evaluate_route_guardrails

    return evaluate_route_guardrails(route_tag=route_tag, out_dir=out_dir)


def autotune_rollback(*, runner: Any, backup_ref: str | None = None) -> Path:
    return restore_tuning_backup(runner, backup_ref=backup_ref)


def register_autotune_commands(*, con: Console, runner: Any) -> None:
    def _cmd_autotune_suggest(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if len(argv) < 2:
            return ["usage: autotune_suggest <route_tag> <feedback_text> [out_dir]"]
        route_tag = str(argv[0]).strip()
        feedback_text = str(argv[1])
        out_dir = _parse_out_dir(argv, 2)
        try:
            context, adjustments = autotune_suggest(
                runner=runner,
                route_tag=route_tag,
                feedback_text=feedback_text,
                out_dir=out_dir,
            )
        except Exception as e:
            return [f"error: {e}"]

        out = [
            f"route: {context.route_tag}",
            f"context: {context.note}",
            f"suggested: {len(adjustments)} invariant change(s)",
        ]
        if context.latest_summary_path is not None:
            out.append(f"latest_summary: {context.latest_summary_path}")
        if context.comparison_path is not None:
            out.append(f"comparison: {context.comparison_path}")
        if context.history_path is not None:
            out.append(f"history: {context.history_path}")
        if not adjustments:
            out.append("no invariant changes suggested")
            return out
        max_rows = 12
        out.extend(_format_adjustment(adj) for adj in adjustments[:max_rows])
        if len(adjustments) > max_rows:
            out.append(f"... +{len(adjustments) - max_rows} more")
        return out

    def _cmd_autotune_apply(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if len(argv) < 2:
            return ["usage: autotune_apply <route_tag> <feedback_text> [out_dir]"]
        route_tag = str(argv[0]).strip()
        feedback_text = str(argv[1])
        out_dir = _parse_out_dir(argv, 2)
        try:
            context, adjustments, backup_path = autotune_apply(
                runner=runner,
                route_tag=route_tag,
                feedback_text=feedback_text,
                out_dir=out_dir,
            )
        except Exception as e:
            return [f"error: {e}"]

        out = [
            f"route: {context.route_tag}",
            f"context: {context.note}",
            f"applied: {len(adjustments)} invariant change(s)",
        ]
        out.append(f"backup: {backup_path}" if backup_path is not None else "backup: skipped (no changes)")
        if adjustments:
            max_rows = 8
            out.extend(_format_adjustment(adj) for adj in adjustments[:max_rows])
            if len(adjustments) > max_rows:
                out.append(f"... +{len(adjustments) - max_rows} more")
        try:
            runner.ui.set_status(f"Autotune apply [{context.route_tag}]: {len(adjustments)} change(s)")
        except Exception:
            pass
        return out

    def _cmd_autotune_eval(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: autotune_eval <route_tag> [out_dir]"]
        route_tag = str(argv[0]).strip()
        out_dir = _parse_out_dir(argv, 1)
        try:
            result = autotune_eval(route_tag=route_tag, out_dir=out_dir)
        except Exception as e:
            return [f"error: {e}"]
        out = [
            f"route: {result.route_tag}",
            f"guardrails: {'pass' if result.passed else 'fail'}",
            f"score: {result.score:+.4f}",
            f"result: +{result.improved_count} / -{result.regressed_count} / ={result.equal_count}",
            f"comparison: {result.comparison_path}",
        ]
        if result.history_path is not None:
            out.append(f"history: {result.history_path}")
        out.extend(_format_check(check) for check in result.checks)
        return out

    def _cmd_autotune_rollback(_ctx: CommandContext, argv: list[str]) -> list[str]:
        ref = " ".join(str(x) for x in argv).strip() if argv else None
        try:
            restored = autotune_rollback(runner=runner, backup_ref=(ref or None))
        except Exception as e:
            return [f"error: {e}"]
        try:
            runner.ui.set_status(f"Autotune rollback restored: {Path(restored).name}")
        except Exception:
            pass
        return [f"restored: {restored}"]

    con.register_command(
        name="autotune_suggest",
        help="Suggest invariant-only route-scoped tuning deltas from feedback text.",
        handler=_cmd_autotune_suggest,
    )
    con.register_command(
        name="autotune_apply",
        help="Backup then apply route-scoped autotune invariant suggestions.",
        handler=_cmd_autotune_apply,
    )
    con.register_command(
        name="autotune_eval",
        help="Evaluate latest route run against guardrails and score.",
        handler=_cmd_autotune_eval,
    )
    con.register_command(
        name="autotune_rollback",
        help="Restore latest tuning backup (or optional backup ref).",
        handler=_cmd_autotune_rollback,
    )


__all__ = [
    "autotune_apply",
    "autotune_eval",
    "autotune_rollback",
    "autotune_suggest",
    "register_autotune_commands",
]
