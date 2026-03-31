import http.server
import json
import subprocess
from pathlib import Path


class ArchviewHandler(http.server.BaseHTTPRequestHandler):
    # Configured before server starts
    static_dir: Path
    data_dir: Path
    project_dir: Path

    MIME = {
        ".js":   "application/javascript",
        ".html": "text/html; charset=utf-8",
        ".json": "application/json",
        ".css":  "text/css",
    }

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/live.html"):
            self._serve_file(self.static_dir / "live.html", "text/html; charset=utf-8")
        elif path == "/graph.json":
            self._serve_file(self.data_dir / "graph.json", "application/json")
        elif path == "/positions.json":
            self._serve_file(self.data_dir / "positions.json", "application/json")
        else:
            # serve any file from static_dir (JS, CSS, etc.)
            candidate = self.static_dir / path.lstrip("/")
            if candidate.exists() and candidate.is_file():
                ext = candidate.suffix.lower()
                mime = self.MIME.get(ext, "application/octet-stream")
                self._serve_file(candidate, mime)
            else:
                self.send_response(404)
                self.end_headers()

    def do_POST(self):
        handlers = {"/open": self._handle_open, "/save": self._handle_save}
        handler = handlers.get(self.path)
        if handler:
            handler()
        else:
            self.send_response(404)
            self.end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_open(self):
        body = self._read_json_body()
        filepath = body.get("file", "")
        if filepath:
            abs_path = self.project_dir / filepath
            if abs_path.exists():
                subprocess.Popen(["code", "--goto", str(abs_path)])
        self._json_response({"ok": True})

    def _handle_save(self):
        positions = self._read_json_body()
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


def make_server(host: str, port: int, static_dir: Path, data_dir: Path, project_dir: Path):
    ArchviewHandler.static_dir = Path(static_dir)
    ArchviewHandler.data_dir = Path(data_dir)
    ArchviewHandler.project_dir = Path(project_dir)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    return http.server.ThreadingHTTPServer((host, port), ArchviewHandler)
