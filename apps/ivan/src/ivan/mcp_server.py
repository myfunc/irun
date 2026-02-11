from __future__ import annotations

"""
Minimal MCP (Model Context Protocol) stdio server for driving IVAN via console commands.

We implement a small JSON-RPC 2.0 subset:
- initialize
- ping
- tools/list
- tools/call

This is intentionally dependency-free (Python 3.9) and forwards `tools/call` to a
localhost ConsoleControlServer running inside the IVAN client/server process.
"""

import argparse
import json
import socket
import sys
from typing import Any


SERVER_NAME = "ivan-console"
SERVER_VERSION = "0.1.0"


def _send_json(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _error(*, req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": int(code), "message": str(message)}}


def _ok(*, req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _control_exec(*, host: str, port: int, line: str, role: str) -> list[str]:
    req = {"line": str(line), "role": str(role), "origin": "mcp"}
    payload = (json.dumps(req, ensure_ascii=True) + "\n").encode("utf-8")
    with socket.create_connection((str(host), int(port)), timeout=1.0) as s:
        s.sendall(payload)
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 5_000_000:
                break
    try:
        obj = json.loads(buf.decode("utf-8", errors="ignore").strip())
    except Exception:
        return ["error: invalid response from control server"]
    if not isinstance(obj, dict):
        return ["error: invalid response from control server"]
    out = obj.get("out")
    if isinstance(out, list):
        return [str(x) for x in out]
    return []


def _control_meta(*, host: str, port: int, role: str, prefix: str = "") -> list[str]:
    line = "cmd_meta"
    if str(prefix).strip():
        line = f"cmd_meta --prefix {prefix}"
    return _control_exec(host=host, port=port, line=line, role=role)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ivan-mcp", description="MCP stdio server for IVAN console control")
    ap.add_argument("--control-host", default="127.0.0.1", help="Host for IVAN ConsoleControlServer.")
    ap.add_argument("--control-port", type=int, default=7779, help="Port for IVAN ConsoleControlServer.")
    args = ap.parse_args(argv)

    protocol_version = "2024-11-05"

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except Exception:
            _send_json(_error(req_id=None, code=-32700, message="Parse error"))
            continue
        if not isinstance(req, dict):
            _send_json(_error(req_id=None, code=-32600, message="Invalid Request"))
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params")

        if not isinstance(method, str):
            _send_json(_error(req_id=req_id, code=-32600, message="Invalid Request"))
            continue

        if method == "initialize":
            if isinstance(params, dict) and isinstance(params.get("protocolVersion"), str):
                protocol_version = str(params["protocolVersion"])
            _send_json(
                _ok(
                    req_id=req_id,
                    result={
                        "protocolVersion": protocol_version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                )
            )
            continue

        if method == "ping":
            _send_json(_ok(req_id=req_id, result={}))
            continue

        if method == "tools/list":
            _send_json(
                _ok(
                    req_id=req_id,
                    result={
                        "tools": [
                            {
                                "name": "console_exec",
                                "title": "IVAN Console Exec",
                                "description": "Execute an IVAN console command line in the running process.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "line": {"type": "string", "description": "Console line to execute."},
                                        "role": {
                                            "type": "string",
                                            "description": 'Execution role hint: "client" or "server".',
                                            "default": "client",
                                        },
                                    },
                                    "required": ["line"],
                                },
                            },
                            {
                                "name": "console_commands",
                                "title": "IVAN Console Commands",
                                "description": "List discoverable IVAN console command metadata.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prefix": {
                                            "type": "string",
                                            "description": "Optional command name prefix filter.",
                                            "default": "",
                                        },
                                        "role": {
                                            "type": "string",
                                            "description": 'Execution role hint: "client" or "server".',
                                            "default": "client",
                                        },
                                    },
                                },
                            }
                        ]
                    },
                )
            )
            continue

        if method == "tools/call":
            if not isinstance(params, dict):
                _send_json(_error(req_id=req_id, code=-32602, message="Invalid params"))
                continue
            name = params.get("name")
            arguments = params.get("arguments")
            if name not in ("console_exec", "console_commands") or not isinstance(arguments, dict):
                _send_json(_error(req_id=req_id, code=-32602, message="Invalid tool call"))
                continue
            role = arguments.get("role") or "client"
            try:
                if name == "console_exec":
                    line = arguments.get("line")
                    if not isinstance(line, str):
                        _send_json(_error(req_id=req_id, code=-32602, message="line must be a string"))
                        continue
                    out_lines = _control_exec(
                        host=str(args.control_host),
                        port=int(args.control_port),
                        line=line,
                        role=str(role),
                    )
                else:
                    out_lines = _control_meta(
                        host=str(args.control_host),
                        port=int(args.control_port),
                        role=str(role),
                        prefix=str(arguments.get("prefix") or ""),
                    )
            except Exception as e:
                _send_json(_error(req_id=req_id, code=-32000, message=f"control error: {e}"))
                continue
            _send_json(
                _ok(
                    req_id=req_id,
                    result={
                        "content": [{"type": "text", "text": "\n".join(out_lines)}],
                    },
                )
            )
            continue

        # Ignore notifications without id; error for unknown request methods.
        if req_id is None:
            continue
        _send_json(_error(req_id=req_id, code=-32601, message=f"Method not found: {method}"))


if __name__ == "__main__":
    main()
