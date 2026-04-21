from __future__ import annotations

import http.server
import json
import subprocess
from pathlib import Path

from archview import annotations, diff


class ArchviewHandler(http.server.BaseHTTPRequestHandler):
    static_dir: Path
    data_dir: Path
    project_dir: Path
    ignore_file: Path | None = None
    interval: int = 10

    MIME = {
        ".js": "application/javascript",
        ".html": "text/html; charset=utf-8",
        ".json": "application/json",
        ".css": "text/css",
    }

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" and "interval" not in self.path:
            self.send_response(302)
            self.send_header("Location", f"/live.html?interval={self.interval}")
            self.end_headers()
            return
        elif path in ("/", "/live.html"):
            self._serve_file(self.static_dir / "live.html", "text/html; charset=utf-8")
        elif path == "/graph.json":
            self._serve_file(self.data_dir / "graph.json", "application/json")
        elif path == "/positions.json":
            self._serve_file(self.data_dir / "positions.json", "application/json")
        elif path == "/annotations.json":
            annotations.handle_annotations_get(self)
        elif path == "/refs":
            diff.handle_refs(self)
        elif path == "/diff":
            diff.handle_diff(self)
        else:
            candidate = (self.static_dir / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(self.static_dir.resolve())
            except ValueError:
                self.send_response(403)
                self.end_headers()
                return
            if candidate.exists() and candidate.is_file():
                ext = candidate.suffix.lower()
                mime = self.MIME.get(ext, "application/octet-stream")
                self._serve_file(candidate, mime)
            else:
                self._not_found()

    def do_POST(self):
        if self.path == "/open":
            self._handle_open()
        elif self.path == "/save":
            self._handle_save()
        elif self.path == "/annotations":
            annotations.handle_annotations_post(self)
        else:
            self._not_found()

    MAX_BODY_SIZE = 2 * 1024 * 1024

    def _not_found(self):
        self.send_response(404)
        self.end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > self.MAX_BODY_SIZE:
            self._json_response({"ok": False, "error": "payload too large"}, 413)
            return None
        return json.loads(self.rfile.read(length))

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_open(self):
        body = self._read_json_body()
        if body is None:
            return
        filepath = body.get("file", "")
        if filepath:
            # resolve(strict=True) follows symlinks and raises on missing files,
            # so the subsequent relative_to check covers both traversal and
            # symlink-escape attempts in one step.
            try:
                abs_path = (self.project_dir / filepath).resolve(strict=True)
                abs_path.relative_to(self.project_dir.resolve(strict=True))
            except (ValueError, OSError):
                self._json_response({"ok": False, "error": "path outside project"}, 403)
                return
            try:
                subprocess.Popen(["code", "--goto", str(abs_path)])
            except FileNotFoundError:
                pass
        self._json_response({"ok": True})

    def _handle_save(self):
        positions = self._read_json_body()
        if positions is None:
            return
        (self.data_dir / "positions.json").write_text(json.dumps(positions, indent=2))
        self._json_response({"ok": True})
        print("  Saved positions")

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def make_server(
    host: str,
    port: int,
    static_dir: Path,
    data_dir: Path,
    project_dir: Path,
    interval: int = 10,
    ignore_file: Path | None = None,
):
    ArchviewHandler.static_dir = Path(static_dir)
    ArchviewHandler.data_dir = Path(data_dir)
    ArchviewHandler.project_dir = Path(project_dir)
    ArchviewHandler.ignore_file = ignore_file
    ArchviewHandler.interval = interval
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    return http.server.ThreadingHTTPServer((host, port), ArchviewHandler)
