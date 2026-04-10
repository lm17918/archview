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
    "error":        ("#dc2626", "#ffffff"),
    "config":       ("#fde68a", "#422006"),
}

CONFIG_EXTENSIONS = (
    "json", "yaml", "yml", "toml", "ini", "cfg", "env", "xml",
)
_CONFIG_SUFFIXES = tuple("." + e for e in CONFIG_EXTENSIONS)


def _collect_files(project_dir: Path, extension: str, ignore_file: Path | None) -> list[str]:
    """Return sorted list of relative paths matching extension, git-aware and ignore-filtered."""
    project_dir = Path(project_dir)
    glob_pattern = f"*.{extension}"
    suffix = f".{extension}"

    try:
        result = subprocess.run(
            ["git", "ls-files", glob_pattern],
            cwd=project_dir, capture_output=True, text=True, check=True
        )
        files = set(result.stdout.strip().splitlines())

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", glob_pattern],
            cwd=project_dir, capture_output=True, text=True
        )
        files.update(untracked.stdout.strip().splitlines())

        deleted = subprocess.run(
            ["git", "ls-files", "--deleted", glob_pattern],
            cwd=project_dir, capture_output=True, text=True
        )
        files -= set(deleted.stdout.strip().splitlines())

    except subprocess.CalledProcessError:
        files = set()
        skip = {"__pycache__", "venv", ".venv", "node_modules", ".git",
                "site-packages", ".archview"}
        for root, dirs, fnames in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in fnames:
                if f.endswith(suffix):
                    rel = os.path.relpath(os.path.join(root, f), project_dir)
                    files.add(rel)

    files = sorted(f for f in files if f)

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

        files = [f for f in files if not matches_any(f)]

    return files


def collect_py_files(project_dir: Path, ignore_file: Path | None) -> list[str]:
    """Return sorted list of relative .py paths, git-aware and ignore-filtered."""
    return _collect_files(project_dir, "py", ignore_file)


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
        if node in parse_errors:
            bg, fg = NODE_COLORS["error"]
            label = "\u26a0 " + node.split(".")[-1]
            docstring = parse_errors[node]
            ntype = "error"
            symbols = ""
        else:
            ntype = _classify_node(node, importers, imported)
            bg, fg = NODE_COLORS[ntype]
            label = node.split(".")[-1]
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


def _config_node_id(rel_path: str) -> str:
    """Convert a config file path to a dot-separated node ID."""
    parts = rel_path.replace("\\", "/").split("/")
    dirs, filename = parts[:-1], parts[-1]
    last_dot = filename.rfind(".")
    if last_dot > 0:
        name = filename[:last_dot] + "_" + filename[last_dot + 1:]
    elif last_dot == 0:
        name = "_" + filename[1:]
    else:
        name = filename
    return ".".join(dirs + [name])


def _build_config_index(project_dir: Path, config_files):
    """Map config file paths to node IDs and absolute paths."""
    modules: dict[str, Path] = {}
    rel_map: dict[str, str] = {}
    for rel in config_files:
        full = project_dir / rel
        if not full.is_file():
            continue
        node_id = _config_node_id(rel)
        modules[node_id] = full
        rel_map[node_id] = rel
    return modules, rel_map


def _parse_config_file(path: Path) -> dict[str, str]:
    """Extract top-level keys from a single config file."""
    ext = path.suffix.lower()
    if not ext and path.name.startswith("."):
        ext = "." + path.name[1:]  # .env -> ".env"
    text = path.read_text()

    if ext == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            return {k: SYM_VAR for k in list(data.keys())[:30]}
        return {}

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                return {
                    k: SYM_VAR for k in list(data.keys())[:30]
                }
        except ImportError:
            pass
        return {}

    if ext == ".toml":
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return {}
        data = tomllib.loads(text)
        if isinstance(data, dict):
            return {k: SYM_VAR for k in list(data.keys())[:30]}
        return {}

    if ext in (".ini", ".cfg"):
        import configparser
        cp = configparser.ConfigParser()
        cp.read_string(text)
        return {s: SYM_VAR for s in cp.sections()[:30]}

    if ext == ".env":
        keys: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key:
                keys[key] = SYM_VAR
                if len(keys) >= 30:
                    break
        return keys

    if ext == ".xml":
        import xml.etree.ElementTree as ET
        root = ET.fromstring(text)
        seen: dict[str, str] = {}
        for child in root:
            tag = child.tag.split("}")[-1]
            if tag not in seen:
                seen[tag] = SYM_VAR
                if len(seen) >= 30:
                    break
        return seen

    return {}


def _parse_config_files(config_modules: dict[str, Path]):
    """Parse config files and extract top-level keys."""
    symbols: dict[str, dict[str, str]] = {}
    errors: dict[str, str] = {}
    for node_id, path in config_modules.items():
        try:
            symbols[node_id] = _parse_config_file(path)
        except Exception as e:
            errors[node_id] = str(e)
            symbols[node_id] = {}
    return symbols, errors


def _collect_config_refs(parsed, module_paths, cfg_rel, project_dir):
    """Scan Python ASTs for config file refs: direct strings and imported vars."""
    path_to_id: dict[str, str] = {}
    for cid, rel in cfg_rel.items():
        path_to_id[rel] = cid
        path_to_id[os.path.basename(rel)] = cid

    def _resolve(s: str, mod_dir: Path) -> str | None:
        cid = path_to_id.get(s)
        if cid is None:
            try:
                candidate = (mod_dir / s).resolve()
                rel_c = os.path.relpath(
                    str(candidate),
                    str(project_dir.resolve()),
                )
                cid = path_to_id.get(rel_c)
            except (ValueError, OSError):
                pass
        if cid is None:
            cid = path_to_id.get(os.path.basename(s))
        return cid

    def _is_cfg(s: str) -> bool:
        return s.endswith(_CONFIG_SUFFIXES)

    edges: dict[tuple[str, str], dict] = {}
    cfg_vars: dict[tuple[str, str], str] = {}

    # Pass 1: direct string literals + variable assignments
    for mod, tree in parsed.items():
        mod_dir = module_paths[mod].parent
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and _is_cfg(node.value)):
                cid = _resolve(node.value, mod_dir)
                if cid:
                    edges.setdefault((mod, cid), {})

            if isinstance(node, ast.Assign):
                val = node.value
                if (isinstance(val, ast.Constant)
                        and isinstance(val.value, str)
                        and _is_cfg(val.value)):
                    cid = _resolve(val.value, mod_dir)
                    if cid:
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                cfg_vars[(mod, t.id)] = cid
            elif isinstance(node, ast.AnnAssign) and node.value:
                val = node.value
                if (isinstance(val, ast.Constant)
                        and isinstance(val.value, str)
                        and _is_cfg(val.value)):
                    cid = _resolve(val.value, mod_dir)
                    if cid and isinstance(node.target, ast.Name):
                        cfg_vars[(mod, node.target.id)] = cid

    # Pass 2: follow "from X import VAR" where VAR is a config path
    if cfg_vars:
        for mod, tree in parsed.items():
            for node in ast.walk(tree):
                if not (isinstance(node, ast.ImportFrom)
                        and node.module):
                    continue
                source = _find_target(
                    node.module, module_paths,
                )
                if not source:
                    continue
                for alias in node.names:
                    cid = cfg_vars.get((source, alias.name))
                    if cid:
                        edges.setdefault((mod, cid), {})

    return edges


def generate_graph(project_dir: Path, ignore_file: Path | None, output_path: Path) -> None:
    """Parse .py and .json files and write Cytoscape elements JSON."""
    project_dir = Path(project_dir)
    py_files = collect_py_files(project_dir, ignore_file)
    modules, module_rel = _build_module_index(project_dir, py_files)
    docstrings, module_symbols, parsed, parse_errors = _parse_modules(modules)
    edge_names = _collect_imports(parsed, modules, module_symbols)

    # Config file support
    config_files: list[str] = []
    for ext in CONFIG_EXTENSIONS:
        config_files.extend(
            _collect_files(project_dir, ext, ignore_file),
        )
    cfg_mods, cfg_rel = _build_config_index(
        project_dir, config_files,
    )
    cfg_syms, cfg_errors = _parse_config_files(cfg_mods)
    cfg_edges = _collect_config_refs(
        parsed, modules, cfg_rel, project_dir,
    )

    all_py = sorted(modules.keys())
    all_cfg = sorted(cfg_mods.keys())
    all_nodes_set = set(all_py) | set(all_cfg)

    # Python-only classification
    importers = {src for src, _ in edge_names}
    imported = {tgt for _, tgt in edge_names}

    # Synthetic folder nodes
    folder_ids: set[str] = set()
    for node in all_nodes_set:
        parts = node.split(".")
        if len(parts) > 1:
            candidate = ".".join(parts[:-1])
            if candidate not in all_nodes_set:
                folder_ids.add(candidate)

    all_containers = all_nodes_set | folder_ids

    elements = _build_elements(
        all_py, folder_ids, all_containers, edge_names,
        importers, imported, docstrings, module_symbols,
        module_rel, parse_errors,
    )

    # Config nodes
    for nid in all_cfg:
        if nid in cfg_errors:
            bg, fg = NODE_COLORS["error"]
            label = "\u26a0 " + Path(cfg_rel[nid]).name
            doc = cfg_errors[nid]
            ntype = "error"
            syms_str = ""
        else:
            bg, fg = NODE_COLORS["config"]
            label = Path(cfg_rel[nid]).name
            doc = ""
            ntype = "config"
            syms = cfg_syms.get(nid, {})
            syms_str = "\n".join(
                f"{sym} {name}"
                for name, sym in sorted(syms.items())
            )
        elements.append({"data": {
            "id": nid,
            "label": label,
            "docstring": doc,
            "color": bg,
            "textColor": fg,
            "type": ntype,
            "group": nid.split(".")[0] if "." in nid else "",
            "filepath": cfg_rel.get(nid, ""),
            "parent": _find_parent(nid, all_containers),
            "symbols": syms_str,
        }})

    # Config edges
    for src, tgt in sorted(cfg_edges.keys()):
        elements.append({"data": {
            "id": f"{src}->{tgt}",
            "source": tgt,
            "target": src,
            "label": "",
        }})

    # Atomic write
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(elements))
    tmp.rename(output_path)
