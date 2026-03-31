"""
Build script that compiles _engine.py into a native extension.

Usage:
    pip install .                  # dev install (compiles _engine.py)
    python setup.py bdist_wheel   # build wheel with compiled .so/.pyd
"""

import sys
from setuptools import setup

try:
    # Block pythran to avoid numpy/scipy conflicts
    sys.modules.setdefault("pythran", None)
    from Cython.Build import cythonize
    ext_modules = cythonize(
        ["archview/_engine.py"],
        compiler_directives={"language_level": "3"},
    )
except ImportError:
    ext_modules = []

setup(ext_modules=ext_modules)
