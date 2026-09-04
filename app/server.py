from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ui_faultlab.actions import Action
from ui_faultlab.environment import BrowserEnvironment


ROOT = Path(__file__).parent
STATIC = ROOT / "static"
ENV = BrowserEnvironment("create_event", 0, Path("work/server_screens"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send(200, json.dumps({"state": ENV.public_web_state(), "task": {"task_id": ENV.task_id, "instruction": ENV.instruction}}).encode(), "application/json")
            return
        file = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
        if file.is_file() and STATIC in file.resolve().parents:
            kinds = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
            self._send(200, file.read_bytes(), kinds.get(file.suffix, "application/octet-stream"))
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        global ENV
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size) or b"{}")
        path = urlparse(self.path).path
        if path == "/api/reset":
            ENV = BrowserEnvironment(payload.get("task_id", "create_event"), int(payload.get("seed", 0)), Path("work/server_screens"))
            ENV.reset()
        elif path == "/api/action":
            ENV.apply(Action.from_dict(payload))
        else:
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, json.dumps({"state": ENV.public_web_state(), "task": {"task_id": ENV.task_id, "instruction": ENV.instruction}}).encode(), "application/json")

    def log_message(self, format: str, *args) -> None:
        return


def serve(host: str, port: int, server_cls=ThreadingHTTPServer) -> None:
    server = server_cls((host, port), Handler)
    actual_port = getattr(server, "server_address", (host, port))[1]
    print(f"Mini Calendar: http://{host}:{actual_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
