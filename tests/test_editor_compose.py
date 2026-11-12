"""Tests for yate.editor_compose (assembly factories)."""

from __future__ import annotations

import ast
from pathlib import Path


def test_editor_compose_has_no_self_app() -> None:
    """editor_compose.py must not hold self.app (architecture guard).

    The module is top-level yate/; test_flow_modules_hold_no_app_handle
    scans such files. Functions take ed: Editor and never touch self.app.
    """
    src = Path("yate/editor_compose.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and node.attr == "app"
            ):
                raise AssertionError(
                    "editor_compose.py must not contain self.app"
                )


def test_editor_compose_exports_six_factories() -> None:
    """The module must define exactly the six assembly factories."""
    src = Path("yate/editor_compose.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    funcs = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    expected = {
        "_build_models",
        "_build_widgets",
        "_open_startup_target",
        "_build_pane_stack",
        "_build_key_ui",
        "_build_macro_flows",
    }
    assert funcs == expected, f"expected {expected}, got {funcs}"


def test_editor_imports_factories_from_compose() -> None:
    """editor.py must import the six factories from editor_compose."""
    src = Path("yate/editor.py").read_text(encoding="utf-8")
    assert "from yate.editor_compose import" in src
    for name in [
        "_build_models",
        "_build_widgets",
        "_open_startup_target",
        "_build_pane_stack",
        "_build_key_ui",
        "_build_macro_flows",
    ]:
        assert name in src, f"missing import: {name}"


def test_editor_compose_no_actions_no_commands_import() -> None:
    """editor_compose.py must not import actions/commands (R5 direction).

    The factories assemble widgets and flows; they never reference the
    built-in tables. R5 forbids editor -> actions/commands; the compose
    module is conceptually part of editor, so the same direction applies.
    """
    src = Path("yate/editor_compose.py").read_text(encoding="utf-8")
    assert "from yate.actions" not in src
    assert "from yate.commands" not in src
    assert "import yate.actions" not in src
    assert "import yate.commands" not in src
