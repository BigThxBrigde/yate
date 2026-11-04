"""Tests for yate.editor_dispatch (key/mouse dispatch routing)."""

from __future__ import annotations

import ast
from pathlib import Path

#: The dispatch functions extracted from the Editor class (big-module-split-2
#: wave-2; ``_execute_action`` rides along as the plan Step 5 fallback).
DISPATCH_FUNCTIONS = [
    "_cancel_mouse_state",
    "_execute_action",
    "_handle_key",
    "_handle_raw_key",
    "_insert_char",
    "_on_view_mouse",
    "_readonly_notice",
]


def test_editor_dispatch_has_no_self_app() -> None:
    """editor_dispatch.py must not contain self.app (architecture guard).

    The module is top-level yate/; ``test_flow_modules_hold_no_app_handle``
    scans it.  Functions take ``ed: Editor`` and reach the app via ``ed.app``
    (Editor is the L3 sole App holder).
    """
    src = Path("yate/editor_dispatch.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "app"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            raise AssertionError("editor_dispatch.py must not contain self.app")


def test_editor_dispatch_exports_dispatch_functions() -> None:
    """The module must define exactly the extracted dispatch functions."""
    src = Path("yate/editor_dispatch.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    funcs = [
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    ]
    assert sorted(funcs) == sorted(DISPATCH_FUNCTIONS), funcs


def test_editor_dispatch_all_lists_functions() -> None:
    """__all__ must list the dispatch functions (parsing.py precedent).

    The names are editor-private; the ``__all__`` entry marks the
    cross-module import from editor.py as deliberate (same-name alias
    form, the wave-1 measured 0-diagnostics wiring).
    """
    src = Path("yate/editor_dispatch.py").read_text(encoding="utf-8")
    assert "__all__" in src
    for name in DISPATCH_FUNCTIONS:
        assert f'"{name}"' in src, f"missing from __all__: {name}"


def test_editor_imports_dispatch_from_dispatch_module() -> None:
    """editor.py must wire the dispatch functions via same-name aliases."""
    src = Path("yate/editor.py").read_text(encoding="utf-8")
    assert "from yate.editor_dispatch import" in src
    for name in DISPATCH_FUNCTIONS:
        assert f"{name} as {name}" in src, f"missing same-name alias: {name}"
    assert "_handle_key(self, event)" in src
    assert "_handle_raw_key(self, raw)" in src
    assert "_execute_action(self, name)" in src


def test_editor_dispatch_import_cycle_is_end_safe() -> None:
    """import yate.editor must sit after the function defs (order safety).

    editor.py imports these names at its top, so the re-entrant
    ``import yate.editor`` inside editor_dispatch.py must only run once
    the functions exist.
    """
    src = Path("yate/editor_dispatch.py").read_text(encoding="utf-8")
    assert "import yate.editor" in src
    first_def = src.index("def _handle_key")
    last_import = src.rindex("import yate.editor")
    assert last_import > first_def


def test_editor_dispatch_no_table_imports() -> None:
    """editor_dispatch.py must not import the action/command tables (R5)."""
    src = Path("yate/editor_dispatch.py").read_text(encoding="utf-8")
    assert "from yate.actions" not in src
    assert "from yate.commands" not in src
    assert "import yate.actions" not in src
    assert "import yate.commands" not in src
