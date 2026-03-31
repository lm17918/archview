# ArchView

**See your codebase. Understand it. Then change it.**

ArchView gives you a live, interactive map of any Python project's architecture — right in your browser. It parses real Python (via AST, not regex), watches for changes, and updates the graph in real time.

Built for developers who vibe-code and need to stay oriented, or anyone inheriting a codebase they didn't write.

<!-- TODO: replace with actual GIF -->
![ArchView demo](docs/demo.gif)

## Why

You're 200 files deep in someone else's project. Or you're building fast and your own code is getting tangled. You need to *see* the structure — what depends on what, where the entry points are, which modules are isolated.

ArchView shows you all of that in seconds, and keeps updating as you code.

## Install

```bash
pip install archview
```

## Usage

```bash
archview /path/to/your/project
```

Open http://localhost:9090 — that's it.

```bash
# Custom port and refresh interval
archview /path/to/project --port 8080 --interval 5
```

## What you see

| Color | Meaning |
|-------|---------|
| **Green** | Entry points — modules that import but aren't imported |
| **Blue** | Connectors — modules that both import and are imported |
| **Red** | Utilities — leaf modules only imported by others |
| **Gray** | Isolated — no import relationships |
| **Red (bright)** | Syntax errors — files that failed to parse |

<!-- TODO: replace with actual GIF -->
![Node colors and types](docs/colors.gif)

## Features

### Live refresh
Edit your code, save — the graph updates automatically. No restart needed.

<!-- TODO: replace with actual GIF -->
![Live refresh](docs/live-refresh.gif)

### Interactive exploration
- **Hover** a node to see its docstring, type, and exported symbols
- **Click** a node to highlight its direct dependencies
- **Double-click** to open the file in VS Code
- **Drag** nodes to rearrange the layout
- **Click folders** to collapse/expand entire packages

<!-- TODO: replace with actual GIF -->
![Interactive exploration](docs/interaction.gif)

### Dependency highlighting
Hover over an edge to see exactly which symbols are imported. Click a node and its entire dependency chain lights up — everything else fades.

### Export
- **PNG** — screenshot the current view
- **Save** — persist node positions (restored on next launch)

### Ignore patterns

```bash
# Exclude directories from analysis
archview ignore tests __pycache__ venv

# List current patterns
archview ignore --list

# Remove a pattern
archview ignore --remove tests
```

## How it works

1. Collects all `.py` files (git-aware, respects `.analyzeignore`)
2. Parses each file's AST to extract imports, functions, classes
3. Builds a dependency graph with classified nodes
4. Renders it with [Cytoscape.js](https://js.cytoscape.org/) + [Dagre](https://github.com/dagrejs/dagre) layout
5. Watches for changes and re-generates every N seconds

**Zero dependencies** — pure Python stdlib. The frontend ships bundled.

## Example

The repo includes an `example_project/` (a mini e-commerce app) to try it out:

```bash
git clone https://github.com/lm17918/archview.git
cd archview
pip install -e .
archview example_project
```

## License

MIT
