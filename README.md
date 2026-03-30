# ArchView

Interactive live architecture viewer for Python projects. Analyzes import dependencies via AST and renders an interactive graph in the browser.

## Features

- **AST-based analysis** — no regex, parses real Python syntax
- **Live refresh** — watches for file changes and updates the graph automatically
- **Interactive UI** — click, hover, drag, collapse folders, highlight dependencies
- **IDE integration** — double-click a node to open the file in VS Code
- **Zero dependencies** — pure Python, ships with Cytoscape.js & Dagre.js
- **Git-aware** — only analyzes tracked files (falls back to os.walk)
- **Draw.io export** — save positions and export as `.drawio`

## Install

```bash
pip install -e .
```

## Quick Start

```bash
# Analyze the example project
archview example_project

# Or analyze any Python project
archview /path/to/your/project

# Custom port and refresh interval
archview /path/to/project --port 8080 --interval 5
```

Then open http://localhost:9090 in your browser.

## Example Project

The `example_project/` directory contains a mini e-commerce app to demonstrate archview's capabilities:

```
example_project/
  app/
    main.py           # Entry point — wires everything together
    config.py         # Global settings
    api/
      routes.py       # REST API route definitions
      auth.py         # Authentication middleware
    services/
      user_service.py   # User management
      order_service.py  # Order processing
      email_service.py  # Email notifications
    models/
      user.py         # User data model
      order.py        # Order data model
    data/
      formatters.py   # CSV/JSON export formatters
    utils/
      logger.py       # Logging utility
      validators.py   # Input validation
  scripts/
    seed_db.py        # Database seeding script
    migrate.py        # Migration runner
    export_report.py  # Report export script
```

Try it:

```bash
archview example_project
```

You'll see all node types in the graph:
- **Green (Top-level)** — entry points like `main.py` and scripts
- **Blue (Intermediate)** — modules that both import and are imported (e.g. `routes`, `user_service`)
- **Red (Utility)** — leaf modules only imported by others (e.g. `logger`, `validators`)
- Folders collapse/expand on click

## Manage Ignore Patterns

```bash
# Exclude directories from analysis
archview ignore tests __pycache__ venv

# List current patterns
archview ignore --list

# Remove a pattern
archview ignore --remove tests
```

## Tests

```bash
pip install -e ".[test]"
pytest tests/
```
