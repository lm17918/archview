# ArchView

**See your codebase. Understand it. Then change it.**

ArchView gives you a live, interactive map of any Python project's architecture — right in your browser. It parses real Python (via AST, not regex), watches for changes, and updates the graph in real time.

Built for developers who vibe-code and need to stay oriented, or anyone inheriting a codebase they didn't write.

![ArchView overview — live dependency graph updating as code changes](https://raw.githubusercontent.com/lm17918/archview/main/docs/overview.gif)

![Drawing annotations — sketching boxes and labels directly on the graph](https://raw.githubusercontent.com/lm17918/archview/main/docs/drawing.gif)

## Why

You're 200 files deep in someone else's project. Or you're building fast and your own code is getting tangled. You need to _see_ the structure — what depends on what, where the entry points are, which modules are isolated.

ArchView shows you all of that in seconds, and keeps updating as you code.

## Install

```bash
pip install archview
```

Available on [PyPI](https://pypi.org/project/archview/). Pure Python, works anywhere with Python 3.9+.

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

| Color            | Meaning                                                |
| ---------------- | ------------------------------------------------------ |
| **Green**        | Entry point — modules that import but aren't imported  |
| **Blue**         | Connector — modules that both import and are imported  |
| **Red**          | Utility — leaf modules only imported by others         |
| **Gray**         | Isolated — no import relationships                     |
| **Red (bright)** | Syntax errors — files that failed to parse             |

## Features

### Live refresh

Edit your code, save — the graph updates automatically. No restart needed.

### Interactive exploration

- **Hover** a node to see its docstring, type, and exported symbols
- **Click** a node to highlight its direct dependencies
- **Double-click** to open the file in VS Code
- **Drag** nodes to rearrange the layout
- **Click folders** to collapse/expand entire packages

### Dependency highlighting

Click a node and it plus its direct dependencies light up — everything else fades. Then hover a highlighted edge to see exactly which symbols are imported across it.

### Annotations

Sketch directly on the graph to explain it. Draw boxes, add text labels, erase — useful for walking a teammate through the architecture or marking up a review. Annotations persist across launches.

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

1. Collects source files — `.py`, plus `.sh` scripts and config files (`.yaml`/`.json`) — git-aware, respects `.archviewignore`
2. Parses Python via AST (imports, functions, classes); resolves shell-script and config references too
3. Builds a dependency graph with classified nodes
4. Renders it with [Cytoscape.js](https://js.cytoscape.org/) + [Dagre](https://github.com/dagrejs/dagre) layout
5. Watches for changes and re-generates every N seconds

**Zero dependencies** — pure Python stdlib. The frontend ships bundled.

## Example

Try it on the example project (hosted on GitHub):

```bash
git clone https://github.com/lm17918/archview.git archview-demo
cd archview-demo
pip install archview
archview examples
```

## License

MIT
