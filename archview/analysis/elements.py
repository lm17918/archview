"""Assemble the Cytoscape elements list (folders, nodes, edges) from analysis."""

from __future__ import annotations

from pathlib import Path

from archview.analysis.model import SYM_CLASS, SYM_FUNC, classify_node, find_parent


def build_elements(
    all_nodes,
    folder_ids,
    all_containers,
    edge_names,
    importers,
    imported,
    docstrings,
    module_symbols,
    module_rel,
    parse_errors=None,
):
    """Assemble the Cytoscape elements list (nodes + edges)."""
    parse_errors = parse_errors or {}
    elements = []

    # Folder (synthetic compound) nodes — emitted first so children can reference them
    for folder in sorted(folder_ids):
        elements.append(
            {
                "data": {
                    "id": folder,
                    "label": folder.split(".")[-1],
                    "is_folder": True,
                    "parent": find_parent(folder, all_containers),
                    "docstring": "",
                    "type": "folder",
                    "group": "",
                    "filepath": "",
                    "symbols": "",
                }
            }
        )

    for node in all_nodes:
        rel = module_rel.get(node, "")
        raw_name = Path(rel).name if rel else node.split(".")[-1]
        filename = node.split(".")[-1] if raw_name == "__init__.py" else raw_name
        if node in parse_errors:
            label = "⚠ " + filename
            docstring = parse_errors[node]
            ntype = "error"
            symbols = ""
        else:
            ntype = classify_node(node, importers, imported)
            label = filename
            docstring = docstrings.get(node, "")
            symbols = "\n".join(
                f"{sym} {name}"
                for name, sym in sorted(module_symbols.get(node, {}).items())
                if sym in (SYM_FUNC, SYM_CLASS)
            )
        elements.append(
            {
                "data": {
                    "id": node,
                    "label": label,
                    "docstring": docstring,
                    "type": ntype,
                    "group": node.split(".")[0] if "." in node else "",
                    "filepath": module_rel.get(node, ""),
                    "parent": find_parent(node, all_containers),
                    "symbols": symbols,
                }
            }
        )

    # Edges — arrow points FROM dependency TO importer
    for src, tgt in sorted(edge_names.keys()):
        name_syms = edge_names[(src, tgt)]
        label = "\n".join(f"{sym} {name}" for name, sym in sorted(name_syms.items()))
        elements.append(
            {
                "data": {
                    "id": f"{src}->{tgt}",
                    "source": tgt,
                    "target": src,
                    "label": label,
                }
            }
        )

    return elements
