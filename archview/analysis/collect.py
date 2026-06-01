"""Gather project source files (git-aware) and map them to module ids."""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path, PurePosixPath


def _collect_files_by_ext(
    project_dir: Path, ignore_file: Path | None, ext: str
) -> list[str]:
    """Return sorted relative paths with given extension (git-aware, ignore-safe)."""
    project_dir = Path(project_dir)
    glob = f"*{ext}"

    try:
        result = subprocess.run(
            ["git", "ls-files", glob],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        found = set(result.stdout.strip().splitlines())

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", glob],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        found.update(untracked.stdout.strip().splitlines())

    except subprocess.CalledProcessError:
        found = set()
        skip = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in files:
                if f.endswith(ext):
                    rel = os.path.relpath(os.path.join(root, f), project_dir)
                    found.add(rel)

    # Keep only files that exist on disk — drops index entries deleted from the
    # working tree without `git ls-files --deleted`, which misreports in subdirs.
    found = sorted(f for f in found if f and (project_dir / f).is_file())

    if ignore_file and Path(ignore_file).exists():
        patterns = []
        for line in Path(ignore_file).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

        def matches_any(filepath: str) -> bool:
            p = PurePosixPath(filepath)
            dir_parts = p.parts[:-1]
            name_parts = list(p.parts) + ([p.stem] if p.suffix else [])
            for pattern in patterns:
                # Trailing slash = directory-only (gitignore-style), so 'build/'
                # ignores the build/ dir but not a file named build.py.
                if pattern.endswith("/"):
                    folder = pattern.rstrip("/")
                    if any(fnmatch.fnmatch(part, folder) for part in dir_parts):
                        return True
                elif any(fnmatch.fnmatch(part, pattern) for part in name_parts):
                    return True
            return False

        found = [f for f in found if not matches_any(f)]

    return found


def collect_py_files(project_dir: Path, ignore_file: Path | None) -> list[str]:
    return _collect_files_by_ext(project_dir, ignore_file, ".py")


def _build_module_index(
    project_dir: Path, files: list[str], ext: str = ".py", keep_ext: bool = False
):
    """Map relative paths to module ids and absolute paths.

    When keep_ext is True the extension is baked into the id using '_' so that
    'config.yaml' becomes 'config_yaml' instead of colliding with 'config.py'.
    """
    modules = {}  # mod -> absolute path
    module_rel = {}  # mod -> relative path
    for rel in files:
        full = project_dir / rel
        if not full.is_file():
            continue
        if keep_ext:
            mod = rel.replace("/", ".").replace(ext, "_" + ext.lstrip("."))
        else:
            mod = rel.replace("/", ".").removesuffix(ext)
        if mod.endswith(".__init__"):
            mod = mod[:-9]
        if not mod:
            continue
        modules[mod] = full
        module_rel[mod] = rel
    return modules, module_rel
