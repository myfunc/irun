"""Tests for MCP server console_commands tool behavior."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from ivan.mcp_server import _control_meta, main


def test_control_meta_builds_line_with_prefix() -> None:
    with patch("ivan.mcp_server._control_exec") as mock_exec:
        mock_exec.return_value = ["[]"]
        _control_meta(host="127.0.0.1", port=7779, role="client", prefix="scene_")
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        assert "scene_" in call_args.kwargs["line"]
        assert call_args.kwargs["line"].startswith("cmd_meta")


def test_control_meta_builds_line_with_pagination() -> None:
    with patch("ivan.mcp_server._control_exec") as mock_exec:
        mock_exec.return_value = ["[]"]
        _control_meta(host="127.0.0.1", port=7779, role="client", page=2, page_size=10)
        mock_exec.assert_called_once()
        line = mock_exec.call_args.kwargs["line"]
        assert "--page 2" in line
        assert "--page_size 10" in line


def test_control_meta_builds_line_with_tag() -> None:
    with patch("ivan.mcp_server._control_exec") as mock_exec:
        mock_exec.return_value = ["[]"]
        _control_meta(host="127.0.0.1", port=7779, role="client", tag="mcp")
        mock_exec.assert_called_once()
        assert "--tag mcp" in mock_exec.call_args.kwargs["line"]


def test_control_meta_defaults_omit_page_params() -> None:
    with patch("ivan.mcp_server._control_exec") as mock_exec:
        mock_exec.return_value = ["[]"]
        _control_meta(host="127.0.0.1", port=7779, role="client")
        line = mock_exec.call_args.kwargs["line"]
        assert line == "cmd_meta"


def test_tools_list_console_commands_advertises_tag_page_page_size() -> None:
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    stdin = StringIO(json.dumps(req) + "\n")
    stdout = StringIO()
    with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
        main(argv=[])
    out = json.loads(stdout.getvalue())
    tools = out.get("result", {}).get("tools", [])
    cc = next((t for t in tools if t["name"] == "console_commands"), None)
    assert cc is not None
    props = cc["inputSchema"]["properties"]
    assert "tag" in props and props["tag"]["type"] == "string"
    assert "page" in props and props["page"]["type"] == "integer"
    assert "page_size" in props and props["page_size"]["type"] == "integer"
