"""Stub HTTP model server for unit testing Gemini and OpenAI clients.

CAPABILITIES:
  CAP-OUTSOURCING-STUB-SERVER: Local HTTP server replaying response scripts and recording requests. [tests: test_gemini_client, test_openai_client, test_acceptance_wo_1_0_10]
INPUTS AND OUTPUTS:
  Context manager yielding base URL and recorded requests list.
CONTRACTS: none.
INVARIANTS:
  - Serves local HTTP on port 0.
NOT IN SCOPE:
  - Real API proxying.
CHANGE LOG:
  2026-10-10 WO-1.0-10 created.
"""
from __future__ import annotations

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


class StubModelServer:

    def __init__(
        self,
        script: list[tuple[int, dict, str]],
        count: int = 50,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.script = deque(script)
        self.count = count
        self.clock = clock
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):

            def log_message(self, *args) -> None:
                return

            def _handle_req(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8") if length else ""
                now = outer.clock() if outer.clock else 0.0

                req_info = {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                    "at": now,
                }
                outer.requests.append(req_info)

                if self.path.endswith(":countTokens"):
                    status, headers, text = 200, {}, json.dumps({"totalTokens": outer.count})
                elif outer.script:
                    status, headers, text = outer.script.popleft()
                elif self.path.endswith("/v1beta/models") and self.command == "GET":
                    status, headers, text = 200, {}, json.dumps({"models": [{"name": "models/stub-model"}]})
                elif self.path.endswith("/models") and self.command == "GET":
                    status, headers, text = 200, {}, json.dumps({"data": [{"id": "stub-model"}]})
                else:
                    status, headers, text = 500, {}, json.dumps({"error": {"message": f"Unscripted request: {self.command} {self.path}"}})

                data = text.encode("utf-8")
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, str(v))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = _handle_req
            do_POST = _handle_req

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> tuple[str, list[dict]]:
        self.thread.start()
        return self.url, self.requests

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
