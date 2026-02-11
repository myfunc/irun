from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass

from ivan.console.core import CommandContext, Console


@dataclass(frozen=True)
class ConsoleExecRequest:
    line: str
    role: str = "client"
    origin: str = "mcp"


class ConsoleControlServer:
    """
    Tiny localhost JSON-lines server to execute console lines in a running process.

    This is the "bridge" that an external MCP stdio server can talk to.
    Protocol (one JSON object per line, request/response):
      request:  {"line":"connect 127.0.0.1 7777","role":"client","origin":"mcp"}
      response: {"ok":true,"out":["..."]}
    """

    def __init__(
        self,
        *,
        console: Console,
        host: str = "127.0.0.1",
        port: int = 7779,
        execute_request=None,
    ) -> None:
        self.console = console
        self.host = str(host)
        self.port = int(port)
        self._execute_request = execute_request
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(8)
        s.settimeout(0.25)
        self._sock = s
        self._thread = threading.Thread(target=self._run, daemon=True, name="ivan-console-control")
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                pass
        self._thread = None

    def _handle_client(self, cs: socket.socket) -> None:
        buf = b""
        cs.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data = cs.recv(4096)
            except socket.timeout:
                continue
            except Exception:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    obj = json.loads(line.decode("utf-8", errors="ignore").strip())
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                line_s = str(obj.get("line") or "")
                role = str(obj.get("role") or "client")
                origin = str(obj.get("origin") or "mcp")
                ctx = CommandContext(role=role, origin=origin)
                if callable(self._execute_request):
                    detail = self._execute_request(ctx=ctx, line=line_s)
                else:
                    detail = self.console.execute_line_detailed(ctx=ctx, line=line_s)
                executions = []
                for it in getattr(detail, "executions", []):
                    executions.append(
                        {
                            "name": str(it.name),
                            "ok": bool(it.ok),
                            "elapsed_ms": float(it.elapsed_ms),
                            "error_code": str(it.error_code or ""),
                            "data": dict(it.data or {}),
                        }
                    )
                resp = {
                    "ok": bool(getattr(detail, "ok", True)),
                    "command": str(line_s),
                    "out": list(getattr(detail, "out", [])),
                    "elapsed_ms": float(getattr(detail, "elapsed_ms", 0.0)),
                    "executions": executions,
                }
                try:
                    cs.sendall((json.dumps(resp, ensure_ascii=True) + "\n").encode("utf-8"))
                except Exception:
                    return

    def _run(self) -> None:
        if self._sock is None:
            return
        while not self._stop.is_set():
            try:
                cs, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                self._handle_client(cs)
            finally:
                try:
                    cs.close()
                except Exception:
                    pass
