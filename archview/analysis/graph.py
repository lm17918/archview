"""Orchestrate analysis into a dependency graph and write it as Cytoscape JSON."""

from __future__ import annotations

import json
from pathlib import Path

from archview.analysis.collect import (
    _build_module_index,
    _collect_files_by_ext,
    collect_py_files,
)
from archview.analysis.elements import build_elements
from archview.analysis.python.edges import _collect_imports
from archview.analysis.python.parse import _parse_modules, _parse_shell_scripts
from archview.analysis.python.refs import _collect_file_refs, _resolve_shell_refs

# Re-exported for tests and callers
__all__ = ["collect_py_files", "generate_graph", "generate_graph_json"]


def generate_graph_json(project_dir: Path, ignore_file: Path | None) -> list[dict]:
    project_dir = Path(project_dir)

    py_files = collect_py_files(project_dir, ignore_file)
    sh_files = _collect_files_by_ext(project_dir, ignore_file, ".sh")
    data_files = []
    for ext in (".yaml", ".yml", ".json"):
        data_files += _collect_files_by_ext(project_dir, ignore_file, ext)

    py_modules, py_rel = _build_module_index(project_dir, py_files, ".py")
    sh_modules, sh_rel = _build_module_index(project_dir, sh_files, ".sh")
    data_modules: dict[str, Path] = {}
    data_rel: dict[str, str] = {}
    for ext in (".yaml", ".yml", ".json"):
        dm, dr = _build_module_index(
            project_dir, [f for f in data_files if f.endswith(ext)], ext, keep_ext=True
        )
        data_modules.update(dm)
        data_rel.update(dr)

    # No collisions: data files keep their extension in the id
    modules = {**data_modules, **sh_modules, **py_modules}
    module_rel = {**data_rel, **sh_rel, **py_rel}

    py_docs, py_syms, parsed, parse_errors = _parse_modules(py_modules)
    sh_docs, sh_syms, shell_refs = _parse_shell_scripts(sh_modules)

    docstrings = {**py_docs, **sh_docs}
    module_symbols = {**py_syms, **sh_syms}

    # Edges: Python imports + file refs in Python strings + shell references
    edge_names = _collect_imports(parsed, py_modules, module_symbols)
    for key, syms in _collect_file_refs(parsed, module_rel).items():
        edge_names.setdefault(key, {}).update(syms)
    for key, syms in _resolve_shell_refs(shell_refs, module_rel).items():
        edge_names.setdefault(key, {}).update(syms)

    all_nodes = sorted(modules.keys())
    all_nodes_set = set(all_nodes)
    importers = {src for src, _ in edge_names}
    imported = {tgt for _, tgt in edge_names}

    # Synthetic folder nodes for every ancestor directory without __init__.py.
    # Walk all ancestors, not just the immediate parent, so dirs holding only
    # subdirs (e.g. examples/) still get a container and children stay nested.
    folder_ids: set[str] = set()
    for node in all_nodes:
        parts = node.split(".")
        for i in range(1, len(parts)):
            # leading-dot hidden files (e.g. .eslintrc.json) produce an empty
            # candidate; skip to avoid emitting an element with id ""
            candidate = ".".join(parts[:i])
            if candidate and candidate not in all_nodes_set:
                folder_ids.add(candidate)

    all_containers = all_nodes_set | folder_ids

    return build_elements(
        all_nodes,
        folder_ids,
        all_containers,
        edge_names,
        importers,
        imported,
        docstrings,
        module_symbols,
        module_rel,
        parse_errors,
    )


def generate_graph(
    project_dir: Path, ignore_file: Path | None, output_path: Path
) -> None:
    elements = generate_graph_json(project_dir, ignore_file)
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(elements))
    tmp.rename(output_path)
