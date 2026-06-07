"""Resolve Python imports into dependency edges, following package re-exports."""

from __future__ import annotations

import ast

from archview.analysis.model import SYM_VAR


def _find_target(imp: str, modules: dict) -> str | None:
    if imp in modules:
        return imp
    for m in modules:
        if m.startswith(imp + "."):
            return m
    return None


def _resolve_absolute(imp: str, mod: str, modules: dict) -> str | None:
    """Resolve an absolute import name, falling back to an implicit sibling
    import (script-style) when no top-level match exists.

    `from evaluate import x` inside `pkg/main.py` resolves to `pkg.evaluate`
    only when it isn't already a top-level module — Python finds it the same
    way when `pkg/` is run as a script. The fallback never overrides a real
    absolute match and only ever resolves to a sibling that actually exists,
    so it cannot redirect an already-resolved import.
    """
    target = _find_target(imp, modules)
    if target:
        return target
    sibling = _resolve_relative_import(mod, 1, imp, modules)
    return _find_target(sibling, modules) if sibling else None


def _resolve_relative_import(
    mod: str, level: int, sub: str | None, modules: dict
) -> str | None:
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
    base_parts = parts[: len(parts) - hops] if hops else parts
    base = ".".join(base_parts)
    if sub:
        return f"{base}.{sub}" if base else sub
    return base or None


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
                base = _resolve_relative_import(mod, node.level, node.module, modules)
                if not base:
                    continue
                pkg_target = _find_target(base, modules) if node.module else None
            elif node.module:
                pkg_target = _resolve_absolute(node.module, mod, modules)
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
                    target = _resolve_absolute(alias.name, mod, modules)
                    if (
                        target
                        and target != mod
                        and not _is_containment_edge(mod, target)
                    ):
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
                                _add_edge(
                                    edge_names,
                                    mod,
                                    target,
                                    alias.name,
                                    sym,
                                    reexport_map,
                                    module_symbols,
                                )
                    else:
                        # from . import x, y  -> each alias may be a submodule
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            sub_target = _find_target(
                                f"{base}.{alias.name}" if base else alias.name,
                                modules,
                            )
                            if (
                                sub_target
                                and sub_target != mod
                                and not _is_containment_edge(mod, sub_target)
                            ):
                                edge_names.setdefault((mod, sub_target), {})[
                                    alias.name
                                ] = SYM_VAR
                elif node.module:
                    target = _resolve_absolute(node.module, mod, modules)
                    if target and target != mod:
                        target_syms = module_symbols.get(target, {})
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            sym = target_syms.get(alias.name, SYM_VAR)
                            _add_edge(
                                edge_names,
                                mod,
                                target,
                                alias.name,
                                sym,
                                reexport_map,
                                module_symbols,
                            )

    return edge_names
