from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ivan.console.command_bus import CommandArgSpec, CommandMetadata, CommandResult
from ivan.console.autotune_bindings import register_autotune_commands
from ivan.console.core import CommandContext, Console
from ivan.console.scene_runtime import SceneRuntimeRegistry
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
    scene_runtime = SceneRuntimeRegistry(runner=runner)

    def _format_bus_meta(name: str) -> list[str]:
        meta = con.find_command_metadata(name)
        if meta is None:
            return [f"unknown command: {name}"]
        lines = [f"{meta.name}: {meta.summary}", f"route: {meta.route}"]
        if meta.tags:
            lines.append(f"tags: {', '.join(meta.tags)}")
        if meta.args:
            lines.append("args:")
            for a in meta.args:
                req = "required" if bool(a.required and a.default is None) else "optional"
                default = "" if a.default is None else f" default={a.default}"
                choices = "" if not a.choices else f" choices={','.join(a.choices)}"
                lines.append(f"  --{a.name} ({a.typ}, {req}){default}{choices} {a.help}".rstrip())
        return lines

    def _cmd_help(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if argv:
            return _format_bus_meta(str(argv[0]))
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

    def _cmd_world_runtime(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        scene = getattr(runner, "scene", None)
        if scene is None:
            return [json.dumps({"error": "scene-unavailable"}, ensure_ascii=True)]
        fn = getattr(scene, "runtime_world_diagnostics", None)
        if callable(fn):
            try:
                payload = fn()
            except Exception as e:
                return [json.dumps({"error": str(e)}, ensure_ascii=True)]
            return [json.dumps(payload, ensure_ascii=True)]
        return [json.dumps({"error": "diagnostics-unavailable"}, ensure_ascii=True)]

    def _bus_help(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        cmd = str(args.get("command") or "").strip()
        if cmd:
            return CommandResult.success(out=_format_bus_meta(cmd))
        return CommandResult.success(out=_cmd_help(_ctx, []))

    def _bus_meta(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        prefix = str(args.get("prefix") or "").strip().casefold()
        rows: list[dict[str, Any]] = []
        for meta in con.list_command_metadata():
            if prefix and prefix not in str(meta.name).casefold():
                continue
            rows.append(
                {
                    "name": meta.name,
                    "summary": meta.summary,
                    "route": meta.route,
                    "tags": list(meta.tags),
                    "args": [
                        {
                            "name": a.name,
                            "type": a.typ,
                            "required": bool(a.required and a.default is None),
                            "default": a.default,
                            "help": a.help,
                            "choices": list(a.choices),
                        }
                        for a in meta.args
                    ],
                }
            )
        rows.sort(key=lambda x: str(x.get("name") or ""))
        return CommandResult.success(out=[json.dumps({"commands": rows}, ensure_ascii=True)], data={"commands": rows})

    def _bus_scene_list(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.list_objects(
                name=str(args.get("name") or ""),
                typ=str(args.get("type") or ""),
                tag=str(args.get("tag") or ""),
                page=int(args.get("page") or 1),
                page_size=int(args.get("page_size") or 25),
            )
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-list")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_select(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.select_object(target=str(args.get("target") or ""))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-select")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_inspect(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        target = str(args.get("target") or "").strip() or None
        try:
            payload = scene_runtime.inspect_selected(target=target)
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-inspect")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_player_look(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.player_look_target(distance=float(args.get("distance") or 256.0))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="player-look")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_create(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.create_object(
                object_type=str(args.get("object_type") or ""),
                name=str(args.get("name") or "runtime_obj"),
            )
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-create")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_delete(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        target = str(args.get("target") or "").strip() or None
        try:
            payload = scene_runtime.delete_object(target=target)
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-delete")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_transform(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        target = str(args.get("target") or "").strip() or None
        try:
            payload = scene_runtime.transform_object(
                target=target,
                mode=str(args.get("mode") or "move"),
                x=float(args.get("x") or 0.0),
                y=float(args.get("y") or 0.0),
                z=float(args.get("z") or 0.0),
                relative=bool(args.get("relative")),
            )
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-transform")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_group(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        raw_targets = str(args.get("targets") or "").strip()
        targets = [s for s in (x.strip() for x in raw_targets.split(",")) if s]
        try:
            payload = scene_runtime.group_objects(group_id=str(args.get("group_id") or ""), targets=targets)
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-group")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_ungroup(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.ungroup(group_id=str(args.get("group_id") or ""))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-ungroup")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_scene_group_transform(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.group_transform(
                group_id=str(args.get("group_id") or ""),
                mode=str(args.get("mode") or "move"),
                x=float(args.get("x") or 0.0),
                y=float(args.get("y") or 0.0),
                z=float(args.get("z") or 0.0),
                relative=bool(args.get("relative")),
            )
        except Exception as e:
            return CommandResult.failure(str(e), error_code="scene-group-transform")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_world_fog_set(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.set_world_fog(
                mode=str(args.get("mode") or "exp2"),
                start=float(args.get("start") or 120.0),
                end=float(args.get("end") or 360.0),
                density=float(args.get("density") or 0.02),
                color_r=float(args.get("color_r") or 0.63),
                color_g=float(args.get("color_g") or 0.67),
                color_b=float(args.get("color_b") or 0.73),
            )
        except Exception as e:
            return CommandResult.failure(str(e), error_code="world-fog")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_world_skybox_set(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.set_world_skybox(skyname=str(args.get("skyname") or ""))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="world-skybox")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    def _bus_world_map_save(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        try:
            payload = scene_runtime.save_world_map(include_fog=bool(args.get("include_fog", True)))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="world-map-save")
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

    con.register_bus_command(
        metadata=CommandMetadata(
            name="help",
            summary="List commands or command details.",
            route="immediate",
            tags=("discoverability",),
            args=(CommandArgSpec(name="command", typ="str", required=False, default="", help="Optional command name."),),
        ),
        handler=_bus_help,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="cmd_meta",
            summary="Dump typed command metadata as JSON.",
            route="immediate",
            tags=("discoverability", "mcp"),
            args=(CommandArgSpec(name="prefix", typ="str", required=False, default="", help="Optional name prefix filter."),),
        ),
        handler=_bus_meta,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_list",
            summary="List scene objects with filters + pagination.",
            route="game-thread",
            tags=("scene", "introspection", "mcp"),
            args=(
                CommandArgSpec(name="name", typ="str", required=False, default="", help="Case-insensitive name filter."),
                CommandArgSpec(name="type", typ="str", required=False, default="", help="Case-insensitive node type filter."),
                CommandArgSpec(name="tag", typ="str", required=False, default="", help="Tag key filter."),
                CommandArgSpec(name="page", typ="int", required=False, default=1, minimum=1, help="Page index (1-based)."),
                CommandArgSpec(
                    name="page_size",
                    typ="int",
                    required=False,
                    default=25,
                    minimum=1,
                    maximum=200,
                    help="Items per page (max 200).",
                ),
            ),
        ),
        handler=_bus_scene_list,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_select",
            summary="Select scene object by id or exact name.",
            route="game-thread",
            tags=("scene", "introspection", "mcp"),
            args=(CommandArgSpec(name="target", typ="str", required=True, help="Object id or exact name."),),
        ),
        handler=_bus_scene_select,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_inspect",
            summary="Inspect selected object details.",
            route="game-thread",
            tags=("scene", "introspection", "mcp"),
            args=(CommandArgSpec(name="target", typ="str", required=False, default="", help="Optional object id/name override."),),
        ),
        handler=_bus_scene_inspect,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="player_look_target",
            summary="Report current player look-target raycast hit.",
            route="game-thread",
            tags=("scene", "introspection", "mcp"),
            args=(
                CommandArgSpec(
                    name="distance",
                    typ="float",
                    required=False,
                    default=256.0,
                    minimum=1.0,
                    maximum=5000.0,
                    help="Raycast distance in world units.",
                ),
            ),
        ),
        handler=_bus_player_look,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_create",
            summary="Create a runtime scene object by type.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(
                CommandArgSpec(name="object_type", typ="str", required=True, choices=("box", "sphere", "empty"), help="Object kind."),
                CommandArgSpec(name="name", typ="str", required=False, default="runtime_obj", help="Node name."),
            ),
        ),
        handler=_bus_scene_create,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_delete",
            summary="Delete selected scene object or explicit target.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(CommandArgSpec(name="target", typ="str", required=False, default="", help="Optional object id/name."),),
        ),
        handler=_bus_scene_delete,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_transform",
            summary="Move/rotate/scale object transform.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(
                CommandArgSpec(name="mode", typ="str", required=True, choices=("move", "rotate", "scale"), help="Transform mode."),
                CommandArgSpec(name="x", typ="float", required=True, help="X / H / scale-x value."),
                CommandArgSpec(name="y", typ="float", required=True, help="Y / P / scale-y value."),
                CommandArgSpec(name="z", typ="float", required=True, help="Z / R / scale-z value."),
                CommandArgSpec(name="target", typ="str", required=False, default="", help="Optional object id/name."),
                CommandArgSpec(name="relative", typ="bool", required=False, default=False, help="Apply delta in local space."),
            ),
        ),
        handler=_bus_scene_transform,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_group",
            summary="Group objects under a shared transform root.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(
                CommandArgSpec(name="group_id", typ="str", required=True, help="Group id."),
                CommandArgSpec(
                    name="targets",
                    typ="str",
                    required=True,
                    help="Comma-separated object ids/names.",
                ),
            ),
        ),
        handler=_bus_scene_group,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_ungroup",
            summary="Ungroup all objects from a group root.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(CommandArgSpec(name="group_id", typ="str", required=True, help="Group id."),),
        ),
        handler=_bus_scene_ungroup,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="scene_group_transform",
            summary="Move/rotate/scale a whole group transform.",
            route="game-thread",
            tags=("scene", "manipulation", "mcp"),
            args=(
                CommandArgSpec(name="group_id", typ="str", required=True, help="Group id."),
                CommandArgSpec(name="mode", typ="str", required=True, choices=("move", "rotate", "scale"), help="Transform mode."),
                CommandArgSpec(name="x", typ="float", required=True, help="X / H / scale-x value."),
                CommandArgSpec(name="y", typ="float", required=True, help="Y / P / scale-y value."),
                CommandArgSpec(name="z", typ="float", required=True, help="Z / R / scale-z value."),
                CommandArgSpec(name="relative", typ="bool", required=False, default=False, help="Apply delta in local space."),
            ),
        ),
        handler=_bus_scene_group_transform,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_fog_set",
            summary="Apply runtime fog override with validation.",
            route="game-thread",
            tags=("world", "fog", "mcp"),
            args=(
                CommandArgSpec(name="mode", typ="str", required=False, default="exp2", choices=("off", "linear", "exp", "exp2")),
                CommandArgSpec(name="start", typ="float", required=False, default=120.0),
                CommandArgSpec(name="end", typ="float", required=False, default=360.0),
                CommandArgSpec(name="density", typ="float", required=False, default=0.02, minimum=0.0),
                CommandArgSpec(name="color_r", typ="float", required=False, default=0.63, minimum=0.0, maximum=1.0),
                CommandArgSpec(name="color_g", typ="float", required=False, default=0.67, minimum=0.0, maximum=1.0),
                CommandArgSpec(name="color_b", typ="float", required=False, default=0.73, minimum=0.0, maximum=1.0),
            ),
        ),
        handler=_bus_world_fog_set,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_skybox_set",
            summary="Switch runtime skybox preset with validation.",
            route="game-thread",
            tags=("world", "skybox", "mcp"),
            args=(CommandArgSpec(name="skyname", typ="str", required=True, help="Skybox preset name."),),
        ),
        handler=_bus_world_skybox_set,
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_map_save",
            summary="Persist pending world overrides into map.json.",
            route="game-thread",
            tags=("world", "map", "save", "mcp"),
            args=(
                CommandArgSpec(
                    name="include_fog",
                    typ="bool",
                    required=False,
                    default=True,
                    help="When true, writes pending fog override into map.json fog block.",
                ),
            ),
        ),
        handler=_bus_world_map_save,
    )

    # Legacy/compat commands remain available for existing scripts.
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
    con.register_command(
        name="world_runtime",
        help="Dump world runtime path + sky/fog diagnostics as JSON.",
        handler=_cmd_world_runtime,
    )

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
