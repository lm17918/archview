"""Tests for archview graph generation and server."""
import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from archview.graph import collect_py_files, generate_graph
from archview.server import make_server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def proj(tmp_path):
    """Minimal project: one top-level script importing two utilities."""
    (tmp_path / "main.py").write_text('"""Main entry."""\nimport utils.helper\nimport utils.math\n')
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "__init__.py").write_text("")
    (tmp_path / "utils" / "helper.py").write_text('"""Helper utility."""\n')
    (tmp_path / "utils" / "math.py").write_text('"""Math utility."""\n')
    return tmp_path


def run(project_dir, tmp_path, ignore_file=None):
    data_dir = tmp_path / ".archview"
    data_dir.mkdir(exist_ok=True)
    graph_path = data_dir / "graph.json"
    generate_graph(project_dir, ignore_file, graph_path)
    elements = json.loads(graph_path.read_text())
    nodes = {e["data"]["id"]: e["data"] for e in elements if "source" not in e["data"]}
    edges = [(e["data"]["source"], e["data"]["target"]) for e in elements if "source" in e["data"]]
    return nodes, edges


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def test_collects_all_py_files(proj, tmp_path):
    files = collect_py_files(proj, None)
    names = {Path(f).name for f in files}
    assert names == {"main.py", "__init__.py", "helper.py", "math.py"}


def test_ignore_by_directory_name(proj, tmp_path):
    ignore = proj / ".analyzeignore"
    ignore.write_text("utils\n")
    files = collect_py_files(proj, ignore)
    assert all("utils" not in f for f in files)
    assert any("main.py" in f for f in files)


def test_ignore_by_stem_matches_py_file(proj, tmp_path):
    """Pattern 'main' should match 'main.py' (stem matching)."""
    ignore = proj / ".analyzeignore"
    ignore.write_text("main\n")
    files = collect_py_files(proj, ignore)
    assert not any("main.py" in f for f in files)


def test_ignore_stem_does_not_match_prefix(proj, tmp_path):
    """Pattern 'main' must NOT match 'main_extra.py' — only exact stem."""
    (proj / "main_extra.py").write_text('"""Extra."""\n')
    ignore = proj / ".analyzeignore"
    ignore.write_text("main\n")
    files = collect_py_files(proj, ignore)
    assert any("main_extra.py" in f for f in files)


def test_ignore_glob_pattern(proj, tmp_path):
    """Glob patterns like 'utils*' should work."""
    ignore = proj / ".analyzeignore"
    ignore.write_text("utils*\n")
    files = collect_py_files(proj, ignore)
    assert not any("utils" in f for f in files)


def test_ignore_comments_and_blank_lines(proj, tmp_path):
    ignore = proj / ".analyzeignore"
    ignore.write_text("# this is a comment\n\nutils\n")
    files = collect_py_files(proj, ignore)
    assert not any("utils" in f for f in files)
    assert any("main.py" in f for f in files)


def test_no_ignore_file(proj, tmp_path):
    files = collect_py_files(proj, None)
    assert len(files) == 4


# ---------------------------------------------------------------------------
# Node types and colors
# ---------------------------------------------------------------------------

COLORS = {
    "entry":        "#6ee7b7",
    "intermediate": "#93c5fd",
    "leaf":         "#fca5a5",
    "isolated":     "#3a3a46",
}
TEXT_COLORS = {
    "entry":        "#0a2a1a",
    "intermediate": "#0a1a2e",
    "leaf":         "#2e0a0a",
    "isolated":     "#e2e2e8",
}


def test_entry_node_type(proj, tmp_path):
    """main.py imports others but nothing imports it → entry."""
    nodes, _ = run(proj, tmp_path)
    assert nodes["main"]["type"] == "entry"


def test_leaf_node_type(proj, tmp_path):
    """helper/math are imported but import nothing → leaf."""
    nodes, _ = run(proj, tmp_path)
    assert nodes["utils.helper"]["type"] == "leaf"
    assert nodes["utils.math"]["type"] == "leaf"


def test_intermediate_node_type(proj, tmp_path):
    (proj / "pipeline.py").write_text('"""Pipeline."""\nimport main\n')
    nodes, _ = run(proj, tmp_path)
    assert nodes["main"]["type"] == "intermediate"


def test_isolated_node_type(proj, tmp_path):
    (proj / "standalone.py").write_text('"""Standalone."""\n')
    nodes, _ = run(proj, tmp_path)
    assert nodes["standalone"]["type"] == "isolated"


def test_node_colors_match_type(proj, tmp_path):
    (proj / "standalone.py").write_text("")
    nodes, _ = run(proj, tmp_path)
    for node in nodes.values():
        assert node["color"] == COLORS[node["type"]], f"{node['id']}: wrong color"


def test_text_color_for_isolated_is_light(proj, tmp_path):
    """Isolated nodes have dark background — text must be light."""
    (proj / "standalone.py").write_text("")
    nodes, _ = run(proj, tmp_path)
    assert nodes["standalone"]["textColor"] == TEXT_COLORS["isolated"]


def test_text_color_for_entry_is_dark(proj, tmp_path):
    nodes, _ = run(proj, tmp_path)
    assert nodes["main"]["textColor"] == TEXT_COLORS["entry"]


# ---------------------------------------------------------------------------
# Edge direction — arrows point FROM dependency TO importer
# ---------------------------------------------------------------------------

def test_edge_points_from_dependency_to_importer(proj, tmp_path):
    """main imports helper → edge should be helper → main (dep feeds importer)."""
    nodes, edges = run(proj, tmp_path)
    assert ("utils.helper", "main") in edges or ("utils.math", "main") in edges


def test_no_edge_pointing_from_importer_to_dep(proj, tmp_path):
    """Old direction (main → utils.helper) must NOT appear."""
    nodes, edges = run(proj, tmp_path)
    assert ("main", "utils.helper") not in edges
    assert ("main", "utils.math") not in edges


# ---------------------------------------------------------------------------
# Docstrings
# ---------------------------------------------------------------------------

def test_docstring_extraction(proj, tmp_path):
    nodes, _ = run(proj, tmp_path)
    assert nodes["main"]["docstring"] == "Main entry."
    assert nodes["utils.helper"]["docstring"] == "Helper utility."


def test_no_docstring_gives_empty_string(proj, tmp_path):
    (proj / "nodoc.py").write_text("x = 1\n")
    nodes, _ = run(proj, tmp_path)
    assert nodes["nodoc"]["docstring"] == ""


def test_long_docstring_is_truncated(proj, tmp_path):
    long_doc = "A" * 100
    (proj / "verbose.py").write_text(f'"""{long_doc}"""\n')
    nodes, _ = run(proj, tmp_path)
    assert len(nodes["verbose"]["docstring"]) <= 80


# ---------------------------------------------------------------------------
# Graph structure
# ---------------------------------------------------------------------------

def test_init_file_collapsed_to_package(proj, tmp_path):
    """utils/__init__.py should appear as 'utils', not 'utils.__init__'."""
    nodes, _ = run(proj, tmp_path)
    assert "utils" in nodes
    assert "utils.__init__" not in nodes


def test_no_self_edges(proj, tmp_path):
    _, edges = run(proj, tmp_path)
    assert all(src != tgt for src, tgt in edges)


def test_no_duplicate_edges(proj, tmp_path):
    _, edges = run(proj, tmp_path)
    assert len(edges) == len(set(edges))


def test_ignored_file_has_no_edges(proj, tmp_path):
    ignore = proj / ".analyzeignore"
    ignore.write_text("helper\n")
    nodes, edges = run(proj, tmp_path, ignore)
    assert "utils.helper" not in nodes
    assert all("utils.helper" not in (s, t) for s, t in edges)


# ---------------------------------------------------------------------------
# Folder (synthetic compound) nodes
# ---------------------------------------------------------------------------

def test_folder_label_has_no_slash(tmp_path):
    """Synthetic folder labels must not contain trailing '/'."""
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "mod.py").write_text('"""Deep."""\n')
    nodes, _ = run(tmp_path, tmp_path)
    assert "deep" in nodes
    assert "/" not in nodes["deep"]["label"]


def test_folder_node_is_marked_as_folder(tmp_path):
    """Synthetic folder nodes must have is_folder=True."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("")
    nodes, _ = run(tmp_path, tmp_path)
    assert nodes["pkg"]["is_folder"] is True


def test_folder_node_is_parent_of_children(tmp_path):
    """Children inside a folder must have the folder as parent."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("")
    (tmp_path / "pkg" / "b.py").write_text("")
    nodes, _ = run(tmp_path, tmp_path)
    assert nodes["pkg.a"]["parent"] == "pkg"
    assert nodes["pkg.b"]["parent"] == "pkg"


def test_package_with_init_is_not_folder(tmp_path):
    """A package with __init__.py is a real module, not a synthetic folder."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "a.py").write_text("")
    nodes, _ = run(tmp_path, tmp_path)
    assert "pkg" in nodes
    assert not nodes["pkg"].get("is_folder")


# ---------------------------------------------------------------------------
# Edge labels carry imported symbols
# ---------------------------------------------------------------------------

def test_edge_label_contains_imported_names(proj, tmp_path):
    """Edge label must list the symbols imported across the dependency."""
    (proj / "utils" / "helper.py").write_text('"""Helper."""\ndef do_stuff(): pass\nclass Widget: pass\n')
    (proj / "main.py").write_text('"""Main."""\nfrom utils.helper import do_stuff, Widget\n')
    data_dir = tmp_path / ".archview"
    data_dir.mkdir(exist_ok=True)
    graph_path = data_dir / "graph.json"
    generate_graph(proj, None, graph_path)
    elements = json.loads(graph_path.read_text())
    edge_labels = {
        (e["data"]["source"], e["data"]["target"]): e["data"]["label"]
        for e in elements if "source" in e["data"]
    }
    label = edge_labels.get(("utils.helper", "main"), "")
    assert "do_stuff" in label
    assert "Widget" in label


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

def test_analysis_completes_quickly(tmp_path):
    """100-file project must analyze in under 2 seconds."""
    for i in range(100):
        f = tmp_path / f"mod_{i}.py"
        f.write_text(f'"""Module {i}."""\nimport mod_{(i+1) % 100}\n')
    graph_path = tmp_path / "graph.json"
    t0 = time.time()
    generate_graph(tmp_path, None, graph_path)
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"Analysis took {elapsed:.2f}s (limit: 2s)"


# ---------------------------------------------------------------------------
# Server endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    static_dir = Path(__file__).parent.parent / "archview" / "static"
    data_dir = tmp_path / ".archview"
    data_dir.mkdir()
    (data_dir / "graph.json").write_text('[{"data":{"id":"a","label":"a","color":"#fff","textColor":"#000","type":"isolated","docstring":"","group":""}}]')

    srv = make_server("127.0.0.1", 19091, static_dir, data_dir, tmp_path)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def test_server_serves_html(server):
    resp = urllib.request.urlopen("http://127.0.0.1:19091/")
    assert resp.status == 200
    assert b"archview" in resp.read()


def test_server_serves_graph_json(server):
    resp = urllib.request.urlopen("http://127.0.0.1:19091/graph.json")
    assert resp.status == 200
    data = json.loads(resp.read())
    assert isinstance(data, list)


def test_server_serves_js_files(server):
    for filename in ("cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"):
        resp = urllib.request.urlopen(f"http://127.0.0.1:19091/{filename}")
        assert resp.status == 200, f"{filename} not served"


def test_server_404_for_unknown(server):
    try:
        urllib.request.urlopen("http://127.0.0.1:19091/nonexistent.txt")
        assert False, "Should have raised"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_server_handles_concurrent_requests(server):
    """ThreadingHTTPServer must handle parallel requests without blocking."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def fetch(url):
        resp = urllib.request.urlopen(url)
        return resp.status

    urls = [f"http://127.0.0.1:19091/{f}" for f in
            ("", "graph.json", "cytoscape.min.js", "dagre.min.js")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, u) for u in urls]
        results = [f.result(timeout=5) for f in as_completed(futures)]
    assert all(s == 200 for s in results)


def test_server_save_and_positions(server, tmp_path):
    positions = {"a": {"x": 100, "y": 200}}
    data = json.dumps(positions).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:19091/save",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    result = json.loads(resp.read())
    assert result["ok"] is True

    # positions.json should now be readable
    resp2 = urllib.request.urlopen("http://127.0.0.1:19091/positions.json")
    saved = json.loads(resp2.read())
    assert saved["a"]["x"] == 100
