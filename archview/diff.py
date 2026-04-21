"""Diff view: compare current graph against a git ref."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from archview.graph import generate_graph_json

_diff_lock = threading.Lock()


def handle_refs(handler):
    handler._json_response(_list_refs(handler.project_dir))


def handle_diff(handler):
    qs = parse_qs(urlparse(handler.path).query)
    ref = qs.get("ref", [None])[0]
    if not ref:
        handler._json_response({"error": "missing ref param"}, 400)
        return

    if not _diff_lock.acquire(blocking=False):
        handler._json_response({"error": "diff already running"}, 429)
        return
    try:
        old = _generate_old_graph(handler.project_dir, ref, handler.ignore_file)
        cur = generate_graph_json(handler.project_dir, handler.ignore_file)
        handler._json_response(_compute_diff(cur, old, ref))
    except subprocess.CalledProcessError:
        handler._json_response({"error": f"invalid ref: {ref}"}, 400)
    finally:
        _diff_lock.release()


def _list_refs(project_dir: Path) -> dict:
    project_dir = Path(project_dir)
    result: dict[str, list] = {"commits": [], "branches": [], "tags": []}

    try:
        log = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in log.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split(None, 1)
            result["commits"].append(
                {
                    "hash": parts[0],
                    "message": parts[1] if len(parts) > 1 else "",
                }
            )
    except subprocess.CalledProcessError:
        pass

    try:
        branches = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        result["branches"] = [
            b.strip() for b in branches.stdout.strip().splitlines() if b.strip()
        ]
    except subprocess.CalledProcessError:
        pass

    try:
        tags = subprocess.run(
            ["git", "tag"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        result["tags"] = [
            t.strip() for t in tags.stdout.strip().splitlines() if t.strip()
        ]
    except subprocess.CalledProcessError:
        pass

    return result


def _generate_old_graph(
    project_dir: Path, ref: str, ignore_file: Path | None
) -> list[dict]:
    project_dir = Path(project_dir)
    subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    tmpdir = tempfile.mkdtemp(prefix="archview_diff_")
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", tmpdir, ref],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return generate_graph_json(Path(tmpdir), ignore_file)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", tmpdir],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(tmpdir, ignore_errors=True)


def _element_fingerprint(el: dict) -> str:
    d = el["data"]
    if "source" in d:
        return f"{d.get('source')}|{d.get('target')}|{d.get('label', '')}"
    return f"{d.get('type', '')}|{d.get('symbols', '')}" f"|{d.get('docstring', '')}"


def _compute_diff(current: list[dict], old: list[dict], ref: str) -> dict:
    def index(elements):
        nodes, edges = {}, {}
        for el in elements:
            eid = el["data"]["id"]
            if "source" in el["data"]:
                edges[eid] = el
            else:
                nodes[eid] = el
        return nodes, edges

    cur_nodes, cur_edges = index(current)
    old_nodes, old_edges = index(old)

    added_nodes = sorted(set(cur_nodes) - set(old_nodes))
    removed_nodes = sorted(set(old_nodes) - set(cur_nodes))
    added_edges = sorted(set(cur_edges) - set(old_edges))
    removed_edges = sorted(set(old_edges) - set(cur_edges))

    modified_nodes = []
    for nid in sorted(set(cur_nodes) & set(old_nodes)):
        if _element_fingerprint(cur_nodes[nid]) != _element_fingerprint(old_nodes[nid]):
            modified_nodes.append(nid)

    modified_edges = []
    for eid in sorted(set(cur_edges) & set(old_edges)):
        if _element_fingerprint(cur_edges[eid]) != _element_fingerprint(old_edges[eid]):
            modified_edges.append(eid)

    removed_elements = []
    for nid in removed_nodes:
        el = old_nodes[nid]
        if not el["data"].get("is_folder"):
            removed_elements.append(el)
    for eid in removed_edges:
        removed_elements.append(old_edges[eid])

    return {
        "ref": ref,
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "modified_nodes": modified_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "modified_edges": modified_edges,
        "removed_elements": removed_elements,
    }
