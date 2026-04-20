"""Node annotations persistence."""

import json


def handle_annotations_get(handler):
    path = handler.data_dir / "annotations.json"
    if not path.exists():
        handler.send_response(404)
        handler.end_headers()
        return
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def handle_annotations_post(handler):
    data = handler._read_json_body()
    if data is None:
        return
    (handler.data_dir / "annotations.json").write_text(
        json.dumps(data, indent=2))
    handler._json_response({"ok": True})
