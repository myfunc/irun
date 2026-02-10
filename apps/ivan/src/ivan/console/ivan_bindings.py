from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ivan.console.autotune_bindings import register_autotune_commands
from ivan.console.core import CommandContext, Console
from ivan.physics.tuning import PhysicsTuning


def export_latest_replay_telemetry(*, out_dir=None, route_tag=None, comment=None, route_name=None, run_note=None, feedback_text=None):
    from ivan.replays.telemetry import export_latest_replay_telemetry as _impl

    return _impl(
        out_dir=out_dir,
        route_tag=route_tag,
        comment=comment,
        route_name=route_name,
        run_note=run_note,
        feedback_text=feedback_text,
    )


def export_replay_telemetry(*, replay_path, out_dir=None, route_tag=None, comment=None, route_name=None, run_note=None, feedback_text=None):
    from ivan.replays.telemetry import export_replay_telemetry as _impl

    return _impl(
        replay_path=replay_path,
        out_dir=out_dir,
        route_tag=route_tag,
        comment=comment,
        route_name=route_name,
        run_note=run_note,
        feedback_text=feedback_text,
    )


def compare_latest_replays(*, out_dir=None, route_tag=None, latest_comment=None):
    from ivan.replays.compare import compare_latest_replays as _impl

    return _impl(out_dir=out_dir, route_tag=route_tag, latest_comment=latest_comment)


def _read_exec_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("//") or s.startswith("#"):
            continue
        out.append(s)
    return out


def build_client_console(runner: Any) -> Console:
    """
    Build a minimal console bound to a running RunnerDemo instance.

    We intentionally avoid an in-game UI for now; this is meant to be driven via MCP/control socket.
    """

    con = Console()

    def _cmd_help(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        lines: list[str] = ["commands:"]
        for name, help_s in con.list_commands():
            lines.append(f"  {name} - {help_s}".rstrip(" -"))
        lines.append("cvars:")
        for name, typ, help_s in con.list_cvars():
            lines.append(f"  {name} ({typ}) - {help_s}".rstrip(" -"))
        return lines

    def _cmd_echo(_ctx: CommandContext, argv: list[str]) -> list[str]:
        return [" ".join(argv)]

    def _cmd_exec(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: exec <path>"]
        p = Path(str(argv[0]))
        if not p.is_absolute():
            p = Path.cwd() / p
        lines = _read_exec_lines(p)
        out: list[str] = [f"exec {p} ({len(lines)} line(s))"]
        for ln in lines:
            out.extend(con.execute_line(ctx=CommandContext(role="client", origin="exec"), line=ln))
        return out

    def _cmd_connect(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: connect <host> [port]"]
        host = str(argv[0]).strip()
        port = None
        if len(argv) >= 2:
            try:
                port = int(str(argv[1]).strip())
            except Exception:
                return ["error: port must be an int"]
        if port is None:
            port = int(getattr(runner, "_runtime_connect_port", 7777))
        runner._on_connect_server_from_menu(host, str(port))  # noqa: SLF001
        return [f"connect {host}:{port}"]

    def _cmd_disconnect(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        runner._on_disconnect_server_from_menu()  # noqa: SLF001
        return ["disconnect"]

    def _cmd_replay_export_latest(_ctx: CommandContext, argv: list[str]) -> list[str]:
        out_dir = Path(str(argv[0])) if argv else None
        try:
            result = export_latest_replay_telemetry(out_dir=out_dir)
        except Exception as e:
            return [f"error: {e}"]
        return [
            f"source: {result.source_demo}",
            f"csv: {result.csv_path}",
            f"summary: {result.summary_path}",
            f"ticks: {result.tick_count} (telemetry: {result.telemetry_tick_count})",
        ]

    def _cmd_replay_export(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: replay_export <replay_path> [out_dir]"]
        replay_path = Path(str(argv[0]))
        if not replay_path.is_absolute():
            replay_path = Path.cwd() / replay_path
        out_dir = Path(str(argv[1])) if len(argv) >= 2 else None
        try:
            result = export_replay_telemetry(replay_path=replay_path, out_dir=out_dir)
        except Exception as e:
            return [f"error: {e}"]
        return [
            f"source: {result.source_demo}",
            f"csv: {result.csv_path}",
            f"summary: {result.summary_path}",
            f"ticks: {result.tick_count} (telemetry: {result.telemetry_tick_count})",
        ]

    def _cmd_replay_compare_latest(_ctx: CommandContext, argv: list[str]) -> list[str]:
        out_dir = Path(str(argv[0])) if argv else None
        route_tag = str(argv[1]).strip() if len(argv) >= 2 else None
        try:
            result = compare_latest_replays(out_dir=out_dir, route_tag=route_tag)
        except Exception as e:
            return [f"error: {e}"]
        return [
            f"latest: {result.latest_export.source_demo}",
            f"reference: {result.reference_export.source_demo}",
            f"comparison: {result.comparison_path}",
            f"result: +{result.improved_count} / -{result.regressed_count} / ={result.equal_count}",
        ]

    def _cmd_feel_feedback(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: feel_feedback <text> [route_tag]"]
        text = str(argv[0])
        route_tag = str(argv[1]).strip() if len(argv) >= 2 else ""
        fn = getattr(runner, "_feel_apply_feedback", None)
        if not callable(fn):
            return ["error: feel feedback is unavailable in this runtime"]
        try:
            fn(route_tag, text)
        except Exception as e:
            return [f"error: {e}"]
        return [f'feel_feedback applied for route="{route_tag or "none"}"']

    def _cmd_tuning_backup(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game.tuning_backups import create_tuning_backup

        label = " ".join(str(x) for x in argv).strip() if argv else ""
        try:
            out = create_tuning_backup(
                runner,
                label=(label or None),
                reason="manual-console",
            )
        except Exception as e:
            return [f"error: {e}"]
        return [f"backup: {out}"]

    def _cmd_tuning_restore(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game.tuning_backups import restore_tuning_backup

        ref = " ".join(str(x) for x in argv).strip() if argv else None
        try:
            out = restore_tuning_backup(runner, backup_ref=(ref or None))
        except Exception as e:
            return [f"error: {e}"]
        try:
            runner.ui.set_status(f"Tuning restored from backup: {Path(out).name}")
        except Exception:
            pass
        return [f"restored: {out}"]

    def _cmd_tuning_backups(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game.tuning_backups import backup_metadata, list_tuning_backups

        limit = 12
        if argv:
            try:
                limit = max(1, min(100, int(str(argv[0]))))
            except Exception:
                return ["usage: tuning_backups [limit]"]
        rows = list_tuning_backups(limit=limit)
        if not rows:
            return ["no tuning backups found"]
        out: list[str] = []
        for p in rows:
            try:
                md = backup_metadata(p)
            except Exception:
                out.append(f"{p.name}")
                continue
            profile = str(md.get("active_profile_name") or "-")
            label = str(md.get("label") or md.get("reason") or "-")
            fields = int(md.get("field_count") or 0)
            out.append(f"{p.name} | profile={profile} | fields={fields} | tag={label}")
        return out

    def _registry() -> dict[str, Any]:
        # Treat these as "entities" for now. We'll extend once map v3 entities exist.
        return {
            "runner": runner,
            "scene": getattr(runner, "scene", None),
            "player": getattr(runner, "player", None),
            "camera": getattr(runner, "camera", None),
            "world_root": getattr(runner, "world_root", None),
        }

    def _resolve_path(obj: Any, path: str | None) -> Any:
        if not path:
            return obj
        cur = obj
        for part in str(path).split("."):
            if cur is None:
                return None
            if isinstance(cur, dict) and part in cur:
                cur = cur.get(part)
                continue
            cur = getattr(cur, part, None)
        return cur

    def _cmd_ent_list(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        reg = _registry()
        out: list[str] = ["entities:"]
        for k in sorted(reg.keys()):
            v = reg[k]
            if v is None:
                out.append(f"  {k}: <none>")
            else:
                out.append(f"  {k}: {type(v).__name__}")
        return out

    def _cmd_ent_get(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: ent_get <name> [path]"]
        reg = _registry()
        obj = reg.get(str(argv[0]))
        if obj is None:
            return [f"error: unknown entity {argv[0]!r}"]
        path = str(argv[1]) if len(argv) >= 2 else None
        val = _resolve_path(obj, path)
        return [json.dumps(val, default=str, ensure_ascii=True)]

    def _cmd_ent_dir(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: ent_dir <name> [path]"]
        reg = _registry()
        obj = reg.get(str(argv[0]))
        if obj is None:
            return [f"error: unknown entity {argv[0]!r}"]
        path = str(argv[1]) if len(argv) >= 2 else None
        cur = _resolve_path(obj, path)
        if cur is None:
            return ["<none>"]
        keys: list[str] = []
        if isinstance(cur, dict):
            keys = [str(k) for k in cur.keys()]
        else:
            keys = [k for k in dir(cur) if k and not k.startswith("_")]
        keys.sort()
        keys = keys[:120]
        return keys

    def _cmd_ent_set(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if len(argv) < 3:
            return ["usage: ent_set <name> <path> <json>"]
        reg = _registry()
        obj = reg.get(str(argv[0]))
        if obj is None:
            return [f"error: unknown entity {argv[0]!r}"]
        path = str(argv[1])
        raw = " ".join(str(x) for x in argv[2:])
        try:
            val = json.loads(raw)
        except Exception:
            val = raw
        parts = path.split(".")
        parent = _resolve_path(obj, ".".join(parts[:-1]) if len(parts) > 1 else None)
        leaf = parts[-1]
        if parent is None:
            return ["error: path resolve failed"]
        if isinstance(parent, dict):
            parent[leaf] = val
            return ["ok"]
        try:
            setattr(parent, leaf, val)
        except Exception as e:
            return [f"error: setattr failed: {e}"]
        return ["ok"]

    def _cmd_ent_pos(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: ent_pos <name> [x y z]"]
        reg = _registry()
        obj = reg.get(str(argv[0]))
        if obj is None:
            return [f"error: unknown entity {argv[0]!r}"]

        def _get_pos(o: Any):
            if hasattr(o, "getPos"):
                try:
                    p = o.getPos()
                    return [float(p.x), float(p.y), float(p.z)]
                except Exception:
                    pass
            if hasattr(o, "pos"):
                try:
                    p = o.pos
                    return [float(p.x), float(p.y), float(p.z)]
                except Exception:
                    pass
            return None

        def _set_pos(o: Any, x: float, y: float, z: float) -> bool:
            if hasattr(o, "setPos"):
                try:
                    o.setPos(float(x), float(y), float(z))
                    return True
                except Exception:
                    pass
            if hasattr(o, "pos"):
                try:
                    p = o.pos
                    p.x = float(x)
                    p.y = float(y)
                    p.z = float(z)
                    o.pos = p
                    return True
                except Exception:
                    pass
            return False

        if len(argv) == 1:
            p = _get_pos(obj)
            return [json.dumps(p, ensure_ascii=True)] if p is not None else ["<no position>"]

        if len(argv) != 4:
            return ["usage: ent_pos <name> [x y z]"]
        try:
            x = float(argv[1])
            y = float(argv[2])
            z = float(argv[3])
        except Exception:
            return ["error: x y z must be numbers"]
        ok = _set_pos(obj, x, y, z)
        return ["ok"] if ok else ["error: failed to set position"]

    con.register_command(name="help", help="List commands and cvars.", handler=_cmd_help)
    con.register_command(name="echo", help="Print text.", handler=_cmd_echo)
    con.register_command(name="exec", help="Execute a .cfg-like script file.", handler=_cmd_exec)
    con.register_command(name="connect", help="Connect to a multiplayer server.", handler=_cmd_connect)
    con.register_command(name="disconnect", help="Disconnect from multiplayer.", handler=_cmd_disconnect)
    con.register_command(
        name="replay_export_latest",
        help="Export telemetry (CSV + JSON summary) for latest replay.",
        handler=_cmd_replay_export_latest,
    )
    con.register_command(
        name="replay_export",
        help="Export telemetry (CSV + JSON summary) for a replay path.",
        handler=_cmd_replay_export,
    )
    con.register_command(
        name="replay_compare_latest",
        help="Auto-export latest+previous replay telemetry and write a comparison summary.",
        handler=_cmd_replay_compare_latest,
    )
    con.register_command(
        name="feel_feedback",
        help="Apply rule-based tuning tweaks from feedback text + latest replay metrics.",
        handler=_cmd_feel_feedback,
    )
    con.register_command(
        name="tuning_backup",
        help="Save a tuning snapshot backup (optional label).",
        handler=_cmd_tuning_backup,
    )
    con.register_command(
        name="tuning_restore",
        help="Restore tuning from latest backup or by name/path.",
        handler=_cmd_tuning_restore,
    )
    con.register_command(
        name="tuning_backups",
        help="List recent tuning backups.",
        handler=_cmd_tuning_backups,
    )
    register_autotune_commands(con=con, runner=runner)
    con.register_command(name="ent_list", help="List registered entities/objects.", handler=_cmd_ent_list)
    con.register_command(name="ent_get", help="Get a property by path (dot-separated).", handler=_cmd_ent_get)
    con.register_command(name="ent_set", help="Set a property by path using JSON value.", handler=_cmd_ent_set)
    con.register_command(name="ent_dir", help="List keys/attrs for an entity or sub-path.", handler=_cmd_ent_dir)
    con.register_command(name="ent_pos", help="Get/set position for an entity.", handler=_cmd_ent_pos)

    for field, anno in PhysicsTuning.__annotations__.items():
        if not isinstance(field, str) or not field:
            continue
        # Keep types simple and predictable.
        typ = "float"
        if anno is bool:
            typ = "bool"
        elif anno is int:
            typ = "int"
        elif anno is str:
            typ = "str"

        def _make_getter(f: str):
            return lambda: getattr(runner.tuning, f)

        def _make_setter(f: str):
            def _set(v: Any) -> None:
                setattr(runner.tuning, f, v)
                runner._on_tuning_change(f)  # noqa: SLF001

            return _set

        con.register_cvar(
            name=field,
            typ=typ,
            get_value=_make_getter(field),
            set_value=_make_setter(field),
            help="Physics tuning field.",
        )

    return con
