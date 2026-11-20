"""Structural guards for the workspace ignore subsystem extraction.

Pins the contract of the ``workspace_ignores`` L0 module: the ignore
primitives are *defined* there (not re-imported from
``yate.services.workspace``), ``Workspace._is_ignored`` stays a thin
delegation over :class:`IgnoreIndex`, and the ``IGNORED_NAMES``
re-export from ``yate.services.workspace`` keeps resolving for
``explorer.py`` and existing tests.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import FunctionType
from typing import cast

from yate.services import workspace_ignores
from yate.services.workspace import IGNORED_NAMES, Workspace

_REPO_ROOT = Path(__file__).resolve().parents[1]
_IGNORES_MODULE_PATH = (
    _REPO_ROOT / "yate" / "services" / "workspace_ignores.py"
)

_PRIMITIVE_NAMES = {"_IgnorePattern", "_parse_ignore", "_anchored_match"}


def _imported_names(tree: ast.Module) -> set[str]:
    """Collect the plain (non-aliased) names imported by a module."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return names


def test_ignore_primitives_are_defined_in_the_dedicated_module() -> None:
    """_IgnorePattern / _parse_ignore / _anchored_match live in the module.

    The three primitives must be defined in ``workspace_ignores.py``
    itself -- merely re-importing them from ``workspace.py`` would leave
    the subsystem un-extracted.
    """
    tree = ast.parse(
        _IGNORES_MODULE_PATH.read_text(encoding="utf-8"),
        filename=str(_IGNORES_MODULE_PATH),
    )
    defined = {
        node.name
        for node in tree.body
        if isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }
    assert _PRIMITIVE_NAMES <= defined
    assert "IgnoreIndex" in defined
    assert not (_PRIMITIVE_NAMES & _imported_names(tree))


def test_workspace_is_ignored_is_a_thin_delegation() -> None:
    """Workspace._is_ignored stays a <=5-line delegation to IgnoreIndex."""
    source = inspect.getsource(cast(FunctionType, getattr(Workspace, "_is_ignored")))
    tree = ast.parse(textwrap.dedent(source))
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_is_ignored"
    )
    statements = fn.body[1:]  # drop the docstring expression
    assert len(statements) == 1
    assert isinstance(statements[0], ast.Return)


def test_ignored_names_reexport_from_workspace_still_resolves() -> None:
    """``from yate.services.workspace import IGNORED_NAMES`` still works.

    The re-export must hand out the very same object the dedicated
    module owns (a copy would silently fork the hidden-name set).
    """
    assert IGNORED_NAMES is workspace_ignores.IGNORED_NAMES
