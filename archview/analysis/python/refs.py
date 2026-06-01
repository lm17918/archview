"""Find references to data/shell files inside Python and shell sources."""

from __future__ import annotations

import ast
import re
from pathlib import Path, PurePosixPath

from archview.analysis.model import SYM_VAR


def _resolve_shell_refs(shell_refs, module_rel):
    rel_to_mod = {rel: mod for mod, rel in module_rel.items()}
    name_to_mod = {Path(rel).name: mod for mod, rel in module_rel.items()}

    edge_names: dict[tuple[str, str], dict[str, str]] = {}
    for mod, refs in shell_refs.items():
        mod_dir = str(PurePosixPath(module_rel.get(mod, "")).parent)
        for ref in refs:
            ref_clean = ref.lstrip("./")
            target = rel_to_mod.get(ref_clean)
            if not target and mod_dir != ".":
                target = rel_to_mod.get(f"{mod_dir}/{ref_clean}")
            if not target:
                target = name_to_mod.get(Path(ref_clean).name)
            if target and target != mod:
                edge_names.setdefault((mod, target), {})[Path(ref).name] = SYM_VAR
    return edge_names


_RE_FILE_REF = re.compile(r"([\w./_-]+\.(?:ya?ml|json|sh))")


def _collect_file_refs(parsed: dict[str, ast.Module], module_rel: dict[str, str]):
    """Scan Python string literals for references to data/shell files in the project."""
    rel_to_mod = {rel: mod for mod, rel in module_rel.items()}
    name_to_mod = {Path(rel).name: mod for mod, rel in module_rel.items()}

    edge_names: dict[tuple[str, str], dict[str, str]] = {}
    for mod, tree in parsed.items():
        mod_dir = str(PurePosixPath(module_rel.get(mod, "")).parent)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for m in _RE_FILE_REF.finditer(node.value):
                ref = m.group(1).lstrip("./")
                target = rel_to_mod.get(ref)
                if not target and mod_dir != ".":
                    target = rel_to_mod.get(f"{mod_dir}/{ref}")
                if not target:
                    target = name_to_mod.get(Path(ref).name)
                if target and target != mod:
                    edge_names.setdefault((mod, target), {})[Path(ref).name] = SYM_VAR
    return edge_names
