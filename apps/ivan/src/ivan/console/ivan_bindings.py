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
            if not isinstance(payload, dict):
                return [json.dumps(payload, ensure_ascii=True)]
            lines: list[str] = ["world_runtime:"]
            for key in sorted(payload.keys()):
                val = payload.get(key)
                if isinstance(val, dict):
                    lines.append(f"  {key}:")
                    for sub_key in sorted(val.keys()):
                        sub_val = val.get(sub_key)
                        lines.append(f"    - {sub_key}: {json.dumps(sub_val, ensure_ascii=True)}")
                    continue
                lines.append(f"  {key}: {json.dumps(val, ensure_ascii=True)}")
            return lines
        return [json.dumps({"error": "diagnostics-unavailable"}, ensure_ascii=True)]

    def _parse_bool_token(raw: Any, *, default: bool | None = None) -> bool:
        if isinstance(raw, bool):
            return bool(raw)
        token = str(raw or "").strip().lower()
        if token in ("1", "true", "on", "yes", "y", "pixelated", "nearest"):
            return True
        if token in ("0", "false", "off", "no", "n", "smooth", "linear"):
            return False
        if default is not None:
            return bool(default)
        raise ValueError(f"invalid bool token: {raw!r}")

    def _cmd_world_textures(_ctx: CommandContext, argv: list[str]) -> list[str]:
        if not argv:
            return ["usage: world_textures <pixelated|smooth|on|off|1|0> [reload:true|false]"]
        try:
            pixelated = _parse_bool_token(argv[0])
            reload_scene = _parse_bool_token(argv[1], default=True) if len(argv) >= 2 else True
        except Exception as e:
            return [f"error: {e}"]
        setter = getattr(runner, "_set_pixelated_textures_enabled", None)
        if not callable(setter):
            return ["error: runtime texture toggle is unavailable"]
        payload = setter(enabled=bool(pixelated), reload_scene=bool(reload_scene))
        return [json.dumps(payload, ensure_ascii=True)]

    def _vm_rpg_state_lines(state: dict[str, object]) -> list[str]:
        return [
            f"vm_rpg.pos={json.dumps(state.get('pos'), ensure_ascii=True)}",
            f"vm_rpg.hpr={json.dumps(state.get('hpr'), ensure_ascii=True)}",
            f"vm_rpg.model_hpr={json.dumps(state.get('model_hpr'), ensure_ascii=True)}",
            f"vm_rpg.model_scale={json.dumps(state.get('model_scale'), ensure_ascii=True)}",
            f"vm_rpg.size={json.dumps(state.get('target_longest'), ensure_ascii=True)}",
        ]

    def _cmd_vm_rpg_print(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        try:
            state = _combat_fx.imported_rpg_debug_state()
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _parse_triplet(argv: list[str]) -> tuple[float, float, float] | None:
        if len(argv) != 3:
            return None
        try:
            return (float(argv[0]), float(argv[1]), float(argv[2]))
        except Exception:
            return None

    def _cmd_vm_rpg_pos(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        if not argv:
            return _vm_rpg_state_lines(_combat_fx.imported_rpg_debug_state())
        triplet = _parse_triplet(argv)
        if triplet is None:
            return ["usage: vm_rpg_pos <x> <y> <z>"]
        try:
            state = _combat_fx.set_imported_rpg_debug_state(runner, pos=triplet)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _cmd_vm_rpg_hpr(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        if not argv:
            return _vm_rpg_state_lines(_combat_fx.imported_rpg_debug_state())
        triplet = _parse_triplet(argv)
        if triplet is None:
            return ["usage: vm_rpg_hpr <h> <p> <r>"]
        try:
            state = _combat_fx.set_imported_rpg_debug_state(runner, hpr=triplet)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _cmd_vm_rpg_model_hpr(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        if not argv:
            return _vm_rpg_state_lines(_combat_fx.imported_rpg_debug_state())
        triplet = _parse_triplet(argv)
        if triplet is None:
            return ["usage: vm_rpg_model_hpr <h> <p> <r>"]
        try:
            state = _combat_fx.set_imported_rpg_debug_state(runner, model_hpr=triplet)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _cmd_vm_rpg_size(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        if not argv:
            return _vm_rpg_state_lines(_combat_fx.imported_rpg_debug_state())
        if len(argv) != 1:
            return ["usage: vm_rpg_size <value>"]
        try:
            value = float(argv[0])
        except Exception:
            return ["error: size must be a number"]
        try:
            state = _combat_fx.set_imported_rpg_debug_state(runner, target_longest=value)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _cmd_vm_rpg_model_scale(_ctx: CommandContext, argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        if not argv:
            return _vm_rpg_state_lines(_combat_fx.imported_rpg_debug_state())
        triplet = _parse_triplet(argv)
        if triplet is None:
            return ["usage: vm_rpg_model_scale <x> <y> <z>"]
        try:
            state = _combat_fx.set_imported_rpg_debug_state(runner, model_scale=triplet)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _cmd_vm_rpg_reset(_ctx: CommandContext, _argv: list[str]) -> list[str]:
        from ivan.game import combat_fx as _combat_fx

        try:
            state = _combat_fx.reset_imported_rpg_debug_state(runner)
        except Exception as e:
            return [f"error: {e}"]
        return _vm_rpg_state_lines(state)

    def _bus_help(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        cmd = str(args.get("command") or "").strip()
        if cmd:
            return CommandResult.success(out=_format_bus_meta(cmd))
        return CommandResult.success(out=_cmd_help(_ctx, []))

    def _bus_meta(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        prefix = str(args.get("prefix") or "").strip().casefold()
        tag_filter = str(args.get("tag") or "").strip().casefold()
        page = max(1, int(args.get("page") or 1))
        page_size = max(1, min(200, int(args.get("page_size") or 50)))
        rows: list[dict[str, Any]] = []
        for meta in con.list_command_metadata():
            if prefix and prefix not in str(meta.name).casefold():
                continue
            if tag_filter and tag_filter not in (t.casefold() for t in meta.tags):
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
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = rows[start:end]
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        payload = {
            "commands": page_rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }
        return CommandResult.success(out=[json.dumps(payload, ensure_ascii=True)], data=payload)

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

    def _bus_world_textures_set(_ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        setter = getattr(runner, "_set_pixelated_textures_enabled", None)
        if not callable(setter):
            return CommandResult.failure("runtime texture toggle is unavailable", error_code="world-textures")
        try:
            pixelated = _parse_bool_token(args.get("pixelated"), default=True)
            reload_scene = _parse_bool_token(args.get("reload"), default=True)
            payload = setter(enabled=bool(pixelated), reload_scene=bool(reload_scene))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="world-textures")
        if not bool(payload.get("ok", True)):
            return CommandResult.failure(str(payload.get("error") or "failed to update texture mode"), error_code="world-textures")
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
            summary="Dump typed command metadata as JSON with filtering and pagination.",
            route="immediate",
            tags=("discoverability", "mcp"),
            args=(
                CommandArgSpec(name="prefix", typ="str", required=False, default="", help="Optional name prefix filter."),
                CommandArgSpec(name="tag", typ="str", required=False, default="", help="Optional tag filter (command must have this tag)."),
                CommandArgSpec(name="page", typ="int", required=False, default=1, minimum=1, help="Page index (1-based)."),
                CommandArgSpec(
                    name="page_size",
                    typ="int",
                    required=False,
                    default=50,
                    minimum=1,
                    maximum=200,
                    help="Items per page (max 200).",
                ),
            ),
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
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_textures_set",
            summary="Toggle runtime pixelated/smooth base texture sampling mode.",
            route="game-thread",
            tags=("world", "render", "textures", "mcp"),
            args=(
                CommandArgSpec(
                    name="pixelated",
                    typ="bool",
                    required=False,
                    default=True,
                    help="True = nearest/pixelated, False = smooth filtering.",
                ),
                CommandArgSpec(
                    name="reload",
                    typ="bool",
                    required=False,
                    default=True,
                    help="When true, reload current map to apply to all textures.",
                ),
            ),
        ),
        handler=_bus_world_textures_set,
    )

    def _legacy_wrap(legacy_handler, meta: CommandMetadata):
        def _wrapped(ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
            argv: list[str] = []
            for spec in meta.args:
                v = args.get(spec.name)
                if spec.required:
                    argv.append(str(v) if v is not None else "")
                elif v is not None and v != "":
                    argv.append(str(v))
            try:
                out = legacy_handler(ctx, argv)
                return CommandResult.success(out=list(out))
            except Exception as e:
                return CommandResult.failure(str(e), error_code="handler-error")

        return _wrapped

    _echo_meta = CommandMetadata(
        name="echo",
        summary="Print text.",
        route="immediate",
        tags=("utility",),
        args=(CommandArgSpec(name="text", typ="str", required=False, default="", help="Text to print.", greedy=True),),
    )
    con.register_bus_command(metadata=_echo_meta, handler=_legacy_wrap(_cmd_echo, _echo_meta))
    con.register_bus_command(
        metadata=CommandMetadata(
            name="exec",
            summary="Execute a .cfg-like script file.",
            route="immediate",
            tags=("utility",),
            args=(CommandArgSpec(name="path", typ="str", required=True, help="Path to script file."),),
        ),
        handler=_legacy_wrap(
            _cmd_exec,
            CommandMetadata(name="exec", summary="", args=(CommandArgSpec(name="path", typ="str", required=True),)),
        ),
    )
    def _bus_connect(ctx: CommandContext, args: dict[str, Any]) -> CommandResult:
        host = str(args.get("host") or "").strip()
        if not host:
            return CommandResult.failure("usage: connect <host> [port]", error_code="usage")
        argv = [host]
        if args.get("port") is not None:
            argv.append(str(args["port"]))
        try:
            return CommandResult.success(out=_cmd_connect(ctx, argv))
        except Exception as e:
            return CommandResult.failure(str(e), error_code="connect")

    con.register_bus_command(
        metadata=CommandMetadata(
            name="connect",
            summary="Connect to a multiplayer server.",
            route="immediate",
            tags=("multiplayer",),
            args=(
                CommandArgSpec(name="host", typ="str", required=True, help="Server host."),
                CommandArgSpec(name="port", typ="int", required=False, default=None, help="Server port (default from runtime)."),
            ),
        ),
        handler=_bus_connect,
    )
    con.register_bus_command(
        metadata=CommandMetadata(name="disconnect", summary="Disconnect from multiplayer.", route="immediate", tags=("multiplayer",), args=()),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_disconnect(ctx, [])),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="replay_export_latest",
            summary="Export telemetry (CSV + JSON summary) for latest replay.",
            route="immediate",
            tags=("replay", "telemetry", "mcp"),
            args=(CommandArgSpec(name="out_dir", typ="str", required=False, default="", help="Optional output directory."),),
        ),
        handler=_legacy_wrap(
            _cmd_replay_export_latest,
            CommandMetadata(name="replay_export_latest", summary="", args=(CommandArgSpec(name="out_dir", typ="str", required=False, default=""),)),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="replay_export",
            summary="Export telemetry (CSV + JSON summary) for a replay path.",
            route="immediate",
            tags=("replay", "telemetry", "mcp"),
            args=(
                CommandArgSpec(name="replay_path", typ="str", required=True, help="Path to replay file."),
                CommandArgSpec(name="out_dir", typ="str", required=False, default="", help="Optional output directory."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_replay_export,
            CommandMetadata(
                name="replay_export",
                summary="",
                args=(
                    CommandArgSpec(name="replay_path", typ="str", required=True),
                    CommandArgSpec(name="out_dir", typ="str", required=False, default=""),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="replay_compare_latest",
            summary="Auto-export latest+previous replay telemetry and write a comparison summary.",
            route="immediate",
            tags=("replay", "telemetry", "mcp"),
            args=(
                CommandArgSpec(name="out_dir", typ="str", required=False, default="", help="Optional output directory."),
                CommandArgSpec(name="route_tag", typ="str", required=False, default="", help="Optional route tag filter."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_replay_compare_latest,
            CommandMetadata(
                name="replay_compare_latest",
                summary="",
                args=(
                    CommandArgSpec(name="out_dir", typ="str", required=False, default=""),
                    CommandArgSpec(name="route_tag", typ="str", required=False, default=""),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="feel_feedback",
            summary="Apply rule-based tuning tweaks from feedback text + latest replay metrics.",
            route="immediate",
            tags=("tuning", "feel", "mcp"),
            args=(
                CommandArgSpec(name="text", typ="str", required=True, help="Feedback text."),
                CommandArgSpec(name="route_tag", typ="str", required=False, default="", help="Optional route tag."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_feel_feedback,
            CommandMetadata(
                name="feel_feedback",
                summary="",
                args=(
                    CommandArgSpec(name="text", typ="str", required=True),
                    CommandArgSpec(name="route_tag", typ="str", required=False, default=""),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="tuning_backup",
            summary="Save a tuning snapshot backup (optional label).",
            route="immediate",
            tags=("tuning", "mcp"),
            args=(CommandArgSpec(name="label", typ="str", required=False, default="", help="Optional backup label."),),
        ),
        handler=_legacy_wrap(
            _cmd_tuning_backup,
            CommandMetadata(name="tuning_backup", summary="", args=(CommandArgSpec(name="label", typ="str", required=False, default=""),)),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="tuning_restore",
            summary="Restore tuning from latest backup or by name/path.",
            route="immediate",
            tags=("tuning", "mcp"),
            args=(CommandArgSpec(name="backup_ref", typ="str", required=False, default="", help="Backup name or path."),),
        ),
        handler=_legacy_wrap(
            _cmd_tuning_restore,
            CommandMetadata(name="tuning_restore", summary="", args=(CommandArgSpec(name="backup_ref", typ="str", required=False, default=""),)),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="tuning_backups",
            summary="List recent tuning backups.",
            route="immediate",
            tags=("tuning", "mcp"),
            args=(CommandArgSpec(name="limit", typ="int", required=False, default=12, minimum=1, maximum=100, help="Max backups to list."),),
        ),
        handler=_legacy_wrap(
            _cmd_tuning_backups,
            CommandMetadata(name="tuning_backups", summary="", args=(CommandArgSpec(name="limit", typ="int", required=False, default=12),)),
        ),
    )
    register_autotune_commands(con=con, runner=runner)
    con.register_bus_command(
        metadata=CommandMetadata(name="ent_list", summary="List registered entities/objects.", route="immediate", tags=("introspection",), args=()),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_ent_list(ctx, [])),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="ent_get",
            summary="Get a property by path (dot-separated).",
            route="immediate",
            tags=("introspection",),
            args=(
                CommandArgSpec(name="name", typ="str", required=True, help="Entity name."),
                CommandArgSpec(name="path", typ="str", required=False, default="", help="Optional dot-separated path."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_ent_get,
            CommandMetadata(
                name="ent_get",
                summary="",
                args=(
                    CommandArgSpec(name="name", typ="str", required=True),
                    CommandArgSpec(name="path", typ="str", required=False, default=""),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="ent_set",
            summary="Set a property by path using JSON value.",
            route="immediate",
            tags=("introspection",),
            args=(
                CommandArgSpec(name="name", typ="str", required=True, help="Entity name."),
                CommandArgSpec(name="path", typ="str", required=True, help="Dot-separated path."),
                CommandArgSpec(name="value", typ="str", required=True, help="JSON value or raw string."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_ent_set,
            CommandMetadata(
                name="ent_set",
                summary="",
                args=(
                    CommandArgSpec(name="name", typ="str", required=True),
                    CommandArgSpec(name="path", typ="str", required=True),
                    CommandArgSpec(name="value", typ="str", required=True),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="ent_dir",
            summary="List keys/attrs for an entity or sub-path.",
            route="immediate",
            tags=("introspection",),
            args=(
                CommandArgSpec(name="name", typ="str", required=True, help="Entity name."),
                CommandArgSpec(name="path", typ="str", required=False, default="", help="Optional dot-separated path."),
            ),
        ),
        handler=_legacy_wrap(
            _cmd_ent_dir,
            CommandMetadata(
                name="ent_dir",
                summary="",
                args=(
                    CommandArgSpec(name="name", typ="str", required=True),
                    CommandArgSpec(name="path", typ="str", required=False, default=""),
                ),
            ),
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="ent_pos",
            summary="Get/set position for an entity.",
            route="immediate",
            tags=("introspection",),
            args=(
                CommandArgSpec(name="name", typ="str", required=True, help="Entity name."),
                CommandArgSpec(name="x", typ="float", required=False, default=None, help="X coordinate (omit for get)."),
                CommandArgSpec(name="y", typ="float", required=False, default=None, help="Y coordinate (omit for get)."),
                CommandArgSpec(name="z", typ="float", required=False, default=None, help="Z coordinate (omit for get)."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_ent_pos(
                ctx,
                [str(args["name"])]
                + ([str(args["x"]), str(args["y"]), str(args["z"])] if args.get("x") is not None and args.get("y") is not None and args.get("z") is not None else []),
            )
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_runtime",
            summary="Dump world runtime path + sky/fog diagnostics as JSON.",
            route="immediate",
            tags=("world", "introspection", "mcp"),
            args=(),
        ),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_world_runtime(ctx, [])),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="world_textures",
            summary="Toggle world texture filtering mode (pixelated/smooth), optionally reloading the map.",
            route="immediate",
            tags=("world", "render", "mcp"),
            args=(
                CommandArgSpec(name="pixelated", typ="bool", required=True, help="True = pixelated, False = smooth."),
                CommandArgSpec(name="reload", typ="bool", required=False, default=True, help="Reload scene to apply."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_world_textures(ctx, [str(args.get("pixelated", True)), str(args.get("reload", True))])
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_print",
            summary="Print imported RPG viewmodel debug transform state.",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(),
        ),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_vm_rpg_print(ctx, [])),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_pos",
            summary="Get/set imported RPG weapon root position (x y z).",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(
                CommandArgSpec(name="x", typ="float", required=False, default=None, help="X (omit for get)."),
                CommandArgSpec(name="y", typ="float", required=False, default=None, help="Y (omit for get)."),
                CommandArgSpec(name="z", typ="float", required=False, default=None, help="Z (omit for get)."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_vm_rpg_pos(ctx, [str(args["x"]), str(args["y"]), str(args["z"])] if args.get("x") is not None and args.get("y") is not None and args.get("z") is not None else [])
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_hpr",
            summary="Get/set imported RPG weapon root rotation (h p r).",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(
                CommandArgSpec(name="h", typ="float", required=False, default=None, help="Heading (omit for get)."),
                CommandArgSpec(name="p", typ="float", required=False, default=None, help="Pitch (omit for get)."),
                CommandArgSpec(name="r", typ="float", required=False, default=None, help="Roll (omit for get)."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_vm_rpg_hpr(ctx, [str(args["h"]), str(args["p"]), str(args["r"])] if args.get("h") is not None and args.get("p") is not None and args.get("r") is not None else [])
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_model_hpr",
            summary="Get/set imported RPG model-pivot rotation (h p r).",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(
                CommandArgSpec(name="h", typ="float", required=False, default=None, help="Heading (omit for get)."),
                CommandArgSpec(name="p", typ="float", required=False, default=None, help="Pitch (omit for get)."),
                CommandArgSpec(name="r", typ="float", required=False, default=None, help="Roll (omit for get)."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_vm_rpg_model_hpr(ctx, [str(args["h"]), str(args["p"]), str(args["r"])] if args.get("h") is not None and args.get("p") is not None and args.get("r") is not None else [])
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_size",
            summary="Get/set imported RPG viewmodel size scalar.",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(CommandArgSpec(name="value", typ="float", required=False, default=None, help="Size scalar (omit for get)."),),
        ),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_vm_rpg_size(ctx, [str(args["value"])] if args.get("value") is not None else [])),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_model_scale",
            summary="Get/set imported RPG model-pivot scale vector (x y z).",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(
                CommandArgSpec(name="x", typ="float", required=False, default=None, help="Scale X (omit for get)."),
                CommandArgSpec(name="y", typ="float", required=False, default=None, help="Scale Y (omit for get)."),
                CommandArgSpec(name="z", typ="float", required=False, default=None, help="Scale Z (omit for get)."),
            ),
        ),
        handler=lambda ctx, args: CommandResult.success(
            out=_cmd_vm_rpg_model_scale(ctx, [str(args["x"]), str(args["y"]), str(args["z"])] if args.get("x") is not None and args.get("y") is not None and args.get("z") is not None else [])
        ),
    )
    con.register_bus_command(
        metadata=CommandMetadata(
            name="vm_rpg_reset",
            summary="Reset imported RPG debug transform to defaults.",
            route="game-thread",
            tags=("viewmodel", "rpg", "mcp"),
            args=(),
        ),
        handler=lambda ctx, args: CommandResult.success(out=_cmd_vm_rpg_reset(ctx, [])),
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
