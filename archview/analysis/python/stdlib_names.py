"""Stdlib module names, used to warn when a project folder shadows one."""

import sys

# Complete on 3.10+; hand-list fallback for 3.9 covers names commonly shadowed
# by project folders.
STDLIB_NAMES = getattr(
    sys,
    "stdlib_module_names",
    frozenset({
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
    }),
)
