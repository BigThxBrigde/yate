"""Architecture guards: the narrow-interface rules must not regress.

These tests enforce the boundaries documented in
``.trae/rules/architecture-boundaries.md`` (R1-R12) and
``.trae/documents/app-layering-refactoring-plans/overview.md`` (section 4,
"dependency rules (hard)"):

* **R1** ``YateApp`` is the composition root: only ``cli.py`` imports
  ``yate.app``.
* **R2** no one-size-fits-all ``AppProtocol``, no ``interfaces.py``, and no
  new ``Protocol`` class beyond the frozen whitelist.
* **R3** ``editor_view/*`` widgets never import ``yate.editor`` / ``yate.app``
  (they receive concrete collaborators or callbacks); the ``app_features``
  package deleted in Plan D stays deleted.
* **R4** the UI-free layers (``keymaps/*``, ``services/*``, ``session.py``,
  ``registries.py``) never import ``editor_view``.  ``editor_core`` joined
  with the diff tool (wave-3): the L0 engine package (buffer / document /
  diff / ...) is scanned by the same UI-free guards.
* **R5** ``editor.py`` never imports the built-in tables ``actions.py`` /
  ``commands.py`` -- they import the editor, so the reverse is a cycle.
* **R6** no ``TYPE_CHECKING`` blocks; concrete objects replace type-only
  imports.
* **R11** the L3 collaborator modules that drive widgets
  (``flows/completion_flows.py`` / ``flows/prompt_completion.py`` /
  ``flows/lsp_sync.py`` / ``flows/shell_flows.py`` / ``flows/overlay_flows.py``
  / ``flows/prompt_flows.py``) keep that coupling frozen and never look
  upward.
* **Naming** (unnumbered guard, rules section 6): no ``*Feature`` / ``*Host``
  / ``*Ops`` / ``*Delegate`` identifiers and no ``AppProtocol``.  ``PaneHost``
  is a real Textual container widget (not a protocol / thin delegate) and is
  whitelisted.  UI flow modules are named by duty: ``*Flows`` for
  multi-step orchestration, verb names like ``LspSync`` for sync adapters;
  new ``*Controller`` names are banned.
* **Callback aliases** callback type aliases are PEP 695 ``type`` statements
  (``type OutputFn = Callable[[bytes], None]``), never ``X = Callable[...]``
  assignments and never ``typing.TypeAlias`` / ``TypeAliasType`` (issue
  IKJUWP): the statement form is lazily evaluated (it may name a class defined
  further down the module), reads as a declaration at the definition site, and
  the ``typing`` aliases add nothing on 3.12.  The guard covers module- and
  class-level bindings -- where aliases live; a one-off callback *attribute*
  inside a function body, and a data table whose *elements* are callbacks
  (``dict[str, Callable[...]]``), are not alias definitions and stay inline.
* **Panes** the pane tree model is L1 state, not a widget-package type layer:
  ``session.py`` owns ``Leaf`` / ``Split`` / ``ViewState`` and the tree
  operations, ``editor_view`` imports them and never re-exports them, and
  ``editor_view/pane_types.py`` stays deleted.
* **Logging** ``log.*`` calls use lazy ``%`` formatting, never f-strings
  (coding-style 4.6): arguments must not be evaluated while the level is off.
* **R12** logging goes through the tracing singleton: no ``self.log`` /
  ``self.app.log`` devtools-channel access anywhere, and no ``textual.app``
  import in the UI-free L0 modules (devtools visibility is the L4
  ``TextualHandler`` bridge's job, not a per-module import).

* **R13** widgets own their theme: L3 ``editor.py`` never paints widget
  styles or forwards theme updates, and scrollbar renderers are injected
  per widget (``apply_slim_scrollbars``), never class-level patched.

* **File size** (A11, rules section 3.7): a ``yate/`` file beyond 800
  lines must be split or registered in the size-exemption list
  (``SIZE_EXEMPT_FILES``), which mirrors the rule text.

* **Capability injection** (semantic capability injection, issue IKJB0Q):
  the L3 flow modules never hold the App handle -- verbs are injected as
  bound methods (``spawn=app.run_worker``, ``push_screen=app.push_screen``)
  and state queries as semantic callables owned by ``editor.py``, the one
  L3 ``App[None]`` holder and capability distributor.  Imprecise
  ``App[Any]`` / ``App[object]`` annotations are banned everywhere.

* **R7** the shell loads the built-in tables: ``YateApp.__init__`` calls
  ``populate(editor.actions, editor)`` / ``register_commands(editor.commands,
  editor)`` and is the only module importing ``actions.py`` / ``commands.py``.

R8 (shared state as concrete objects), R9 (widget ids) and R10 (one dispatch
per key) are design constraints reviewed by hand and exercised by the Plan F
smoke checklist; they have no guard here yet.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import re
from pathlib import Path

import pytest

PROJECT: Path = Path(__file__).resolve().parent.parent
YATE: Path = PROJECT / "yate"

_SELF: Path = Path(__file__).resolve()

#: Only the CLI entry point may import the application class (R1).
APP_IMPORTERS_ALLOWED: set[str] = {"cli.py"}

#: Modules no layer below the shell may look back up at (R3 / R4).
UPWARD_MODULES: tuple[str, ...] = ("yate.editor", "yate.app")

#: The frozen ``Protocol`` whitelist (R2): ``PaneRegistry`` breaks the
#: ``PaneHost`` <-> ``EditorView`` construction cycle, ``SyntaxBackend`` and
#: the ``_Ts*`` structural types are leaf-package types that predate this
#: refactoring.  Any other ``Protocol`` class fails the build.
ALLOWED_PROTOCOLS: dict[str, set[str]] = {
    "editor_view/editor.py": {"PaneRegistry"},
    "editor_syntax/engine.py": {"SyntaxBackend"},
    "editor_syntax/ts_backend/backend.py": {"_TsPoint", "_TsNode"},
}

#: Pure logic packages / modules that must run without any widget (R4).
#: ``config.py`` joined in N30: it used to lazily import editor_view.theme
#: inside ``load_config`` (the only L0->L2 edge; theme support is now
#: injected as callbacks by the L4 caller).  ``keyproto`` joined with the
#: Windows chord driver: a pure L0 leaf that must never reach editor_view.
#: ``editor_core`` joined with the diff tool (wave-3): the whole L0 engine
#: package (buffer / document / diff / ...) stays widget-free.
UI_FREE_PACKAGES: tuple[str, ...] = (
    "keymaps",
    "services",
    "keyproto",
    "editor_sprites",
    "editor_core",
)
UI_FREE_FILES: tuple[str, ...] = ("session.py", "registries.py", "config.py", "yaterc.py")

#: L3 collaborator modules that do drive a few widget types by design: they
#: still may not depend upward, and their ``editor_view`` coupling is frozen
#: here, so a new widget import fails until it is justified (R4).
UI_FROZEN_FILES: dict[str, set[str]] = {
    "flows/prompt_completion.py": {
        "yate.editor_view",
        "yate.editor_view.theme",
    },
    "flows/document_flows.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.explorer",
        "yate.editor_view.panes",
    },
    "flows/window_flows.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.explorer",
        "yate.editor_view.panes",
    },
    "flows/completion_flows.py": {
        "yate.editor_view",
        "yate.editor_view.theme",
        "yate.editor_view.commandline",
        "yate.editor_view.completion",
        "yate.editor_view.editor",
        "yate.editor_view.panes",
    },
    "flows/lsp_sync.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.modals",
        "yate.editor_view.panes",
        "yate.editor_view.statusbar",
    },
    "flows/mouse_flows.py": {
        "yate.editor_view",
        "yate.editor_view.editor",
    },
    "flows/shell_flows.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.modals",
    },
    "flows/overlay_flows.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.diffview",
        "yate.editor_view.manual",
        "yate.editor_view.modals",
        "yate.editor_view.palette",
        "yate.editor_view.screensaver",
    },
    "flows/prompt_flows.py": {
        "yate.editor_view",
        "yate.editor_view.commandline",
        "yate.editor_view.panes",
    },
}

#: The built-in tables import the editor; the editor must not import them (R5).
EDITOR_FORBIDDEN_IMPORTS: tuple[str, ...] = ("yate.actions", "yate.commands")

#: The built-in tables the shell registers into the editor's registries (R7).
BUILTIN_TABLE_MODULES: tuple[str, ...] = ("yate.actions", "yate.commands")

#: Banned identifier suffixes (R7): no protocol-ish / thin-delegate naming.
#: ``PaneHost`` is the Textual widget container in ``editor_view/panes.py``,
#: so it is whitelisted.  Flow modules are named by duty (``*Flows`` /
#: ``LspSync``); ``*Controller`` is banned for new code.
BANNED_SUFFIXES: tuple[str, ...] = ("Feature", "Host", "Ops", "Delegate", "Controller")
BANNED_SUFFIX_WHITELIST: set[str] = {"PaneHost"}

#: Banned identifier names (R2 / R7).
BANNED_NAMES: set[str] = {"AppProtocol"}

#: Single-file size threshold (A11, rules section 3.7): a ``yate/`` file
#: beyond *MAX_SOURCE_LINES* lines must be split or registered in the
#: exemption list below.  The list mirrors
#: ``.trae/rules/architecture-boundaries.md`` section 3.7 -- the two are
#: maintained in sync (each big-module-split wave shrinks both).
MAX_SOURCE_LINES: int = 800

#: Files exempt from the size threshold (A11), keyed by ``yate/``-relative
#: path.  ``keymaps/vim.py`` and ``editor.py`` are permanent exemptions
#: (big-module-split plan section 2); the rest are temporary registrations
#: ahead of their split wave (c: editor_view/editor, d: theme,
#: e: buffer + emulator, f: manager + yaterc).  Wave b is done:
#: ``editor_view/diffview.py`` was split into ``diff_pane.py`` and dropped.
SIZE_EXEMPT_FILES: frozenset[str] = frozenset({
    "keymaps/vim.py",
    "editor.py",
    "editor_view/editor.py",
    "editor_core/buffer.py",
    "editor_term/emulator.py",
    "editor_lsp/manager.py",
    "editor_view/theme.py",
    "yaterc.py",
})


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


def _is_callable_spelling(node: ast.expr) -> bool:
    """Whether *node* is spelled ``Callable``, bare or module-qualified."""
    if isinstance(node, ast.Name):
        return node.id == "Callable"
    if isinstance(node, ast.Attribute):
        return node.attr == "Callable"
    return False


def _is_callable_annotation(node: ast.expr) -> bool:
    """Whether *node* *is* a ``Callable[...]``, optionally unioned with ``None``.

    Only the top level counts, on purpose: ``dict[str, Callable[...]]`` is a
    data table whose *elements* are callbacks, not an alias definition, and it
    reads fine inline (plan rule R-C).  Tuples and lists *are* unpacked, so the
    ``X, Y = Callable[...], Callable[...]`` unpacking form cannot slip through.
    A quoted forward reference counts as a mention -- the fix is the same
    either way (give it a name); :func:`_assigns_callable_alias` keeps that
    heuristic out of plain values, where a string is only a string.
    """
    if isinstance(node, ast.Subscript):
        return _is_callable_spelling(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_callable_annotation(node.left) or _is_callable_annotation(node.right)
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_is_callable_annotation(element) for element in node.elts)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "Callable[" in node.value
    return False


def _assigns_callable_alias(node: ast.Assign | ast.AnnAssign) -> bool:
    """Whether *node* defines a callback alias the pre-PEP-695 way.

    Both spellings count: ``X = Callable[...]`` and ``X: Callable[...] = ...``.
    A bare declaration without a value -- a dataclass field such as
    ``message: Callable[[str], None]`` -- is not an alias definition and stays
    allowed; give it a named alias or keep the inline shape.

    A plain string *value* is never an alias: with postponed annotations only
    the annotation may be a quoted reference, so a module-level
    ``DOC = "call it Callable[[int], None]"`` stays prose (PR !62 review M1).
    """
    if isinstance(node, ast.AnnAssign):
        if node.value is None:
            return False
        return _is_callable_annotation(node.annotation)
    value = node.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return False
    return _is_callable_annotation(value)


def _alias_binding_statements(body: list[ast.stmt]) -> list[ast.Assign | ast.AnnAssign]:
    """Module-level and class-level assignments, descending into ``if`` / ``try``.

    Function and method bodies are instance state (``self._hook:
    Callable[...] = None``), not alias definitions, so the walk stops at their
    boundary: a one-off callback attribute whose name already says what it is
    has nothing to gain from an alias.
    """
    out: list[ast.Assign | ast.AnnAssign] = []
    for node in body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            out.append(node)
        elif isinstance(node, ast.ClassDef):
            out.extend(_alias_binding_statements(node.body))
        elif isinstance(node, (ast.If, ast.While)):
            out.extend(_alias_binding_statements(node.body))
            out.extend(_alias_binding_statements(node.orelse))
        elif isinstance(node, ast.Try):
            out.extend(_alias_binding_statements(node.body))
            for handler in node.handlers:
                out.extend(_alias_binding_statements(handler.body))
            out.extend(_alias_binding_statements(node.orelse))
            out.extend(_alias_binding_statements(node.finalbody))
    return out


def test_callable_aliases_use_type_statements() -> None:
    """Callback aliases are ``type`` statements, not assignments (IKJUWP)."""
    offenders: list[tuple[str, int]] = []
    for path in _yate_files():
        rel = path.relative_to(YATE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _alias_binding_statements(tree.body):
            if _assigns_callable_alias(node):
                offenders.append((rel, node.lineno))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "typing"
                and any(a.name in ("TypeAlias", "TypeAliasType") for a in node.names)
            ):
                offenders.append((rel, node.lineno))
    assert not offenders, offenders


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
    """``keymaps`` / ``services`` / ``keyproto`` / ``session.py`` /
    ``registries.py`` / ``config.py`` run without a mounted app: they must
    not import ``editor_view`` (R4)."""
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
    """``flows/completion_flows.py`` / ``flows/prompt_completion.py`` are
    editor-level collaborators: they may drive their known widgets but never
    depend upward, and a new ``editor_view`` import must be added here first
    (R11)."""
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


def test_source_files_within_size_threshold() -> None:
    """``yate/`` files stay within the A11 size threshold unless registered.

    A file beyond :data:`MAX_SOURCE_LINES` lines is a split candidate
    (rules section 3.7): multi-duty files must be split, single-duty long
    files may be registered in :data:`SIZE_EXEMPT_FILES` -- which mirrors
    the rule text, so a wave of big-module-split shrinks both in the same
    change.  The count is the with-blank-lines figure the plan documents
    use (``Get-Content | Measure-Object -Line`` equivalent).
    """
    offenders: list[tuple[str, int]] = []
    for path in _yate_files():
        key = path.relative_to(YATE).as_posix()
        if key in SIZE_EXEMPT_FILES:
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_SOURCE_LINES:
            offenders.append((key, lines))
    assert not offenders, offenders


def test_pane_model_lives_in_l1_session() -> None:
    """The pane tree model is L1 state, not a widget-package type layer:
    ``session.py`` owns it; ``editor_view`` imports it, never re-exports it."""
    source = (YATE / "session.py").read_text(encoding="utf-8")
    for name in ("class Leaf", "class Split", "class ViewState", "def find_leaf"):
        assert name in source, name
    assert not (YATE / "editor_view" / "pane_types.py").exists()
    panes = (YATE / "editor_view" / "panes.py").read_text(encoding="utf-8")
    assert "backward compatibility" not in panes


#: ``logging`` levels whose message must use lazy ``%`` placeholders.
LOG_LEVEL_METHODS: set[str] = {"debug", "info", "warning", "error", "exception", "critical"}


def _fstring_log_calls(path: Path) -> list[int]:
    """Line numbers of ``log.<level>(f"...")`` calls in *path* (style 4.6)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in LOG_LEVEL_METHODS):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "log"):
            continue
        if node.args and isinstance(node.args[0], ast.JoinedStr):
            out.append(node.lineno)
    return out


def test_log_calls_use_lazy_percent_formatting() -> None:
    """``log.*`` calls never format the message with an f-string: a lazy
    ``%`` placeholder keeps argument evaluation off while the trace level
    filters the record (python-coding-style 4.6)."""
    for path in _yate_files():
        lines = _fstring_log_calls(path)
        assert lines == [], (path, lines)


#: Per-session AST cache keyed by (path, mtime): several guards re-scan
#: overlapping file sets, so each file is parsed (and read) once.
_PARSE_CACHE: dict[tuple[Path, float], ast.Module] = {}


def _parsed_tree(path: Path) -> ast.Module:
    """Parse *path* once per (path, mtime) for the whole test session."""
    key = (path, path.stat().st_mtime)
    tree = _PARSE_CACHE.get(key)
    if tree is None:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _PARSE_CACHE[key] = tree
    return tree


def _module_imports(path: Path) -> set[str]:
    """Every module *path* imports (stdlib, third-party, project)."""
    tree = _parsed_tree(path)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
    return out


def _devtools_log_accesses(path: Path) -> list[str]:
    """``self.log`` / ``self.app.log`` attribute accesses in *path* (R12).

    AST-based so a docstring or comment that merely mentions the devtools
    channel does not false-positive.
    """
    tree = _parsed_tree(path)
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr != "log":
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id == "self":
            out.append("self.log")
        elif (
            isinstance(value, ast.Attribute)
            and value.attr == "app"
            and isinstance(value.value, ast.Name)
            and value.value.id == "self"
        ):
            out.append("self.app.log")
    return out


def test_logging_never_touches_devtools_channel() -> None:
    """``self.log`` / ``self.app.log`` is Textual's devtools channel: yate
    logs through the tracing singleton only, and devtools visibility comes
    from the ``TextualHandler`` bridge in ``YateApp.on_mount`` (R12).  The
    Windows chord driver once imported ``textual.app`` just to reach it."""
    for path in _yate_files():
        accesses = _devtools_log_accesses(path)
        assert accesses == [], (path, accesses)


def test_ui_free_layers_do_not_import_textual_app() -> None:
    """``textual.app`` (the shell and the devtools logger's home) stays out
    of the UI-free L0 modules (R12): a leaf that needs it for logging is a
    layering violation -- the L4 bridge replaces that need entirely."""
    targets: list[Path] = []
    for package in UI_FREE_PACKAGES:
        targets.extend(
            p for p in (YATE / package).rglob("*.py")
            if "__pycache__" not in p.parts
        )
    targets.extend(YATE / name for name in (*UI_FREE_FILES, "logs.py"))
    for path in targets:
        assert path.exists(), f"stale UI-free guard target: {path}"
        assert "textual.app" not in _module_imports(path), path


def test_devtools_bridge_follows_app_lifecycle() -> None:
    """The R12 ``TextualHandler`` bridge is mounted on the tracing root in
    ``YateApp.on_mount`` and detached in ``on_unmount`` -- exactly one
    handler per mounted app, none left behind after unmount."""
    from textual.logging import TextualHandler

    from yate.app import YateApp
    from yate.logs import LOGGER_NAME

    # Platform-independent: run_test drives the HeadlessDriver, not the
    # Windows console driver.
    root = logging.getLogger(LOGGER_NAME)
    app = YateApp()

    async def _drive() -> None:
        async with app.run_test(size=(80, 24)):
            mounted = [h for h in root.handlers if isinstance(h, TextualHandler)]
            assert len(mounted) == 1, mounted
        detached = [h for h in root.handlers if isinstance(h, TextualHandler)]
        assert detached == [], detached

    try:
        asyncio.run(_drive())
    finally:
        # A crash between mount and unmount must not poison other tests.
        for handler in [h for h in root.handlers if isinstance(h, TextualHandler)]:
            root.removeHandler(handler)


def test_devtools_bridge_forwards_only_while_tracing_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The R12 bridge is gated by the tracing switch: with tracing disabled
    no record may reach the devtools channel (one switch for all yate
    diagnostics), and enabled records forward to ``TextualHandler.emit``.

    The bridge under test is the instance actually mounted by ``on_mount``
    -- which also proves the mounted handler is the gated subclass."""
    from textual.logging import TextualHandler

    from yate.app import YateApp
    from yate.logs import LOGGER_NAME, tracing

    root = logging.getLogger(LOGGER_NAME)
    app = YateApp()

    async def _drive() -> None:
        async with app.run_test(size=(80, 24)):
            bridge = next(h for h in root.handlers if isinstance(h, TextualHandler))
            forwarded: list[logging.LogRecord] = []

            def _fake_emit(
                sender: TextualHandler, record: logging.LogRecord
            ) -> None:
                forwarded.append(record)

            monkeypatch.setattr(TextualHandler, "emit", _fake_emit)
            record = logging.LogRecord(
                "yate.test", logging.WARNING, __file__, 1, "boom", None, None
            )
            monkeypatch.setattr(tracing, "is_enabled", lambda: False)
            bridge.emit(record)
            assert forwarded == []
            monkeypatch.setattr(tracing, "is_enabled", lambda: True)
            bridge.emit(record)
            assert len(forwarded) == 1

    try:
        asyncio.run(_drive())
    finally:
        for handler in [h for h in root.handlers if isinstance(h, TextualHandler)]:
            root.removeHandler(handler)


def test_no_class_level_scrollbar_renderer_patch() -> None:
    """Slim scrollbars are injected per widget, never patched globally.

    T1 governance (review_ui_refine_20260927): ``ScrollBar.renderer = ...``
    at class level is a process-global monkey-patch that would leak across
    every Textual app in the process.  Only per-widget instance assignment
    (``widget.vertical_scrollbar.renderer = ...``) is allowed.
    """
    pattern = re.compile(r"(?m)^\s*ScrollBar\.renderer\s*=")
    for path in _yate_files():
        source = path.read_text(encoding="utf-8")
        assert pattern.search(source) is None, (
            f"{path}: class-level ScrollBar.renderer patch is banned; "
            "use editor_view.scrollbars.apply_slim_scrollbars(widget)"
        )


def test_editor_does_not_paint_widget_styles() -> None:
    """T2 governance (review_ui_refine_20260927): widgets own their theme.

    The L3 ``Editor`` must not reach into widget internals: no
    ``apply_theme`` / ``update_sidebar_head`` any more, and no direct
    ``styles.background`` / ``styles.scrollbar_*`` assignments.  Layout
    attributes it owns (terminal dock height) stay allowed.
    """
    source = (YATE / "editor.py").read_text(encoding="utf-8")
    for banned in (
        "def apply_theme",
        "def update_sidebar_head",
        ".styles.background =",
        ".styles.scrollbar_",
    ):
        assert banned not in source, (
            f"editor.py must not contain {banned!r}: widgets paint themselves"
        )


def _stringified_imprecise(annotation: ast.expr) -> bool:
    """Whether *annotation* is a stringified ``App[Any]`` / ``App[object]``.

    Quoted forward references parse as plain ``Constant`` strings, so they
    hide the subscript from the ``Subscript`` branch of the guard.
    """
    return (
        isinstance(annotation, ast.Constant)
        and isinstance(annotation.value, str)
        and annotation.value.strip() in ("App[Any]", "App[object]")
    )


def _imprecise_app_annotations(path: Path) -> list[int]:
    """Line numbers of ``App[Any]`` / ``App[object]`` subscripts in *path*.

    AST-based so docstrings mentioning the shapes do not false-positive.
    ``App[None]`` (the shell's precise message type) is the only allowed
    ``App`` subscript.  Matches the bare (``App[...]``) and qualified
    (``textual.app.App[...]``) spellings plus stringified forward
    references at the variable-annotation, parameter and return positions.
    """
    tree = _parsed_tree(path)
    out: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            value = node.value
            named = (isinstance(value, ast.Name) and value.id == "App") or (
                isinstance(value, ast.Attribute) and value.attr == "App"
            )
            if not named:
                continue
            subscript = node.slice
            if isinstance(subscript, ast.Name) and subscript.id in ("Any", "object"):
                out.append(node.lineno)
            elif _stringified_imprecise(subscript):
                out.append(node.lineno)
        elif isinstance(node, ast.AnnAssign):
            if _stringified_imprecise(node.annotation):
                out.append(node.lineno)
        elif isinstance(node, ast.arg):
            if node.annotation is not None and _stringified_imprecise(node.annotation):
                out.append(node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None and _stringified_imprecise(node.returns):
                out.append(node.lineno)
    return out


def test_app_annotations_are_precise() -> None:
    """``App[Any]`` / ``App[object]`` are banned across ``yate/``.

    The shell is ``App[None]``; collaborators receive that precise type or
    injected capabilities, never a vague App handle to reach ``.run_worker``
    through (issue IKJB0Q -- the ``App[object]`` / ``App[Any]`` muddle).
    """
    for path in _yate_files():
        lines = _imprecise_app_annotations(path)
        assert lines == [], (path, lines)


def _self_app_accesses(path: Path) -> list[int]:
    """Line numbers of ``self.app`` attribute chains in *path*.

    AST-based so a docstring that merely mentions the handle does not
    false-positive (same rationale as the R12 devtools guard).
    """
    tree = _parsed_tree(path)
    out: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "app"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            out.append(node.lineno)
    return out


def test_flow_modules_hold_no_app_handle() -> None:
    """Top-level modules other than ``editor.py`` never hold the App handle.

    Verbs are injected as bound methods and state queries as editor-owned
    semantic callables (semantic capability injection, issue IKJB0Q);
    ``editor.py`` is the one L3 ``App[None]`` holder and capability
    distributor.  The scan covers top-level ``yate/*.py`` plus the
    ``yate/flows/`` subpackage, matching the plan's Stage 3 declaration.
    """
    scan_roots = [YATE.glob("*.py"), (YATE / "flows").glob("*.py")]
    for path in (p for root in scan_roots for p in root):
        if path.name == "editor.py":
            continue
        lines = _self_app_accesses(path)
        assert lines == [], (path, lines)


def test_editor_lsp_package_root_is_light() -> None:
    """The ``editor_lsp`` package root never pulls in the manager (A1).

    The root re-exports the lightweight client data types only; the
    heavyweight ``LspManager`` lives in :mod:`yate.editor_lsp.manager` so
    ``import yate.editor_lsp`` stays cheap (architecture-boundaries rule 3.5,
    layer 3: heavyweight implementation modules stay out of package roots).
    """
    imports = _module_imports(YATE / "editor_lsp" / "__init__.py")
    offenders = [name for name in imports if name.startswith("yate.editor_lsp.manager")]
    assert offenders == [], sorted(imports)


def test_leaf_package_reexports_carry_exception_note() -> None:
    """Every re-exporting leaf package documents the rule 3.5 exception (A1).

    Guards against the rule text and the code drifting apart again: a leaf
    package may keep re-exports only while its ``__init__.py`` notes the
    documented exception (architecture-boundaries rule 3.5 layer 3).
    """
    leaf_packages = ("editor_core", "editor_lsp", "editor_syntax", "editor_term", "keymaps")
    for name in leaf_packages:
        text = (YATE / name / "__init__.py").read_text(encoding="utf-8")
        if "__all__" not in text:
            continue
        assert "architecture-boundaries" in text, name


def test_support_mouse_gate_lives_in_app_on_event() -> None:
    """``support_mouse = false`` drops mouse events in ``YateApp.on_event``
    before ``super().on_event`` forwards them (issue IKJRFK): the gate
    must appear before the forward call in the source."""
    source = (YATE / "app.py").read_text(encoding="utf-8")
    assert "support_mouse" in source
    gate = source.index("support_mouse")
    forward = source.index("await super().on_event(event)")
    assert gate < forward
