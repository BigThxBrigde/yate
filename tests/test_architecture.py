"""Architecture guards: the narrow-interface rules must not regress.

These tests enforce the boundaries documented in
``.trae/rules/architecture-boundaries.md`` (R1-R11) and
``.trae/documents/app-layering-refactoring-plans/README.md`` (section 4,
"依赖规则（硬性）"):

* **R1** ``YateApp`` is the composition root: only ``cli.py`` imports
  ``yate.app``.
* **R2** no one-size-fits-all ``AppProtocol``, no ``interfaces.py``, and no
  new ``Protocol`` class beyond the frozen whitelist.
* **R3** ``editor_view/*`` widgets never import ``yate.editor`` / ``yate.app``
  (they receive concrete collaborators or callbacks); the ``app_features``
  package deleted in Plan D stays deleted.
* **R4** the UI-free layers (``keymaps/*``, ``services/*``, ``session.py``,
  ``registries.py``) never import ``editor_view``.
* **R5** ``editor.py`` never imports the built-in tables ``actions.py`` /
  ``commands.py`` -- they import the editor, so the reverse is a cycle.
* **R6** no ``TYPE_CHECKING`` blocks; concrete objects replace type-only
  imports.
* **R11** the two L3 collaborator modules that drive widgets
  (``completion.py`` / ``prompt_completion.py``) keep that coupling frozen
  and never look upward.
* **Naming** (unnumbered guard, rules section 6): no ``*Feature`` / ``*Host``
  / ``*Ops`` / ``*Delegate`` identifiers and no ``AppProtocol``.  ``PaneHost``
  is a real Textual container widget (not a protocol / thin delegate) and is
  whitelisted; ``*Manager`` and flow-level ``*Controller`` names stay allowed.
* **Panes** the pane tree model is L1 state, not a widget-package type layer:
  ``session.py`` owns ``Leaf`` / ``Split`` / ``ViewState`` and the tree
  operations, ``editor_view`` imports them and never re-exports them, and
  ``editor_view/pane_types.py`` stays deleted.

* **R7** the shell loads the built-in tables: ``YateApp.__init__`` calls
  ``populate(editor.actions, editor)`` / ``register_commands(editor.commands,
  editor)`` and is the only module importing ``actions.py`` / ``commands.py``.

R8 (shared state as concrete objects), R9 (widget ids) and R10 (one dispatch
per key) are design constraints reviewed by hand and exercised by the Plan F
smoke checklist; they have no guard here yet.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
YATE = PROJECT / "yate"

_SELF = Path(__file__).resolve()

#: Only the CLI entry point may import the application class (R1).
APP_IMPORTERS_ALLOWED = {"cli.py"}

#: Modules no layer below the shell may look back up at (R3 / R4).
UPWARD_MODULES = ("yate.editor", "yate.app")

#: The frozen ``Protocol`` whitelist (R2): ``PaneRegistry`` breaks the
#: ``PaneHost`` <-> ``EditorView`` construction cycle, ``SyntaxBackend`` and
#: the ``_Ts*`` structural types are leaf-package types that predate this
#: refactoring.  Any other ``Protocol`` class fails the build.
ALLOWED_PROTOCOLS = {
    "editor_view/editor.py": {"PaneRegistry"},
    "editor_syntax/engine.py": {"SyntaxBackend"},
    "editor_syntax/ts_backend/backend.py": {"_TsPoint", "_TsNode"},
}

#: Pure logic packages / modules that must run without any widget (R4).
UI_FREE_PACKAGES = ("keymaps", "services")
UI_FREE_FILES = ("session.py", "registries.py")

#: L3 collaborator modules that do drive a few widget types by design: they
#: still may not depend upward, and their ``editor_view`` coupling is frozen
#: here, so a new widget import fails until it is justified (R4).
UI_FROZEN_FILES = {
    "prompt_completion.py": {
        "yate.editor_view",
        "yate.editor_view.theme",
    },
    "completion.py": {
        "yate.editor_view",
        "yate.editor_view.theme",
        "yate.editor_view.commandline",
        "yate.editor_view.completion",
        "yate.editor_view.editor",
        "yate.editor_view.panes",
    },
}

#: The built-in tables import the editor; the editor must not import them (R5).
EDITOR_FORBIDDEN_IMPORTS = ("yate.actions", "yate.commands")

#: The built-in tables the shell registers into the editor's registries (R7).
BUILTIN_TABLE_MODULES = ("yate.actions", "yate.commands")

#: Banned identifier suffixes (R7): no protocol-ish / thin-delegate naming.
#: ``PaneHost`` is the Textual widget container in ``editor_view/panes.py``,
#: so it is whitelisted; ``*Manager`` and ``*Controller`` remain legal.
BANNED_SUFFIXES = ("Feature", "Host", "Ops", "Delegate")
BANNED_SUFFIX_WHITELIST = {"PaneHost"}

#: Banned identifier names (R2 / R7).
BANNED_NAMES = {"AppProtocol"}


def _python_files() -> list[Path]:
    """Every project Python file (yate + tests + tools), excluding this one."""
    out: list[Path] = []
    for base in (YATE, PROJECT / "tests", PROJECT / "tools"):
        out.extend(
            p for p in base.rglob("*.py")
            if "__pycache__" not in p.parts and p != _SELF
        )
    return out


def _yate_files() -> list[Path]:
    """Every ``yate/`` Python file, excluding this one."""
    return [
        p for p in YATE.rglob("*.py")
        if "__pycache__" not in p.parts and p != _SELF
    ]


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


def _imports_upward(module: str) -> bool:
    """Whether *module* is ``yate.editor`` / ``yate.app`` or a submodule."""
    return any(
        module == target or module.startswith(target + ".")
        for target in UPWARD_MODULES
    )


def _protocol_classes(path: Path) -> set[str]:
    """Names of every class in *path* whose bases include ``Protocol`` (R2)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else ""
            if name == "Protocol":
                out.add(node.name)
    return out


def _identifiers(path: Path) -> set[str]:
    """Every identifier *name* defined or referenced in a module (R7)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        elif isinstance(node, ast.alias):
            out.add(node.name.rsplit(".", 1)[-1])
    return out


def test_no_app_protocol() -> None:
    """The one-size-fits-all ``AppProtocol`` must not come back (R2 / R7)."""
    for path in _python_files():
        assert "AppProtocol" not in path.read_text(encoding="utf-8"), path


def test_interfaces_module_is_gone() -> None:
    """No central interface module: ``yate/interfaces.py`` stays deleted (R2)."""
    assert not (YATE / "interfaces.py").exists()


def test_no_new_protocols() -> None:
    """Shared state travels as concrete objects: no new ``Protocol`` beyond
    the frozen whitelist (R2)."""
    for path in _yate_files():
        key = path.relative_to(YATE).as_posix()
        for name in _protocol_classes(path):
            assert name in ALLOWED_PROTOCOLS.get(key, set()), (key, name)


def test_no_type_checking() -> None:
    """Type-only import blocks are banned; local protocols replace them (R6)."""
    for path in _python_files():
        assert "TYPE_CHECKING" not in path.read_text(encoding="utf-8"), path


def test_only_cli_imports_app() -> None:
    """``YateApp`` is the composition root; lower layers never import it (R1)."""
    for path in _yate_files():
        if path.name == "app.py" or path.name in APP_IMPORTERS_ALLOWED:
            continue
        assert "yate.app" not in _yate_imports(path), path


def test_editor_view_does_not_import_upward() -> None:
    """Widgets take concrete collaborators or callbacks: ``editor_view/*``
    never imports ``yate.editor`` / ``yate.app`` (R3)."""
    for path in (YATE / "editor_view").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for module in _yate_imports(path):
            assert not _imports_upward(module), (path, module)


def test_app_features_package_is_gone() -> None:
    """The thin-delegate ``app_features`` layer stays deleted (R3 / R7).

    The whole directory must be gone, not just ``__init__.py``: a leftover
    directory (a stale ``__pycache__`` is enough) is still importable as an
    empty *namespace package*, which hides the removal and masks import
    regressions.
    """
    assert not (YATE / "app_features").exists()


def test_keymaps_services_and_models_stay_ui_free() -> None:
    """``keymaps`` / ``services`` / ``session.py`` / ``registries.py`` run
    without a mounted app: they must not import ``editor_view`` (R4)."""
    targets: list[Path] = []
    for package in UI_FREE_PACKAGES:
        targets.extend(
            p for p in (YATE / package).rglob("*.py")
            if "__pycache__" not in p.parts
        )
    targets.extend(YATE / name for name in UI_FREE_FILES)
    for path in targets:
        for module in _yate_imports(path):
            assert not module.startswith("yate.editor_view"), (path, module)


def test_collaborators_keep_widget_coupling_frozen() -> None:
    """``completion.py`` / ``prompt_completion.py`` are editor-level
    collaborators: they may drive their known widgets but never depend
    upward, and a new ``editor_view`` import must be added here first (R11)."""
    for name, allowed in UI_FROZEN_FILES.items():
        path = YATE / name
        for module in _yate_imports(path):
            assert not _imports_upward(module), (path, module)
            if module.startswith("yate.editor_view"):
                assert module in allowed, (path, module)


def test_editor_does_not_import_action_tables() -> None:
    """``actions.py`` / ``commands.py`` import the editor, so ``editor.py``
    must not import them back -- that would close an import cycle (R5)."""
    path = YATE / "editor.py"
    for module in _yate_imports(path):
        assert not any(
            module == banned or module.startswith(banned + ".")
            for banned in EDITOR_FORBIDDEN_IMPORTS
        ), (path, module)


def test_shell_loads_the_builtin_tables() -> None:
    """Only the shell loads the built-in tables into the editor (R7).

    ``actions.py`` / ``commands.py`` import the editor (R5), so the shell is
    the one place allowed to import them; it must register both tables into
    the editor's empty registries in ``YateApp.__init__``.
    """
    source = (YATE / "app.py").read_text(encoding="utf-8")
    assert "populate(self.editor.actions, self.editor)" in source
    assert "register_commands(self.editor.commands, self.editor)" in source
    importers = sorted(
        path.relative_to(YATE).as_posix()
        for path in _yate_files()
        if any(module in BUILTIN_TABLE_MODULES for module in _yate_imports(path))
    )
    assert importers == ["app.py"], importers


def test_no_banned_identifier_names() -> None:
    """No protocol-ish / thin-delegate naming: ``*Feature``, ``*Host``,
    ``*Ops``, ``*Delegate`` and ``AppProtocol`` are banned (naming guard,
    rules section 6 -- not R7, which is the shell's table loading).
    ``PaneHost`` is a Textual container widget and whitelisted."""
    for path in _yate_files():
        for name in _identifiers(path):
            assert name not in BANNED_NAMES, (path, name)
            if name.endswith(BANNED_SUFFIXES):
                assert name in BANNED_SUFFIX_WHITELIST, (path, name)


def test_pane_model_lives_in_l1_session() -> None:
    """The pane tree model is L1 state, not a widget-package type layer:
    ``session.py`` owns it; ``editor_view`` imports it, never re-exports it."""
    source = (YATE / "session.py").read_text(encoding="utf-8")
    for name in ("class Leaf", "class Split", "class ViewState", "def find_leaf"):
        assert name in source, name
    assert not (YATE / "editor_view" / "pane_types.py").exists()
    panes = (YATE / "editor_view" / "panes.py").read_text(encoding="utf-8")
    assert "backward compatibility" not in panes
