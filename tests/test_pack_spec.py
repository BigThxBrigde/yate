"""Static guards for the PyInstaller build scripts under ``pack/`` (issue IKJPVB).

Two packaging promises are pure build-time wiring that no runtime test can
observe, so both are pinned statically here:

* the shared inventory ``pack/_common.EXCLUDES`` still drops Pillow (13.1 MiB
  of the 68.4 MiB one-folder bundle, dragged into the graph by
  ``pygments.formatters.img``) and numpy, that the specs feed that inventory
  to ``Analysis`` instead of a literal ``excludes=[]``, and -- the assumption
  the inventory rests on -- that nothing in ``yate/`` imports those packages;
* the one-folder spec scopes the flat layout to Windows --
  ``EXE(contents_directory="." if sys.platform == "win32" else "_internal")``
  -- so the runtime files sit next to ``yate.exe`` there and stay under
  ``_internal/`` elsewhere, while the onefile spec, which ships nothing beside
  the exe, must not grow that knob at all.

Nothing here imports PyInstaller: it lives in the ``build`` extra, which is not
a CI dependency.  ``pack/_common.py`` is therefore loaded straight from its path
(its module level touches the stdlib only), and the two ``.spec`` scripts -- which
PyInstaller *execs* as plain scripts with an injected ``SPECPATH``, so they are
not importable -- are read with :mod:`ast` instead of run.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

#: Repository root -- this module lives in ``tests/``, one level below it.
_REPO_ROOT: Path = Path(__file__).resolve().parents[1]

#: The shared build logic; module level imports stdlib only, so it loads without
#: PyInstaller being installed.
_COMMON_PATH: Path = _REPO_ROOT / "pack" / "_common.py"

#: One-folder spec: flat layout (``contents_directory``) plus the shared excludes.
_ONEFOLDER_SPEC: Path = _REPO_ROOT / "pack" / "yate.spec"

#: Onefile spec: everything is embedded in the exe, so no layout knob applies.
_ONEFILE_SPEC: Path = _REPO_ROOT / "pack" / "yate-onefile.spec"

#: Both specs, for the checks that must hold for either build mode.
_SPECS: tuple[Path, ...] = (_ONEFOLDER_SPEC, _ONEFILE_SPEC)


@functools.lru_cache(maxsize=1)
def _load_common() -> ModuleType:
    """Import ``pack/_common.py`` by path, with PyInstaller absent.

    The spec files are exec'd scripts rather than modules, so they cannot be
    imported at all (see the module docstring); ``_common.py`` is an ordinary
    module and is registered in :data:`sys.modules` while it executes so that
    its :func:`dataclasses.dataclass` can resolve the postponed annotations.

    Cached: without it every call would build a *fresh* module object, so the
    resulting classes would differ per call and any ``isinstance`` against them
    would silently answer ``False``.
    """
    spec = importlib.util.spec_from_file_location("pack_common", _COMMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_COMMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _excludes() -> list[str]:
    """The shared exclude inventory as ``pack/_common.py`` declares it.

    The constant is read out of the module namespace instead of an attribute
    access, which pyright cannot type for a dynamically loaded module; the
    :func:`cast` is that narrowing, and the final assert keeps a non-string
    entry from slipping past as a silently dropped row.
    """
    raw: object = _load_common().__dict__["EXCLUDES"]
    assert isinstance(raw, tuple), f"EXCLUDES must stay a tuple, got {type(raw).__name__}"
    items = cast("tuple[object, ...]", raw)
    entries = [entry for entry in items if isinstance(entry, str)]
    assert len(entries) == len(items), f"EXCLUDES must hold strings only, got {items!r}"
    return entries


def _parse(path: Path) -> ast.Module:
    """The AST of a Python source file (``pack/_common.py``, a ``.spec``, ``yate/**``)."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _yate_sources() -> list[Path]:
    """Every ``.py`` file of the shipped package -- the exclusion's premise scope."""
    return sorted((_REPO_ROOT / "yate").rglob("*.py"))


def _calls(tree: ast.Module, callee: str) -> list[ast.Call]:
    """Every ``callee(...)`` call in *tree*, at any nesting depth."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == callee
    ]


def _one_call(tree: ast.Module, callee: str, path: Path) -> ast.Call:
    """The single ``callee(...)`` call in *tree*; a spec must not grow a second."""
    calls = _calls(tree, callee)
    assert len(calls) == 1, f"{path.name} must call {callee}() once, found {len(calls)}"
    return calls[0]


def _keyword_value(call: ast.Call, name: str) -> ast.expr | None:
    """The expression bound to keyword *name*, or ``None`` when it is absent."""
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _is_empty_list_literal(expr: ast.expr) -> bool:
    """True when *expr* is a literal ``[]`` -- the shape this guard forbids."""
    return isinstance(expr, ast.List) and not expr.elts


def _functions(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    """Every top-level ``def name(...)`` in *tree*; empty when it is gone."""
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def _returned_call(function: ast.FunctionDef) -> ast.Call:
    """The single ``return <call>(...)`` of *function*, asserted not guessed.

    A bare ``next()`` here would turn a renamed or restructured function into
    an opaque ``StopIteration`` -- exactly the failure a guard exists to
    report clearly (python-coding-style.md §4.5).
    """
    calls = [
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
    ]
    assert len(calls) == 1, (
        f"{function.name}() must return exactly one call, found {len(calls)}"
    )
    return calls[0]


# --- the shared exclude inventory (pack/_common.py) ---------------------------


def test_excludes_inventory_when_common_loaded_lists_pillow_and_numpy() -> None:
    """Pillow and its optional array backend must stay out of the bundle."""
    excludes = _excludes()
    assert "PIL" in excludes
    assert "numpy" in excludes


def test_excludes_entries_when_common_loaded_are_non_empty_module_names() -> None:
    """Every entry has to be a usable module name, not padding or whitespace.

    PyInstaller matches ``excludes`` against module names, so a stray dot or an
    inner space would silently exclude nothing at all; ``excludes`` is also
    case-sensitive, hence the case-variant check.

    Residual limitation (registered as R-07 in the review record): a single
    entry whose *only* defect is wrong case cannot be told apart from a real
    package here -- the inventory cannot be probed for importability because the
    ``build`` extra (and therefore Pillow) is absent from the CI environment.
    """
    entries = _excludes()
    assert entries
    assert all(entry == entry.strip() for entry in entries)
    segments = [part for entry in entries for part in entry.split(".")]
    assert all(segment.isidentifier() for segment in segments), entries
    lowered = [entry.lower() for entry in entries]
    assert len(set(lowered)) == len(entries), f"case-variant duplicates: {entries}"


def test_excludes_entries_when_common_loaded_exclude_no_yate_module() -> None:
    """The inventory holds third-party payload only.

    Excluding ``yate`` itself (or any submodule) would produce an exe that
    cannot start, and nothing in a build report would point at this list.
    """
    offenders = [
        entry for entry in _excludes() if entry == "yate" or entry.startswith("yate.")
    ]
    assert offenders == []


def test_collect_return_when_common_parsed_passes_shared_excludes_inventory() -> None:
    """``collect()`` must feed the inventory to the specs, not a private copy.

    The specs read ``inputs.excludes``; a literal list here would leave the two
    build modes free to drift apart again.
    """
    collect_fns = _functions(_parse(_COMMON_PATH), "collect")
    assert len(collect_fns) == 1, f"{_COMMON_PATH.name} must define exactly one collect()"
    excludes_value = _keyword_value(_returned_call(collect_fns[0]), "excludes")
    assert isinstance(excludes_value, ast.Call), "collect() must pass excludes=list(EXCLUDES)"
    assert isinstance(excludes_value.func, ast.Name)
    assert excludes_value.func.id == "list"
    assert len(excludes_value.args) == 1, (
        f"list(EXCLUDES) must take exactly one argument, got {len(excludes_value.args)}"
    )
    [source] = excludes_value.args
    assert isinstance(source, ast.Name)
    assert source.id == "EXCLUDES"


def test_yate_sources_when_scanned_never_import_excluded_modules() -> None:
    """Nothing in ``yate/`` may import a package the build drops.

    ``EXCLUDES`` is only safe while the shipped package is independent of those
    packages: PyInstaller removes them from the frozen graph, so a new feature
    that reached for one would still *build* fine and fail only when a user
    starts the exe -- with nothing in the build report pointing at the list.
    yate's sole legitimate use of Pillow is regenerating the committed
    ``pack/yate.ico`` from the build machine (``tools/pack/icon.py``, dynamic
    import), which is not part of the frozen entry point.
    """
    banned = set(_excludes())
    offenders: list[tuple[str, str]] = []
    for path in _yate_sources():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Import):
                offenders += [
                    (path.name, alias.name)
                    for alias in node.names
                    if alias.name.split(".")[0] in banned
                ]
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in banned:
                    offenders.append((path.name, node.module))
    assert offenders == []


# --- both specs forward the inventory to Analysis -----------------------------


@pytest.mark.parametrize("spec_path", _SPECS, ids=["onefolder", "onefile"])
def test_analysis_call_when_spec_parsed_forwards_shared_excludes(spec_path: Path) -> None:
    """Every build mode drops the same modules, via ``inputs.excludes``.

    The host object is pinned too: ``other.excludes`` would satisfy an
    attribute-name-only check while silently forwarding a different inventory.
    """
    excludes_value = _keyword_value(_one_call(_parse(spec_path), "Analysis", spec_path), "excludes")
    assert isinstance(excludes_value, ast.Attribute), f"{spec_path.name} dropped excludes="
    assert excludes_value.attr == "excludes"
    assert isinstance(excludes_value.value, ast.Name), f"{spec_path.name} must read inputs.excludes"
    assert excludes_value.value.id == "inputs"


@pytest.mark.parametrize("spec_path", _SPECS, ids=["onefolder", "onefile"])
def test_analysis_excludes_when_spec_parsed_is_not_an_empty_literal(spec_path: Path) -> None:
    """``excludes=[]`` is the exact pre-issue shape and must not come back."""
    excludes_value = _keyword_value(_one_call(_parse(spec_path), "Analysis", spec_path), "excludes")
    assert excludes_value is not None, f"{spec_path.name} dropped excludes="
    assert not _is_empty_list_literal(excludes_value)


# --- bundle layout ------------------------------------------------------------


def test_exe_call_when_onefolder_spec_parsed_scopes_flat_layout_to_windows() -> None:
    """The flat layout must be platform-scoped, and explicit about it.

    ``"."`` is only valid where the executable keeps an ``.exe`` suffix: on
    POSIX the exe becomes ``dist/yate/yate``, which is the very path COLLECT
    needs for the bundled ``yate/`` package directory (issue IKJPVB).  So the
    spec must spell out ``IfExp(sys.platform == "win32", ".", "_internal")``.

    Limitation: this asserts the *shape* of that conditional, not that the
    branches are semantically right -- ``sys.platform`` cannot be evaluated
    statically, and whether the POSIX build actually succeeds needs a real
    Linux build, which CI cannot do.  What it does pin down is that the
    platform condition is present at all, that Windows still gets the flat
    layout, and that other platforms get an explicit non-flat directory
    instead of silently inheriting whatever the default changes to.
    """
    exe = _one_call(_parse(_ONEFOLDER_SPEC), "EXE", _ONEFOLDER_SPEC)
    contents_directory = _keyword_value(exe, "contents_directory")
    assert contents_directory is not None, "the one-folder build lost its layout choice"
    assert isinstance(contents_directory, ast.IfExp), (
        "contents_directory must be a sys.platform conditional, got "
        f"{type(contents_directory).__name__}"
    )
    assert ast.unparse(contents_directory.test) == "sys.platform == 'win32'"
    assert ast.unparse(contents_directory.body) == "'.'"
    assert ast.unparse(contents_directory.orelse) == "'_internal'"


def test_exe_call_when_onefile_spec_parsed_omits_contents_directory() -> None:
    """Onefile embeds everything in the exe, so the layout knob is meaningless."""
    exe = _one_call(_parse(_ONEFILE_SPEC), "EXE", _ONEFILE_SPEC)
    assert _keyword_value(exe, "contents_directory") is None
