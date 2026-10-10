"""Resolve import names to module ids, following package re-exports."""

from __future__ import annotations

import ast


def _find_target(imp: str, modules: dict) -> str | None:
    """Resolve an import name to a module id.

    When `imp` is a namespace directory (no __init__.py, only a prefix of real
    modules) return `imp` itself — that matches the synthetic folder node,
    which always exists because at least one module lives beneath it. Picking
    an arbitrary submodule here would draw a wrong edge.
    """
    if imp in modules:
        return imp
    for m in modules:
        if m.startswith(imp + "."):
            return imp
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
