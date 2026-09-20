"""Packaging helpers for the standalone executables (``python -m tools.pack``).

Complements the PyInstaller specs in ``pack/``: everything that has to be
generated *before* a build lives here, so ``pack/`` stays a pure spec folder.

Entry point: ``python -m tools.pack --help``.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
