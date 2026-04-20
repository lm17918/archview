# ArchView examples

Mini object-detection projects used to test archview features.

Run `archview <folder>` inside any of them and check the graph.

| Folder | What it exercises |
|--------|-------------------|
| `01_basic_pipeline` | Linear chain — node classification (entry / intermediate / leaf) |
| `02_package_structure` | Subpackages + `__init__` re-exports — folder grouping, re-export redirect |
| `03_configs_and_shells` | `.yaml` / `.json` / `.sh` files — non-Python nodes and file-reference edges |
| `04_edge_cases` | Syntax error, isolated module, circular imports — error nodes & cycles |
| `05_relative_imports` | `from . import x`, `from ..y import z` — PEP 328 resolution |
