import argparse
import importlib.resources
import sys
import threading
from pathlib import Path

from archview.graph import generate_graph
from archview.server import make_server

# Known stdlib module names that are commonly shadowed by project folders
_STDLIB_NAMES = {
    "abc", "ast", "asyncio", "base64", "calendar", "collections", "copy",
    "csv", "ctypes", "datetime", "decimal", "difflib", "email", "enum",
    "fractions", "functools", "glob", "gzip", "hashlib", "html", "http",
    "importlib", "inspect", "io", "itertools", "json", "logging", "math",
    "multiprocessing", "numbers", "operator", "os", "pathlib", "pickle",
    "platform", "pprint", "profile", "queue", "random", "re", "secrets",
    "select", "shelve", "shutil", "signal", "socket", "sqlite3",
    "statistics", "string", "struct", "subprocess", "sys", "tempfile",
    "test", "textwrap", "threading", "time", "timeit", "token", "tokenize",
    "trace", "traceback", "types", "typing", "unittest", "urllib", "uuid",
    "warnings", "weakref", "xml", "xmlrpc", "zipfile", "zipimport",
}


def _check_stdlib_shadowing(project_dir: Path):
    """Warn if any folder in the project shadows a Python stdlib module."""
    shadowed = []
    for item in project_dir.iterdir():
        if item.is_dir() and item.name in _STDLIB_NAMES:
            init = item / "__init__.py"
            if init.exists() or any(item.glob("*.py")):
                shadowed.append(item.name)
    if shadowed:
        print(f"\n  WARNING: These project folders shadow Python stdlib modules:")
        for name in sorted(shadowed):
            print(f"    - {name}/")
        print(f"  This may cause crashes in archview or pip.")
        print(f"  Consider renaming them.\n")

IGNORE_FILENAME = ".analyzeignore"


def _ignore_file_path(project_dir: Path) -> Path:
    return project_dir / IGNORE_FILENAME


def _read_patterns(ignore_file: Path) -> list[str]:
    if not ignore_file.exists():
        return []
    lines = ignore_file.read_text().splitlines()
    return [l for l in lines if l.strip() and not l.strip().startswith("#")]


def _cmd_ignore(args):
    project_dir = Path(args.project_dir).resolve()
    ignore_file = _ignore_file_path(project_dir)

    if args.list:
        patterns = _read_patterns(ignore_file)
        if not patterns:
            print("No patterns in .analyzeignore")
        else:
            print(f"{ignore_file}:")
            for p in patterns:
                print(f"  {p}")
        return

    if args.remove:
        if not ignore_file.exists():
            print("No .analyzeignore file found")
            return
        lines = ignore_file.read_text().splitlines()
        new_lines = [l for l in lines if l.strip() != args.remove]
        if len(new_lines) == len(lines):
            print(f"Pattern not found: {args.remove}")
            return
        ignore_file.write_text("\n".join(new_lines) + "\n")
        print(f"Removed: {args.remove}")
        return

    if not args.patterns:
        print("Usage: archview ignore <pattern> [pattern ...]")
        print("       archview ignore --list")
        print("       archview ignore --remove <pattern>")
        return

    existing = _read_patterns(ignore_file)
    added = []
    for pattern in args.patterns:
        if pattern in existing:
            print(f"Already ignored: {pattern}")
        else:
            added.append(pattern)

    if added:
        write_header = not ignore_file.exists() or ignore_file.stat().st_size == 0
        with ignore_file.open("a") as f:
            if write_header:
                f.write("# Folders/patterns to exclude from analysis (one per line)\n")
            for p in added:
                f.write(p + "\n")
        for p in added:
            print(f"Added: {p}")


def _cmd_serve(args):
    project_dir = Path(args.project_dir).resolve()
    data_dir = project_dir / ".archview"
    data_dir.mkdir(exist_ok=True)

    ignore_file = _ignore_file_path(project_dir)
    if not ignore_file.exists():
        ignore_file = None

    static_dir = Path(str(importlib.resources.files("archview"))) / "static"
    graph_path = data_dir / "graph.json"

    _check_stdlib_shadowing(project_dir)
    print("Running initial analysis...")
    generate_graph(project_dir, ignore_file, graph_path)
    print(f"Graph generated. Open http://localhost:{args.port}")

    stop_event = threading.Event()

    def watcher():
        while not stop_event.wait(args.interval):
            try:
                generate_graph(project_dir, ignore_file, graph_path)
            except Exception:
                pass

    threading.Thread(target=watcher, daemon=True).start()

    server = make_server("127.0.0.1", args.port, static_dir, data_dir, project_dir, args.interval)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("Press Ctrl+C to stop\n")
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1)
    except KeyboardInterrupt:
        stop_event.set()
        server.shutdown()
        print("\nStopped.")


def main():
    # If first positional arg is not a known subcommand, inject "serve"
    # so that `archview example_project` works as `archview serve example_project`
    known_commands = {"ignore", "serve"}
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands and not sys.argv[1].startswith("-"):
        sys.argv.insert(1, "serve")

    parser = argparse.ArgumentParser(
        prog="archview",
        description="Interactive live architecture viewer for Python projects",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- ignore subcommand ---
    ignore_parser = subparsers.add_parser("ignore", help="Manage .analyzeignore patterns")
    ignore_parser.add_argument("patterns", nargs="*", help="Patterns to add")
    ignore_parser.add_argument("--list", "-l", action="store_true", help="List current patterns")
    ignore_parser.add_argument("--remove", "-r", metavar="PATTERN", help="Remove a pattern")
    ignore_parser.add_argument("--project-dir", default=".", metavar="DIR")

    # --- serve (default) ---
    serve_parser = subparsers.add_parser("serve", help="Start the live architecture viewer")
    serve_parser.add_argument("project_dir", nargs="?", default=".")
    serve_parser.add_argument("--port", "-p", type=int, default=9090,
                              choices=range(1, 65536), metavar="PORT")
    serve_parser.add_argument("--interval", type=int, default=10,
                              choices=range(1, 3601), metavar="SEC",
                              help="Graph refresh interval in seconds (default: 10)")

    args = parser.parse_args()

    if args.command == "ignore":
        _cmd_ignore(args)
    elif args.command == "serve":
        _cmd_serve(args)
    else:
        # No args at all → default to serve current dir
        sys.argv.insert(1, "serve")
        args = parser.parse_args()
        _cmd_serve(args)
