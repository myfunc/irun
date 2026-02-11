from __future__ import annotations

"""
Scope 04 MCP-oriented realtime command demo.

Run while IVAN client is running:
  python apps/ivan/tools/mcp_scope04_demo.py --port 7779
"""

import argparse
import json
import socket


def _exec_line(*, host: str, port: int, line: str) -> dict:
    req = {"line": line, "role": "client", "origin": "mcp-demo"}
    payload = (json.dumps(req, ensure_ascii=True) + "\n").encode("utf-8")
    with socket.create_connection((host, int(port)), timeout=1.5) as s:
        s.sendall(payload)
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    obj = json.loads(buf.decode("utf-8", errors="ignore").strip() or "{}")
    if not isinstance(obj, dict):
        return {"ok": False, "out": ["error: invalid response"]}
    return obj


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run Scope 04 command-bus demo over the console control bridge.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7779)
    args = ap.parse_args(argv)

    lines = [
        "cmd_meta --prefix scene_",
        "scene_list --page 1 --page_size 5",
        "scene_create box runtime_box_a",
        "scene_create box runtime_box_b",
        "scene_list --name runtime_box --page 1 --page_size 10",
        "scene_group demo_grp --targets runtime_box_a,runtime_box_b",
        "scene_group_transform demo_grp move 2 0 0 --relative true",
        "scene_inspect runtime_box_a",
        "world_fog_set --mode linear --start 80 --end 260 --color_r 0.45 --color_g 0.55 --color_b 0.7",
        "player_look_target --distance 256",
        "world_runtime",
    ]
    for line in lines:
        print(f"\n$ {line}")
        try:
            resp = _exec_line(host=args.host, port=int(args.port), line=line)
        except Exception as e:
            print(f"error: {e}")
            continue
        print(json.dumps(resp, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

