"""Parse Python (via AST) and shell scripts for docstrings, symbols, and refs."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from archview.analysis.model import SYM_CLASS, SYM_FUNC, SYM_VAR


def _parse_modules(modules: dict[str, Path]):
    docstrings: dict[str, str] = {}
    module_symbols: dict[str, dict[str, str]] = {}
    parsed: dict[str, ast.Module] = {}
    parse_errors: dict[str, str] = {}

    for mod, path in modules.items():
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
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


_RE_SH_FUNC = re.compile(r"^\s*(?:function\s+(\w+)|(\w+)\s*\(\s*\))", re.MULTILINE)
_DATA_EXT = r"(?:ya?ml|json)"
_RE_SH_REFS = [
    re.compile(r"(?:python[\d.]*)\s+(?:-\w+\s+)*([\w./_-]+\.py)"),
    re.compile(r"(?:bash|sh|zsh)\s+(?:-\w+\s+)*([\w./_-]+\.(?:sh|bash))"),
    re.compile(r"(?:source|\.)\s+([\w./_-]+\.(?:sh|bash))"),
    re.compile(r"\./?([\w./_-]+\.(?:sh|bash|py))"),
    re.compile(r"([\w./_-]+\." + _DATA_EXT + r")"),
]


def _parse_shell_scripts(modules: dict[str, Path]):
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

        syms: dict[str, str] = {}
        for m in _RE_SH_FUNC.finditer(text):
            name = m.group(1) or m.group(2)
            syms[name] = SYM_FUNC
        module_symbols[mod] = syms

        refs: set[str] = set()
        for pat in _RE_SH_REFS:
            for m in pat.finditer(text):
                refs.add(m.group(1))
        shell_refs[mod] = list(refs)

    return docstrings, module_symbols, shell_refs
