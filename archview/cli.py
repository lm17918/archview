"""Command-line entry point: argument parsing and the serve/ignore commands."""

import argparse
import hashlib
import importlib.resources
import os
import signal
import sys
import threading
from pathlib import Path

from archview.analysis import generate_graph
from archview.analysis.python.stdlib_names import STDLIB_NAMES
from archview.ignore import cmd_ignore, ensure_default_ignore_file
from archview.interface import make_server
from archview.watch import LiveBroker, tree_signature


def _check_stdlib_shadowing(project_dir: Path) -> None:
    shadowed = []
    for item in project_dir.iterdir():
        if item.is_dir() and item.name in STDLIB_NAMES:
            init = item / "__init__.py"
            if init.exists() or any(item.glob("*.py")):
                shadowed.append(item.name)
    if shadowed:
        print("\n  WARNING: These project folders shadow Python stdlib modules:")
        for name in sorted(shadowed):
            print(f"    - {name}/")
        print("  This may cause crashes in archview or pip.")
        print("  Consider renaming them.\n")


PORT_SCAN_RANGE = 100


def _bind_free_port(
    start, static_dir, data_dir, project_dir, interval, ignore_file, broker
):
    """Bind the first free port from `start`, scanning up to PORT_SCAN_RANGE."""
    for port in range(start, start + PORT_SCAN_RANGE):
        try:
            server = make_server(
                "127.0.0.1",
                port,
                static_dir,
                data_dir,
                project_dir,
                interval,
                ignore_file,
                broker,
            )
        except OSError:
            continue
        return server, port
    return None, None


def _project_cache_dir(project_dir: Path) -> Path:
    """Per-project cache dir outside the repo (XDG-style)."""
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "archview"
    digest = hashlib.sha1(str(project_dir).encode("utf-8")).hexdigest()[:10]
    return base / f"{project_dir.name}-{digest}"


def _cmd_serve(args) -> None:
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        print(f"Not a directory: {args.project_dir}")
        sys.exit(1)
    data_dir = _project_cache_dir(project_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    ignore_file = ensure_default_ignore_file(project_dir)
    static_dir = Path(str(importlib.resources.files("archview.interface"))) / "static"
    graph_path = data_dir / "graph.json"

    _check_stdlib_shadowing(project_dir)
    print("Running initial analysis...")
    generate_graph(project_dir, ignore_file, graph_path)

    broker = LiveBroker()
    server, port = _bind_free_port(
        args.port, static_dir, data_dir, project_dir, args.interval, ignore_file, broker
    )
    if server is None:
        print(f"No free port in {args.port}-{args.port + PORT_SCAN_RANGE - 1}")
        sys.exit(1)
    print(f"Graph generated. Open http://localhost:{port}")

    stop_event = threading.Event()

    def watcher():
        last_sig = tree_signature(project_dir, ignore_file)
        while not stop_event.wait(args.interval):
            try:
                sig = tree_signature(project_dir, ignore_file)
                if sig == last_sig:
                    continue
                last_sig = sig
                generate_graph(project_dir, ignore_file, graph_path)
                broker.bump()
            except Exception:
                pass

    threading.Thread(target=watcher, daemon=True).start()

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("Press Ctrl+C to stop\n")

    shutdown_requested = threading.Event()

    def _request_shutdown(signum, frame):
        shutdown_requested.set()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGHUP, _request_shutdown)

    try:
        while server_thread.is_alive() and not shutdown_requested.is_set():
            server_thread.join(timeout=1)
    except KeyboardInterrupt:
        pass
    stop_event.set()
    server.shutdown()
    print("\nStopped.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archview",
        description="Interactive live architecture viewer for Python projects",
    )
    subparsers = parser.add_subparsers(dest="command")

    ignore_parser = subparsers.add_parser(
        "ignore", help="Manage .archviewignore patterns"
    )
    ignore_parser.add_argument("patterns", nargs="*", help="Patterns to add")
    ignore_parser.add_argument(
        "--list", "-l", action="store_true", help="List current patterns"
    )
    ignore_parser.add_argument(
        "--remove", "-r", metavar="PATTERN", help="Remove a pattern"
    )
    ignore_parser.add_argument("--project-dir", default=".", metavar="DIR")

    serve_parser = subparsers.add_parser(
        "serve", help="Start the live architecture viewer"
    )
    serve_parser.add_argument("project_dir", nargs="?", default=".")
    serve_parser.add_argument(
        "--port", "-p", type=int, default=8080, choices=range(1, 65536), metavar="PORT"
    )
    serve_parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        metavar="SEC",
        help="Filesystem scan interval in seconds; lower = snappier (default: 0.5)",
    )
    return parser


def main() -> None:
    # If first positional arg is not a known subcommand, inject "serve"
    # so that `archview example_project` works as `archview serve example_project`
    known_commands = {"ignore", "serve"}
    if (
        len(sys.argv) > 1
        and sys.argv[1] not in known_commands
        and not sys.argv[1].startswith("-")
    ):
        sys.argv.insert(1, "serve")

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "ignore":
        cmd_ignore(args)
    elif args.command == "serve":
        _cmd_serve(args)
    else:
        # No args at all -> default to serve current dir
        sys.argv.insert(1, "serve")
        args = parser.parse_args()
        _cmd_serve(args)
