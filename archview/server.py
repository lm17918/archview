import http.server
import json
import subprocess
import xml.etree.ElementTree as ET
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

        elements = json.loads((self.data_dir / "graph.json").read_text())
        drawio_path = self.project_dir / "project_analysis_positioned.drawio"
        self._generate_drawio(elements, positions, drawio_path)

        self._json_response({"ok": True, "drawio": drawio_path.name})
        print(f"  Saved positions + {drawio_path}")

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

    def _generate_drawio(self, elements, positions, path: Path):
        nodes = [e for e in elements if "source" not in e["data"]]
        edges = [e for e in elements if "source" in e["data"]]

        root = ET.Element("mxfile")
        diagram = ET.SubElement(root, "diagram", name="Architecture", id="arch")
        model = ET.SubElement(diagram, "mxGraphModel",
            dx="1000", dy="600", grid="1", gridSize="10",
            guides="1", tooltips="1", connect="1", arrows="1",
            fold="1", page="0", pageScale="1", pageWidth="1600", pageHeight="900")
        root_cell = ET.SubElement(model, "root")
        ET.SubElement(root_cell, "mxCell", id="0")
        ET.SubElement(root_cell, "mxCell", id="1", parent="0")

        cell_id = 2
        id_map = {}

        for node in nodes:
            d = node["data"]
            nid = str(cell_id)
            id_map[d["id"]] = nid
            cell_id += 1

            color = d.get("color", "#e8e8e8")
            label = d.get("label", d["id"])
            docstring = d.get("docstring", "")

            if docstring:
                value = (f'<b>{label}</b><br/>'
                         f'<font style="font-size:11px;" color="#555555"><i>{docstring}</i></font>')
            else:
                value = f"<b>{label}</b>"

            style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={color};"
                     f"strokeColor=#666666;fontFamily=Helvetica;fontSize=13;")

            pos = positions.get(d["id"], {"x": 100, "y": 100})
            w = max(len(label) * 9 + 24, 120)
            h = 40 if not docstring else 58

            cell = ET.SubElement(root_cell, "mxCell",
                id=nid, value=value, style=style, vertex="1", parent="1")
            geom = ET.SubElement(cell, "mxGeometry",
                x=str(round(pos["x"] - w / 2)),
                y=str(round(pos["y"] - h / 2)),
                width=str(w), height=str(h))
            geom.set("as", "geometry")

        for edge in edges:
            d = edge["data"]
            eid = str(cell_id)
            cell_id += 1
            src = id_map.get(d["source"], "")
            tgt = id_map.get(d["target"], "")
            if src and tgt:
                style = "edgeStyle=orthogonalEdgeStyle;curved=1;strokeColor=#666666;"
                ET.SubElement(root_cell, "mxCell",
                    id=eid, style=style, edge="1", parent="1",
                    source=src, target=tgt)

        path.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(path, xml_declaration=True, encoding="UTF-8")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def make_server(host: str, port: int, static_dir: Path, data_dir: Path, project_dir: Path):
    ArchviewHandler.static_dir = Path(static_dir)
    ArchviewHandler.data_dir = Path(data_dir)
    ArchviewHandler.project_dir = Path(project_dir)
    return http.server.ThreadingHTTPServer((host, port), ArchviewHandler)
