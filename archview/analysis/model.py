"""Graph model: language-neutral symbol tags and node-role classification."""

from __future__ import annotations

# Symbol type tags used in node symbols and edge labels (language-neutral)
SYM_FUNC = "fn"
SYM_CLASS = "cls"
SYM_VAR = "var"


def classify_node(node_id: str, importers: set, imported: set) -> str:
    is_importer = node_id in importers
    is_imported = node_id in imported
    if is_importer and not is_imported:
        return "entry"
    if is_imported and not is_importer:
        return "leaf"
    if is_importer and is_imported:
        return "intermediate"
    return "isolated"


def find_parent(node_id: str, all_containers: set[str]) -> str:
    parts = node_id.split(".")
    if len(parts) > 1:
        candidate = ".".join(parts[:-1])
        if candidate in all_containers:
            return candidate
    return ""
