"""Architecture guards: the narrow-interface rules must not regress.

These tests enforce the boundaries documented in
``.trae/rules/architecture-boundaries.md``: no global ``AppProtocol``, no
``TYPE_CHECKING`` blocks, ``YateApp`` stays the composition root that only
the CLI imports, and the feature / widget / service layers keep their
import directions (all cycles stay impossible by construction).
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
YATE = PROJECT / "yate"

_SELF = Path(__file__).resolve()

#: Only the CLI entry point may import the application class (R1).
APP_IMPORTERS_ALLOWED = {"cli.py"}

#: What ``app_features`` may import from ``editor_view`` (R3): the package
#: helpers plus the widgets that do not depend back on the feature layer.
ALLOWED_FEATURE_VIEW_IMPORTS = {
    "yate.editor_view",
    "yate.editor_view.theme",
    "yate.editor_view.icons",
    "yate.editor_view.keys",
    "yate.editor_view.pane_types",
    "yate.editor_view.completion",
    "yate.editor_view.editor",
    "yate.editor_view.manual",
}


def _python_files() -> list[Path]:
    """Every project Python file (yate + tests + tools), excluding this one."""
    out: list[Path] = []
    for base in (YATE, PROJECT / "tests", PROJECT / "tools"):
        out.extend(
            p for p in base.rglob("*.py")
            if "__pycache__" not in p.parts and p != _SELF
        )
    return out


def _yate_imports(path: Path) -> list[str]:
    """Every ``yate.*`` module *path* imports, at any nesting depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "yate" or node.module.startswith("yate."):
                out.append(node.module)
        elif isinstance(node, ast.Import):
            out.extend(a.name for a in node.names if a.name.startswith("yate"))
    return out


def test_no_app_protocol() -> None:
    """The one-size-fits-all ``AppProtocol`` must not come back (R2)."""
    for path in _python_files():
        assert "AppProtocol" not in path.read_text(encoding="utf-8"), path


def test_interfaces_module_is_gone() -> None:
    assert not (YATE / "interfaces.py").exists()


def test_no_type_checking() -> None:
    """Type-only import blocks are banned; local protocols replace them (R6)."""
    for path in _python_files():
        assert "TYPE_CHECKING" not in path.read_text(encoding="utf-8"), path


def test_only_cli_imports_app() -> None:
    """``YateApp`` is the composition root; lower layers never import it (R1)."""
    for path in YATE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.name == "app.py" or path.name in APP_IMPORTERS_ALLOWED:
            continue
        assert "yate.app" not in _yate_imports(path), path


def test_features_import_only_allowed_view_modules() -> None:
    """``app_features`` drives widgets through protocols, never by importing
    the widget modules that depend back on the feature layer (R3)."""
    for path in (YATE / "app_features").rglob("*.py"):
        for module in _yate_imports(path):
            if not module.startswith("yate.editor_view"):
                continue
            assert module in ALLOWED_FEATURE_VIEW_IMPORTS, (path, module)


def test_keymaps_and_services_stay_ui_free() -> None:
    """``keymaps`` and ``services`` run without a mounted app: they must not
    import the ``editor_view`` layer (R5)."""
    for package in ("keymaps", "services"):
        for path in (YATE / package).rglob("*.py"):
            for module in _yate_imports(path):
                assert not module.startswith("yate.editor_view"), (path, module)
