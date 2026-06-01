"""ArchView: a live, interactive architecture map for Python projects."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("archview")
except PackageNotFoundError:
    __version__ = "0.0.0"
