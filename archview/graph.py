"""
Public API for graph generation.

This module re-exports the engine. The actual implementation lives in
archview/_engine.py (which will be compiled/obfuscated for distribution).
"""

from archview._engine import (  # noqa: F401
    SYM_FUNC,
    SYM_CLASS,
    SYM_VAR,
    NODE_COLORS,
    collect_py_files,
    generate_graph,
)
