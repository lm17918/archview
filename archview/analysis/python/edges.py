"""Walk Python ASTs to build dependency edges, classified by import context."""

from __future__ import annotations

import ast

from archview.analysis.model import SYM_VAR
from archview.analysis.python.resolve import (
    _build_reexport_map,
    _find_target,
    _is_containment_edge,
    _resolve_absolute,
    _resolve_relative_import,
    _resolve_reexport,
)

# Import context: static (executed at import time), lazy (inside a function),
# type-only (under `if TYPE_CHECKING:`). Lower rank = stronger dependency;
# an edge keeps the strongest kind of all imports that produced it.
KIND_STATIC = "static"
KIND_LAZY = "lazy"
KIND_TYPE = "type"
_KIND_RANK = {KIND_STATIC: 0, KIND_LAZY: 1, KIND_TYPE: 2}


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _walk_imports(node: ast.AST, kind: str):
    """Yield (import_or_call_node, kind), tracking the lexical context."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield node, kind
        return
    if isinstance(node, ast.Call):
        yield node, kind
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        if kind == KIND_STATIC:
            kind = KIND_LAZY
    if isinstance(node, ast.If) and _is_type_checking(node.test):
        for sub in node.body:
            yield from _walk_imports(sub, KIND_TYPE)
        for sub in node.orelse:
            yield from _walk_imports(sub, kind)
        return
    for child in ast.iter_child_nodes(node):
        yield from _walk_imports(child, kind)


def _dynamic_import_name(call: ast.Call) -> str | None:
    """Module name from importlib.import_module("x") / __import__("x") calls."""
    func = call.func
    is_import_call = (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    ) or (isinstance(func, ast.Name) and func.id in ("import_module", "__import__"))
    if not is_import_call or not call.args:
        return None
    arg = call.args[0]
    if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
        return None
    name = arg.value
    if not name.startswith("."):
        return name
    # Relative form needs a literal package= to anchor against
    pkg = next(
        (
            kw.value.value
            for kw in call.keywords
            if kw.arg == "package"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ),
        None,
    )
    if not pkg:
        return None
    hops = len(name) - len(name.lstrip(".")) - 1
    parts = pkg.split(".")
    if hops > len(parts):
        return None
    base = parts[: len(parts) - hops] if hops else parts
    sub = name.lstrip(".")
    return ".".join(base + [sub]) if sub else ".".join(base)


def _collect_imports(parsed, modules, module_symbols):
    """Build (importer, dep) -> {name: symbol_type} plus a kind per edge."""
    edge_names: dict[tuple[str, str], dict[str, str]] = {}
    edge_kinds: dict[tuple[str, str], str] = {}
    reexport_map = _build_reexport_map(parsed, modules)

    def merge_kind(key, kind):
        cur = edge_kinds.get(key)
        if cur is None or _KIND_RANK[kind] < _KIND_RANK[cur]:
            edge_kinds[key] = kind

    def add_module_edge(mod, target, kind):
        if target and target != mod and not _is_containment_edge(mod, target):
            edge_names.setdefault((mod, target), {})
            merge_kind((mod, target), kind)

    def add_symbol_edge(mod, target, name, kind):
        final = _resolve_reexport(target, name, reexport_map)
        # `from pkg import sub` where sub is a module, not a symbol: the
        # dependency is the submodule itself, with no symbol label.
        if name not in module_symbols.get(final, {}) and f"{final}.{name}" in modules:
            add_module_edge(mod, f"{final}.{name}", kind)
            return
        if final == mod or _is_containment_edge(mod, final):
            return
        sym = module_symbols.get(final, {}).get(name, SYM_VAR)
        edge_names.setdefault((mod, final), {})[name] = sym
        merge_kind((mod, final), kind)

    def handle_import_from(node, mod, kind):
        if node.level:
            base = _resolve_relative_import(mod, node.level, node.module, modules)
            if not base:
                return
            if node.module:
                target = _find_target(base, modules)
                if not target or target == mod:
                    return
                for alias in node.names:
                    if alias.name != "*":
                        add_symbol_edge(mod, target, alias.name, kind)
            else:
                # from . import x, y -> each alias may be a submodule
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    sub = _find_target(
                        f"{base}.{alias.name}" if base else alias.name, modules
                    )
                    add_module_edge(mod, sub, kind)
        elif node.module:
            target = _resolve_absolute(node.module, mod, modules)
            if not target or target == mod:
                return
            for alias in node.names:
                if alias.name != "*":
                    add_symbol_edge(mod, target, alias.name, kind)

    for mod, tree in parsed.items():
        for node, kind in _walk_imports(tree, KIND_STATIC):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add_module_edge(
                        mod, _resolve_absolute(alias.name, mod, modules), kind
                    )
            elif isinstance(node, ast.ImportFrom):
                handle_import_from(node, mod, kind)
            else:  # ast.Call — maybe a dynamic import
                name = _dynamic_import_name(node)
                if name:
                    add_module_edge(mod, _resolve_absolute(name, mod, modules), kind)

    return edge_names, edge_kinds
