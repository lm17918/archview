from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
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
    "error":        ("#dc2626", "#ffffff"),
}


def _collect_files_by_ext(project_dir: Path, ignore_file: Path | None, ext: str) -> list[str]:
    """Return sorted list of relative paths with given extension, git-aware and ignore-filtered."""
    project_dir = Path(project_dir)
    glob = f"*{ext}"

    try:
        result = subprocess.run(
            ["git", "ls-files", glob],
            cwd=project_dir, capture_output=True, text=True, check=True
        )
        found = set(result.stdout.strip().splitlines())

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", glob],
            cwd=project_dir, capture_output=True, text=True
        )
        found.update(untracked.stdout.strip().splitlines())

        deleted = subprocess.run(
            ["git", "ls-files", "--deleted", glob],
            cwd=project_dir, capture_output=True, text=True
        )
        found -= set(deleted.stdout.strip().splitlines())

    except subprocess.CalledProcessError:
        found = set()
        skip = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in files:
                if f.endswith(ext):
                    rel = os.path.relpath(os.path.join(root, f), project_dir)
                    found.add(rel)

    found = sorted(f for f in found if f)

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

        found = [f for f in found if not matches_any(f)]

    return found


def collect_py_files(project_dir: Path, ignore_file: Path | None) -> list[str]:
    """Return sorted list of relative .py paths, git-aware and ignore-filtered."""
    return _collect_files_by_ext(project_dir, ignore_file, ".py")


def _find_target(imp: str, modules: dict) -> str | None:
    """Resolve an import string to a known module id."""
    if imp in modules:
        return imp
    for m in modules:
        if m.startswith(imp + "."):
            return m
    return None


def _resolve_relative_import(mod: str, level: int, sub: str | None,
                              modules: dict) -> str | None:
    """Resolve a PEP 328 relative import to an absolute module id.

    For a package (__init__.py), level=1 anchors to the package itself; for a
    module file, level=1 anchors to its containing package.
    """
    path = modules.get(mod)
    is_package = path is not None and path.name == "__init__.py"
    parts = mod.split(".")
    hops = level - 1 if is_package else level
    if hops < 0 or hops > len(parts):
        return None
    base_parts = parts[:len(parts) - hops] if hops else parts
    base = ".".join(base_parts)
    if sub:
        return f"{base}.{sub}" if base else sub
    return base or None


def _build_module_index(project_dir: Path, files: list[str], ext: str = ".py",
                        keep_ext: bool = False):
    """Map relative paths to module ids and absolute paths.

    When keep_ext is True the extension is baked into the id using '_' so that
    'config.yaml' becomes 'config_yaml' instead of colliding with 'config.py'.
    """
    modules = {}      # mod -> absolute path
    module_rel = {}   # mod -> relative path
    for rel in files:
        full = project_dir / rel
        if not full.is_file():
            continue
        if keep_ext:
            mod = rel.replace("/", ".").replace(ext, "_" + ext.lstrip("."))
        else:
            mod = rel.replace("/", ".").removesuffix(ext)
        if mod.endswith(".__init__"):
            mod = mod[:-9]
        modules[mod] = full
        module_rel[mod] = rel
    return modules, module_rel


def _parse_modules(modules: dict[str, Path]):
    """Parse each module via AST. Returns docstrings, symbols, parsed trees, and errors."""
    docstrings: dict[str, str] = {}
    module_symbols: dict[str, dict[str, str]] = {}
    parsed: dict[str, ast.Module] = {}
    parse_errors: dict[str, str] = {}

    for mod, path in modules.items():
        try:
            tree = ast.parse(path.read_text())
            parsed[mod] = tree
        except SyntaxError as e:
            parse_errors[mod] = f"SyntaxError: {e.msg} (line {e.lineno})"
            continue
        except Exception as e:
            parse_errors[mod] = str(e)
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

    return docstrings, module_symbols, parsed, parse_errors


def _is_containment_edge(src: str, dst: str) -> bool:
    """True when src and dst are on the same package spine.

    These edges (package __init__ re-exporting its own submodules, or a
    submodule reaching up to its own parent) are already conveyed by the
    containment hierarchy in the graph view, so adding an arrow is noise.
    """
    return dst.startswith(src + ".") or src.startswith(dst + ".")


def _build_reexport_map(parsed, modules):
    """Map (package_mod, local_name) -> origin submodule, via __init__ re-exports."""
    reexport: dict[str, dict[str, str]] = {}
    for mod, tree in parsed.items():
        path = modules.get(mod)
        if path is None or path.name != "__init__.py":
            continue
        entries: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:
                base = _resolve_relative_import(
                    mod, node.level, node.module, modules
                )
                if not base:
                    continue
                pkg_target = _find_target(base, modules) if node.module else None
            elif node.module:
                pkg_target = _find_target(node.module, modules)
                base = node.module
            else:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                if node.level and not node.module:
                    sub = _find_target(
                        f"{base}.{alias.name}" if base else alias.name, modules
                    )
                    if sub:
                        entries[local] = sub
                elif pkg_target:
                    entries[local] = pkg_target
        if entries:
            reexport[mod] = entries
    return reexport


def _resolve_reexport(target: str, name: str, reexport_map) -> str:
    """Follow re-export chain for `name` starting at `target`."""
    seen: set[tuple[str, str]] = set()
    while True:
        key = (target, name)
        if key in seen:
            return target
        seen.add(key)
        nxt = reexport_map.get(target, {}).get(name)
        if not nxt or nxt == target:
            return target
        target = nxt


def _add_edge(edge_names, mod, target, name, sym, reexport_map, module_symbols):
    """Add one edge, redirecting through re-exports when possible."""
    final = _resolve_reexport(target, name, reexport_map)
    if final == mod or _is_containment_edge(mod, final):
        return
    real_sym = module_symbols.get(final, {}).get(name, sym)
    edge_names.setdefault((mod, final), {})[name] = real_sym


def _collect_imports(parsed, modules, module_symbols):
    """Walk ASTs to build edge map: (importer, dep) -> {name: symbol_type}."""
    edge_names: dict[tuple[str, str], dict[str, str]] = {}
    reexport_map = _build_reexport_map(parsed, modules)

    for mod, tree in parsed.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _find_target(alias.name, modules)
                    if target and target != mod and not _is_containment_edge(mod, target):
                        edge_names.setdefault((mod, target), {})
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = _resolve_relative_import(
                        mod, node.level, node.module, modules
                    )
                    if not base:
                        continue
                    if node.module:
                        target = _find_target(base, modules)
                        if target and target != mod:
                            target_syms = module_symbols.get(target, {})
                            for alias in node.names:
                                if alias.name == "*":
                                    continue
                                sym = target_syms.get(alias.name, SYM_VAR)
                                _add_edge(edge_names, mod, target, alias.name,
                                          sym, reexport_map, module_symbols)
                    else:
                        # from . import x, y  -> each alias may be a submodule
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            sub_target = _find_target(
                                f"{base}.{alias.name}" if base else alias.name,
                                modules,
                            )
                            if sub_target and sub_target != mod and not _is_containment_edge(mod, sub_target):
                                edge_names.setdefault(
                                    (mod, sub_target), {}
                                )[alias.name] = SYM_VAR
                elif node.module:
                    target = _find_target(node.module, modules)
                    if target and target != mod:
                        target_syms = module_symbols.get(target, {})
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            sym = target_syms.get(alias.name, SYM_VAR)
                            _add_edge(edge_names, mod, target, alias.name,
                                      sym, reexport_map, module_symbols)

    return edge_names


# --- Shell script analysis ------------------------------------------------

_RE_SH_FUNC = re.compile(
    r'^\s*(?:function\s+(\w+)|(\w+)\s*\(\s*\))', re.MULTILINE
)
_DATA_EXT = r'(?:ya?ml|json)'
_RE_SH_REFS = [
    re.compile(r'(?:python[\d.]*)\s+(?:-\w+\s+)*([\w./_-]+\.py)'),
    re.compile(r'(?:bash|sh|zsh)\s+(?:-\w+\s+)*([\w./_-]+\.(?:sh|bash))'),
    re.compile(r'(?:source|\.)\s+([\w./_-]+\.(?:sh|bash))'),
    re.compile(r'\./?([\w./_-]+\.(?:sh|bash|py))'),
    re.compile(r'([\w./_-]+\.' + _DATA_EXT + r')'),
]


def _parse_shell_scripts(modules: dict[str, Path]):
    """Parse shell scripts to extract function definitions and file references."""
    docstrings: dict[str, str] = {}
    module_symbols: dict[str, dict[str, str]] = {}
    shell_refs: dict[str, list[str]] = {}

    for mod, path in modules.items():
        try:
            text = path.read_text()
        except Exception:
            continue

        # First comment block (after shebang) as docstring
        lines = text.strip().splitlines()
        if lines and lines[0].startswith("#!"):
            lines = lines[1:]
        doc_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                doc_lines.append(stripped.lstrip("# "))
            elif stripped == "":
                continue
            else:
                break
        if doc_lines:
            ds = doc_lines[0]
            if len(ds) > 80:
                ds = ds[:77] + "..."
            docstrings[mod] = ds

        # Function definitions
        syms: dict[str, str] = {}
        for m in _RE_SH_FUNC.finditer(text):
            name = m.group(1) or m.group(2)
            syms[name] = SYM_FUNC
        module_symbols[mod] = syms

        # Script/file references
        refs: set[str] = set()
        for pat in _RE_SH_REFS:
            for m in pat.finditer(text):
                refs.add(m.group(1))
        shell_refs[mod] = list(refs)

    return docstrings, module_symbols, shell_refs


def _resolve_shell_refs(shell_refs, module_rel):
    """Convert shell file references into graph edges."""
    rel_to_mod = {rel: mod for mod, rel in module_rel.items()}
    name_to_mod: dict[str, str] = {}
    for mod, rel in module_rel.items():
        name_to_mod[Path(rel).name] = mod

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


_RE_FILE_REF = re.compile(r'([\w./_-]+\.(?:ya?ml|json|sh))')


def _collect_file_refs(parsed: dict[str, ast.Module], module_rel: dict[str, str]):
    """Scan Python string literals for references to data/shell files in the project."""
    rel_to_mod = {rel: mod for mod, rel in module_rel.items()}
    name_to_mod: dict[str, str] = {}
    for mod, rel in module_rel.items():
        name_to_mod[Path(rel).name] = mod

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
                    importers, imported, docstrings, module_symbols, module_rel,
                    parse_errors=None):
    """Assemble the Cytoscape elements list (nodes + edges)."""
    parse_errors = parse_errors or {}
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
        rel = module_rel.get(node, "")
        raw_name = Path(rel).name if rel else node.split(".")[-1]
        filename = node.split(".")[-1] + ".py" if raw_name == "__init__.py" else raw_name
        if node in parse_errors:
            bg, fg = NODE_COLORS["error"]
            label = "\u26a0 " + filename
            docstring = parse_errors[node]
            ntype = "error"
            symbols = ""
        else:
            ntype = _classify_node(node, importers, imported)
            bg, fg = NODE_COLORS[ntype]
            label = filename
            docstring = docstrings.get(node, "")
            symbols = "\n".join(
                f"{sym} {name}"
                for name, sym in sorted(module_symbols.get(node, {}).items())
                if sym in (SYM_FUNC, SYM_CLASS)
            )
        elements.append({"data": {
            "id": node,
            "label": label,
            "docstring": docstring,
            "color": bg,
            "textColor": fg,
            "type": ntype,
            "group": node.split(".")[0] if "." in node else "",
            "filepath": module_rel.get(node, ""),
            "parent": _find_parent(node, all_containers),
            "symbols": symbols,
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


def generate_graph_json(project_dir: Path, ignore_file: Path | None) -> list[dict]:
    """Parse project files and return Cytoscape elements list."""
    project_dir = Path(project_dir)

    # Collect files by type
    py_files = collect_py_files(project_dir, ignore_file)
    sh_files = _collect_files_by_ext(project_dir, ignore_file, ".sh")
    data_files = []
    for ext in (".yaml", ".yml", ".json"):
        data_files += _collect_files_by_ext(project_dir, ignore_file, ext)

    # Build module indices
    py_modules, py_rel = _build_module_index(project_dir, py_files, ".py")
    sh_modules, sh_rel = _build_module_index(project_dir, sh_files, ".sh")
    data_modules: dict[str, Path] = {}
    data_rel: dict[str, str] = {}
    for ext in (".yaml", ".yml", ".json"):
        dm, dr = _build_module_index(project_dir,
            [f for f in data_files if f.endswith(ext)], ext, keep_ext=True)
        data_modules.update(dm)
        data_rel.update(dr)

    # Merge — no collisions: data files keep their extension in the ID
    modules = {**data_modules, **sh_modules, **py_modules}
    module_rel = {**data_rel, **sh_rel, **py_rel}

    # Parse Python files via AST
    py_docs, py_syms, parsed, parse_errors = _parse_modules(py_modules)

    # Parse shell scripts via regex
    sh_docs, sh_syms, shell_refs = _parse_shell_scripts(sh_modules)

    # Merge metadata
    docstrings = {**py_docs, **sh_docs}
    module_symbols = {**py_syms, **sh_syms}

    # Build edges: Python imports + file refs in Python strings + shell references
    edge_names = _collect_imports(parsed, py_modules, module_symbols)
    py_file_edges = _collect_file_refs(parsed, module_rel)
    for key, syms in py_file_edges.items():
        edge_names.setdefault(key, {}).update(syms)
    sh_edges = _resolve_shell_refs(shell_refs, module_rel)
    for key, syms in sh_edges.items():
        edge_names.setdefault(key, {}).update(syms)

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

    return _build_elements(
        all_nodes, folder_ids, all_containers, edge_names,
        importers, imported, docstrings, module_symbols, module_rel,
        parse_errors,
    )


def generate_graph(project_dir: Path, ignore_file: Path | None, output_path: Path) -> None:
    """Parse project files and write Cytoscape elements JSON to output_path."""
    elements = generate_graph_json(project_dir, ignore_file)
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(elements))
    tmp.rename(output_path)
