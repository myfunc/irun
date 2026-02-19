"""Tests for server console typed command behavior and metadata discoverability."""

from __future__ import annotations

import json
from types import SimpleNamespace

from ivan.console.core import CommandContext
from ivan.console.server_bindings import build_server_console


def _fake_server() -> SimpleNamespace:
    """Minimal server mock with tuning and apply path."""
    tuning = SimpleNamespace()
    for f in ("jump_height", "max_ground_speed", "surf_enabled"):
        setattr(tuning, f, 1.0 if f == "surf_enabled" else 6.0)
    server = SimpleNamespace()
    server.tuning = tuning
    server._tuning_version = 1

    def _apply(snap: dict) -> None:
        for k, v in snap.items():
            if hasattr(server.tuning, k):
                setattr(server.tuning, k, v)

    server._apply_tuning_snapshot = _apply
    return server


def test_server_echo_command() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="echo hello world")
    assert out == ["hello world"]


def test_server_help_lists_commands_and_cvars() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="help")
    assert any("commands:" in line for line in out)
    assert any("cvars:" in line for line in out)
    assert any("help" in line for line in out)
    assert any("echo" in line for line in out)
    assert any("exec" in line for line in out)
    assert any("cmd_meta" in line for line in out)


def test_server_help_command_detail() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="help cmd_meta")
    assert out
    assert any("cmd_meta" in line for line in out)
    assert any("prefix" in line or "tag" in line or "page" in line for line in out)


def test_server_cmd_meta_exposes_typed_registry() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="cmd_meta")
    assert out
    payload = json.loads(out[0])
    assert "commands" in payload
    names = [c["name"] for c in payload["commands"]]
    assert "help" in names
    assert "echo" in names
    assert "exec" in names
    assert "cmd_meta" in names


def test_server_cmd_meta_prefix_filter() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="cmd_meta --prefix cmd_")
    assert out
    payload = json.loads(out[0])
    for cmd in payload["commands"]:
        assert "cmd_" in cmd["name"]


def test_server_cmd_meta_pagination() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="cmd_meta --page 1 --page_size 2")
    assert out
    payload = json.loads(out[0])
    assert "pagination" in payload
    pag = payload["pagination"]
    assert pag["page"] == 1
    assert pag["page_size"] == 2
    assert len(payload["commands"]) <= 2


def test_server_cmd_meta_tag_filter() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="cmd_meta --tag server")
    assert out
    payload = json.loads(out[0])
    for cmd in payload["commands"]:
        assert "server" in [t.lower() for t in cmd.get("tags", [])]


def test_server_exec_usage_without_path() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="exec")
    assert out
    # Bus validation or legacy handler returns error/usage
    assert any("usage" in line.lower() or "error" in line.lower() or "required" in line.lower() for line in out)


def test_server_cvar_read() -> None:
    server = _fake_server()
    con = build_server_console(server)
    out = con.execute_line(ctx=CommandContext(role="server", origin="test"), line="jump_height")
    assert out
    assert any("jump_height" in line for line in out)
