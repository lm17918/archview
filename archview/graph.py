import ast
import fnmatch
import json
import os
import subprocess
from pathlib import Path, PurePosixPath

# Symbol type tags used in node symbols and edge labels
SYM_FUNC = "fn"
SYM_CLASS = "cls"
SYM_VAR = "var"

# (background, text) colors per node role
NODE_COLORS = {
    "entry":        ("#6ee7b7", "#0a2a1a"),
    "intermediate": ("#93c5fd", "#0a1a2e"),
    "leaf":         ("#fca5a5", "#2e0a0a"),
    "isolated":     ("#3a3a46", "#e2e2e8"),
}


def collect_py_files(project_dir: Path, ignore_file: Path | None) -> list[str]:
    """Return sorted list of relative .py paths, git-aware and ignore-filtered."""
    project_dir = Path(project_dir)

    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=project_dir, capture_output=True, text=True, check=True
        )
        py_files = set(result.stdout.strip().splitlines())

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "*.py"],
            cwd=project_dir, capture_output=True, text=True
        )
        py_files.update(untracked.stdout.strip().splitlines())

        deleted = subprocess.run(
            ["git", "ls-files", "--deleted", "*.py"],
            cwd=project_dir, capture_output=True, text=True
        )
        py_files -= set(deleted.stdout.strip().splitlines())

    except subprocess.CalledProcessError:
        py_files = set()
        skip = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in files:
                if f.endswith(".py"):
                    rel = os.path.relpath(os.path.join(root, f), project_dir)
                    py_files.add(rel)

    py_files = sorted(f for f in py_files if f)

    if ignore_file and Path(ignore_file).exists():
        patterns = []
        for line in Path(ignore_file).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

        def matches_any(filepath: str) -> bool:
            p = PurePosixPath(filepath)
            parts = list(p.parts) + ([p.stem] if p.suffix else [])
            return any(
                any(fnmatch.fnmatch(part, pattern) for part in parts)
                for pattern in patterns
            )

        py_files = [f for f in py_files if not matches_any(f)]

    return py_files


def _find_target(imp: str, modules: dict) -> str | None:
    """Resolve an import string to a known module id."""
    if imp in modules:
        return imp
    for m in modules:
        if m.startswith(imp + "."):
            return m
    return None


def _build_module_index(project_dir: Path, py_files: list[str]):
    """Map relative paths to module ids and absolute paths."""
    modules = {}      # mod -> absolute path
    module_rel = {}   # mod -> relative path
    for rel in py_files:
        full = project_dir / rel
        if not full.is_file():
            continue
        mod = rel.replace("/", ".").removesuffix(".py")
        if mod.endswith(".__init__"):
            mod = mod[:-9]
        modules[mod] = full
        module_rel[mod] = rel
    return modules, module_rel


def _parse_modules(modules: dict[str, Path]):
    """Parse each module via AST. Returns docstrings, symbols, and parsed trees."""
    docstrings: dict[str, str] = {}
    module_symbols: dict[str, dict[str, str]] = {}
    parsed: dict[str, ast.Module] = {}

    for mod, path in modules.items():
        try:
            tree = ast.parse(path.read_text())
            parsed[mod] = tree
        except Exception:
            continue

        ds = ast.get_docstring(tree)
        if ds:
            first_line = ds.strip().split("\n")[0].strip()
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            docstrings[mod] = first_line

        syms: dict[str, str] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                syms[node.name] = SYM_FUNC
            elif isinstance(node, ast.ClassDef):
                syms[node.name] = SYM_CLASS
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in syms:
                        syms[t.id] = SYM_VAR
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id not in syms:
                    syms[node.target.id] = SYM_VAR
        module_symbols[mod] = syms

    return docstrings, module_symbols, parsed


def _collect_imports(parsed, modules, module_symbols):
    """Walk ASTs to build edge map: (importer, dep) -> {name: symbol_type}."""
    edge_names: dict[tuple[str, str], dict[str, str]] = {}

    for mod, tree in parsed.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _find_target(alias.name, modules)
                    if target and target != mod:
                        edge_names.setdefault((mod, target), {})
            elif isinstance(node, ast.ImportFrom) and node.module:
                target = _find_target(node.module, modules)
                if target and target != mod:
                    target_syms = module_symbols.get(target, {})
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        sym = target_syms.get(alias.name, SYM_VAR)
                        edge_names.setdefault((mod, target), {})[alias.name] = sym

    return edge_names


def _classify_node(node_id, importers, imported):
    """Return the role of a module based on its import relationships."""
    is_importer = node_id in importers
    is_imported = node_id in imported
    if is_importer and not is_imported:
        return "entry"
    if is_imported and not is_importer:
        return "leaf"
    if is_importer and is_imported:
        return "intermediate"
    return "isolated"


def _find_parent(node_id: str, all_containers: set[str]) -> str:
    """Return the parent container id, or empty string if top-level."""
    parts = node_id.split(".")
    if len(parts) > 1:
        candidate = ".".join(parts[:-1])
        if candidate in all_containers:
            return candidate
    return ""


def _build_elements(all_nodes, folder_ids, all_containers, edge_names,
                    importers, imported, docstrings, module_symbols, module_rel):
    """Assemble the Cytoscape elements list (nodes + edges)."""
    elements = []

    # Folder (synthetic compound) nodes — emitted first so children can reference them
    for folder in sorted(folder_ids):
        elements.append({"data": {
            "id": folder,
            "label": folder.split(".")[-1],
            "is_folder": True,
            "parent": _find_parent(folder, all_containers),
            "docstring": "", "color": "", "textColor": "",
            "type": "folder", "group": "", "filepath": "", "symbols": "",
        }})

    # Module nodes
    for node in all_nodes:
        ntype = _classify_node(node, importers, imported)
        bg, fg = NODE_COLORS[ntype]
        elements.append({"data": {
            "id": node,
            "label": node.split(".")[-1],
            "docstring": docstrings.get(node, ""),
            "color": bg,
            "textColor": fg,
            "type": ntype,
            "group": node.split(".")[0] if "." in node else "",
            "filepath": module_rel.get(node, ""),
            "parent": _find_parent(node, all_containers),
            "symbols": "\n".join(
                f"{sym} {name}"
                for name, sym in sorted(module_symbols.get(node, {}).items())
                if sym in (SYM_FUNC, SYM_CLASS)
            ),
        }})

    # Edges — arrow points FROM dependency TO importer
    for src, tgt in sorted(edge_names.keys()):
        name_syms = edge_names[(src, tgt)]
        label = "\n".join(f"{sym} {name}" for name, sym in sorted(name_syms.items()))
        elements.append({"data": {
            "id": f"{src}->{tgt}",
            "source": tgt,
            "target": src,
            "label": label,
        }})

    return elements


def generate_graph(project_dir: Path, ignore_file: Path | None, output_path: Path) -> None:
    """Parse .py files via AST and write Cytoscape elements JSON to output_path."""
    project_dir = Path(project_dir)
    py_files = collect_py_files(project_dir, ignore_file)
    modules, module_rel = _build_module_index(project_dir, py_files)
    docstrings, module_symbols, parsed = _parse_modules(modules)
    edge_names = _collect_imports(parsed, modules, module_symbols)

    all_nodes = sorted(modules.keys())
    all_nodes_set = set(all_nodes)
    importers = {src for src, _ in edge_names}
    imported = {tgt for _, tgt in edge_names}

    # Synthetic folder nodes for directories without __init__.py
    folder_ids: set[str] = set()
    for node in all_nodes:
        parts = node.split(".")
        if len(parts) > 1:
            candidate = ".".join(parts[:-1])
            if candidate not in all_nodes_set:
                folder_ids.add(candidate)

    all_containers = all_nodes_set | folder_ids

    elements = _build_elements(
        all_nodes, folder_ids, all_containers, edge_names,
        importers, imported, docstrings, module_symbols, module_rel,
    )
    output_path.write_text(json.dumps(elements))
