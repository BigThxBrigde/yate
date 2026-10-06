"""Static guards for the PyInstaller build scripts under ``pack/`` (issue IKJPVB).

Two packaging promises are pure build-time wiring that no runtime test can
observe, so both are pinned statically here:

* the shared inventory ``pack/_common.EXCLUDES`` still drops Pillow and numpy,
  that the specs feed that inventory to ``Analysis`` instead of a literal
  ``excludes=[]``, and -- the assumption the inventory rests on -- that no code
  shipped inside the frozen app imports those packages (core modules *and* the
  bundled extension examples, both of which execute at runtime);
* the one-folder spec commits to a single cross-platform layout: the runtime
  files live in one named contents directory on Windows *and* POSIX alike --
  ``EXE(contents_directory=CONTENTS_DIRNAME)`` with
  ``CONTENTS_DIRNAME = "runtime"`` at spec top level -- while the onefile spec,
  which embeds everything in the exe and ships nothing beside it, must not grow
  that knob at all.  The name is pinned by shape *and* by value because the
  content directory is the one place where a legal-but-wrong choice (PyInstaller's
  ``_internal`` default, the flat ``"."``, or the exe's own base name) produces a
  build that breaks rather than one that merely looks different.

Nothing here imports PyInstaller: it lives in the ``build`` extra, which is not
a CI dependency.  ``pack/_common.py`` is therefore loaded straight from its path
(its module level touches the stdlib only), and the two ``.spec`` scripts -- which
PyInstaller *execs* as plain scripts with an injected ``SPECPATH``, so they are
not importable -- are read with :mod:`ast` instead of run.  Note that pyright
itself cannot check them either (it only analyses ``.py``), so for the specs
these AST guards plus a real build are the coverage that exists.
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

#: One-folder spec: the named contents directory plus the shared excludes.
_ONEFOLDER_SPEC: Path = _REPO_ROOT / "pack" / "yate.spec"

#: Onefile spec: everything is embedded in the exe, so no layout knob applies.
_ONEFILE_SPEC: Path = _REPO_ROOT / "pack" / "yate-onefile.spec"

#: Both specs, for the checks that must hold for either build mode.
_SPECS: tuple[Path, ...] = (_ONEFOLDER_SPEC, _ONEFILE_SPEC)


#: ``SpecInputs`` fields a spec never reads as ``inputs.<field>`` because it is
#: consumed through a helper instead -- ``project_root`` only reaches the specs
#: via :meth:`SpecInputs.pkg_path`.  Listed so that adding a field without wiring
#: it into the specs fails loudly instead of silently doing nothing.
_SPEC_HELPER_FIELDS: frozenset[str] = frozenset({"project_root"})

#: The only dynamic imports the shipped code may perform, as
#: ``"<path>:<callee>(<argument source>)"``.  Both load tree-sitter grammar
#: modules, which :data:`pack._common._TS_PACKAGES` collects explicitly; they
#: are listed here so that a *new* dynamic import has to be reviewed and
#: justified rather than slipping past the premise guard.
_REVIEWED_DYNAMIC_IMPORTS: frozenset[str] = frozenset(
    {
        "editor_syntax/ts_backend/languages.py:importlib.import_module(module_name)",
        "editor_syntax/ts_backend/languages.py:importlib.import_module(grammar)",
    }
)


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


@functools.lru_cache(maxsize=None)
def _parse(path: Path) -> ast.Module:
    """The AST of a Python source file (``pack/_common.py``, a ``.spec``, ``yate/**``).

    Memoised like :func:`_load_common`: the guards ask for the same handful of
    files repeatedly, and the trees are never mutated by the callers.
    """
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dynamic_import_name(node: ast.Call) -> str | None:
    """The dynamic-import callee of *node* as source text, or ``None``.

    Returning ``ast.unparse(node.func)`` rather than a normalised label keeps
    the three spellings distinguishable -- ``__import__("x")``,
    ``importlib.import_module("x")`` and ``from importlib import
    import_module`` -- which is what lets the reviewed-import allowlist name an
    exact call shape.  The bare-name form is matched by name alone, so a local
    function called ``import_module`` would also be inspected; harmless, since
    the checks only fire on a banned module name or an unreviewed call shape.
    """
    func = node.func
    if isinstance(func, ast.Name) and func.id in {"__import__", "import_module"}:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        return ast.unparse(func)
    return None


def _yate_sources() -> list[Path]:
    """Every Python source file the frozen app can execute.

    ``*.py`` covers ordinary modules.  ``*.example`` covers the templates that
    ship as data yet run at runtime through ``compile()``/``exec()``:

    * ``yate/extensions/*.py.example`` -- bundled extensions, imported via
      ``importlib.util.spec_from_file_location`` (``yate/services/extensions.py``);
    * ``yate/yaterc.example`` -- an rc file (``yate/config.py``);
    * ``yate/resources/theme_examples/*.example`` -- themes (``yate/editor_view/theme.py``).

    Matching the suffix rather than enumerating paths keeps this honest when a
    fourth kind of template appears.
    """
    package = _REPO_ROOT / "yate"
    return sorted({*package.rglob("*.py"), *package.rglob("*.example")})


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

    Scope: every ``.py`` under ``yate/`` plus every ``*.example`` template --
    the extensions, ``yaterc.example`` and the theme examples ship as data but
    execute at runtime.  Dynamic imports are covered too -- only ``import``/
    ``from`` statements would leave ``importlib.import_module("PIL")`` unnoticed.

    Residual limitation: an import computed at runtime (name built from
    variables) still escapes this scan.
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
            elif isinstance(node, ast.Call) and _dynamic_import_name(node):
                offenders += [
                    (path.name, arg.value)
                    for arg in node.args
                    if isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and arg.value.split(".")[0] in banned
                ]
    assert offenders == []


# --- both specs forward the inventory to Analysis -----------------------------


@pytest.mark.parametrize("spec_path", _SPECS, ids=["onefolder", "onefile"])
def test_analysis_call_when_spec_parsed_forwards_shared_excludes(spec_path: Path) -> None:
    """Every build mode drops the same modules, via ``inputs.excludes``.

    Asserting the attribute *and* its host also rules out the pre-issue shape
    ``excludes=[]`` -- a list literal is not an ``ast.Attribute``, so that
    fallback can no longer reach the build.
    """
    excludes_value = _keyword_value(_one_call(_parse(spec_path), "Analysis", spec_path), "excludes")
    assert isinstance(excludes_value, ast.Attribute), (
        f"{spec_path.name} must read inputs.excludes (a literal list would ship "
        "the excluded packages)"
    )
    assert excludes_value.attr == "excludes"
    assert isinstance(excludes_value.value, ast.Name), f"{spec_path.name} must read inputs.excludes"
    assert excludes_value.value.id == "inputs"


def _spec_input_fields() -> list[str]:
    """Field names declared on the ``SpecInputs`` dataclass."""
    dataclass = next(
        node
        for node in _parse(_COMMON_PATH).body
        if isinstance(node, ast.ClassDef) and node.name == "SpecInputs"
    )
    return [
        node.target.id
        for node in dataclass.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]


def _collected_field_names() -> set[str]:
    """Field names ``collect()`` passes to the ``SpecInputs(...)`` constructor."""
    [collect_fn] = _functions(_parse(_COMMON_PATH), "collect")
    return {
        keyword.arg
        for keyword in _returned_call(collect_fn).keywords
        if keyword.arg is not None
    }


def _inputs_attributes(path: Path) -> set[str]:
    """Every ``inputs.<field>`` a spec reads."""
    return {
        node.attr
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "inputs"
    }


def test_collect_when_common_parsed_fills_every_spec_input_field() -> None:
    """A dataclass field and its constructor argument must not drift apart.

    pyright cannot check the specs (they are exec'd with PyInstaller-injected
    globals, so every ``Analysis`` / ``EXE`` / ``SPECPATH`` reference would be an
    undefined-variable error), which makes this the guard that actually keeps the
    shared contract honest: a field added to ``SpecInputs`` cannot start
    defaulting to nothing without this failing.
    """
    assert _collected_field_names() == set(_spec_input_fields())


@pytest.mark.parametrize("spec_path", _SPECS, ids=["onefolder", "onefile"])
def test_spec_when_parsed_reads_every_spec_input_field(spec_path: Path) -> None:
    """Both build modes must consume every collected input.

    Without this a field could be collected, handed to one spec and quietly
    ignored by the other -- the exact drift the shared ``_common.py`` exists to
    prevent.  Fields reached through a helper are named in
    :data:`_SPEC_HELPER_FIELDS` instead.
    """
    unread = set(_spec_input_fields()) - _inputs_attributes(spec_path)
    assert unread - _SPEC_HELPER_FIELDS == set(), f"{spec_path.name} ignores {sorted(unread)}"


# --- dynamic imports inside the shipped code ----------------------------------


def _dynamic_imports() -> list[tuple[str, str]]:
    """``(call shape, callee)`` for every dynamic import in the shipped sources."""
    found: list[tuple[str, str]] = []
    package = _REPO_ROOT / "yate"
    for path in _yate_sources():
        # Stated as an assertion rather than left to relative_to(): a scope that
        # escaped the package would raise ValueError, which is exactly the
        # unreadable failure mode these guards exist to avoid.
        assert path.is_relative_to(package), f"guard scope escaped the package: {path}"
        relative = path.relative_to(package).as_posix()
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            callee = _dynamic_import_name(node)
            if callee is None:
                continue
            arguments = ", ".join(ast.unparse(argument) for argument in node.args)
            found.append((f"{relative}:{callee}({arguments})", callee))
    return found


def test_dynamic_imports_when_sources_scanned_are_reviewed_not_invisible() -> None:
    """A non-literal dynamic import must be justified in writing.

    The premise guard catches literal module names; a computed one
    (``importlib.import_module(some_name)``) is invisible to it.  Rather than
    accepting that hole, every dynamic import in the shipped code must appear in
    :data:`_REVIEWED_DYNAMIC_IMPORTS` with its exact call shape -- adding one is
    then a deliberate, reviewable act.  ``__import__`` is banned outright: it has
    no legitimate use in application code.
    """
    found = _dynamic_imports()
    banned = sorted(key for key, callee in found if callee.split(".")[-1] == "__import__")
    assert banned == [], f"__import__ is banned in shipped code: {banned}"
    unreviewed = sorted(key for key, _ in found if key not in _REVIEWED_DYNAMIC_IMPORTS)
    assert unreviewed == [], f"unreviewed dynamic imports: {unreviewed}"


# --- bundle layout ------------------------------------------------------------


def test_exe_call_when_onefolder_spec_parsed_uses_the_named_contents_directory() -> None:
    """The one-folder layout must resolve to one named constant, not a choice.

    What is guarded: the layout decision collapses to a single name that every
    platform shares, instead of being re-derived per platform.  Pinning the
    shape explicitly -- ``ast.Name`` with ``id == "CONTENTS_DIRNAME"`` -- is what
    makes both regressions fail loudly.  Bringing back
    ``IfExp(sys.platform == "win32", ".", "_internal")`` would fork the two
    platforms again (the exact shape issue note_51452120 rejects), and inlining a
    bare ``"runtime"`` literal would work today but let the name drift between
    the spec and the packaging scripts that check for ``dist/yate/runtime``,
    since only the constant gives them one thing to agree on.

    Limitation: this asserts the *reference*, not the value it resolves to --
    that is the next guard's job.
    """
    exe = _one_call(_parse(_ONEFOLDER_SPEC), "EXE", _ONEFOLDER_SPEC)
    contents_directory = _keyword_value(exe, "contents_directory")
    assert contents_directory is not None, "the one-folder build lost its layout choice"
    assert isinstance(contents_directory, ast.Name), (
        "contents_directory must read the CONTENTS_DIRNAME constant, got "
        f"{ast.unparse(contents_directory)}"
    )
    assert contents_directory.id == "CONTENTS_DIRNAME", (
        f"contents_directory must read CONTENTS_DIRNAME, got {contents_directory.id!r}"
    )


def test_contents_dirname_when_onefolder_spec_parsed_is_a_cross_platform_runtime_dir() -> None:
    """The contents directory name must stay a usable single directory name.

    ``contents_directory`` accepts a single path segment and nothing more
    (``PyInstaller/building/api.py:501-508``): ``""`` and ``"."`` mean the flat
    layout, while ``".."`` or any name containing a separator makes PyInstaller
    ``SystemExit`` before it writes anything.  ``"_internal"`` is legal but is
    precisely the default issue note_51452120 asks to replace.  The one real
    collision left is the exe's own base name: ``EXECUTABLE`` always lands in
    ``join(name, dest)`` while everything else lands in
    ``join(name, contents_directory, dest)``, so equal names make COLLECT's
    ``os.makedirs`` raise ``SystemExit`` (``api.py:1183-1189``) -- hence reading
    the exe name out of the spec rather than hardcoding ``"yate"``, which keeps
    the guard honest if the exe is ever renamed.

    Both binding shapes are accepted -- the annotated ``CONTENTS_DIRNAME: str =
    "runtime"`` the spec actually uses (module-level names must carry an
    annotation, python-coding-style.md §3.1) and the bare ``Assign`` form -- since
    the annotation is a style matter this guard has no reason to police; what it
    insists on is one unambiguous binding whose value is a literal.

    Limitation (registered as RK1 in the plan): these are static shape and value
    assertions.  A conditional value cannot be evaluated statically at all, which
    is why the first guard insists on a plain literal here; and whether a POSIX
    build of this layout really succeeds can only be shown by a real Linux
    build, which CI cannot do -- the name being a legal single segment and
    distinct from the exe name is the strongest claim available from source.
    """
    tree = _parse(_ONEFOLDER_SPEC)
    assignments = [
        node
        for node in tree.body
        if (
            (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "CONTENTS_DIRNAME"
            )
            or (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "CONTENTS_DIRNAME"
            )
        )
    ]
    assert len(assignments) == 1, (
        f"{_ONEFOLDER_SPEC.name} must bind CONTENTS_DIRNAME once at module level, "
        f"found {len(assignments)}"
    )
    dirname_node = assignments[0].value
    assert isinstance(dirname_node, ast.Constant), (
        "CONTENTS_DIRNAME must be a plain literal, got "
        f"{ast.unparse(dirname_node) if dirname_node is not None else None}"
    )
    assert isinstance(dirname_node.value, str), "CONTENTS_DIRNAME must be a string"
    dirname = dirname_node.value

    exe_name_node = _keyword_value(_one_call(tree, "EXE", _ONEFOLDER_SPEC), "name")
    assert isinstance(exe_name_node, ast.Constant), (
        f"{_ONEFOLDER_SPEC.name} must keep a literal name= for EXE()"
    )
    assert isinstance(exe_name_node.value, str), "the EXE() name must be a string"

    assert dirname not in {"", ".", ".."}, (
        f"{dirname!r} is not a directory PyInstaller can create: '' and '.' are the "
        "flat layouts and '..' makes it exit immediately"
    )
    assert dirname != "_internal", (
        f"{dirname!r} is PyInstaller's own default -- the name note_51452120 asks to "
        "replace, not to keep"
    )
    assert dirname != exe_name_node.value, (
        f"contents_directory {dirname!r} collides with the exe base name; COLLECT would "
        "have to create a directory where the executable already sits"
    )
    assert "/" not in dirname and "\\" not in dirname, (
        f"{dirname!r} must be a single path segment"
    )
    assert dirname.isidentifier(), f"{dirname!r} is not a plain directory name"


def test_exe_call_when_onefile_spec_parsed_omits_contents_directory() -> None:
    """Onefile embeds everything in the exe, so the layout knob is meaningless."""
    exe = _one_call(_parse(_ONEFILE_SPEC), "EXE", _ONEFILE_SPEC)
    assert _keyword_value(exe, "contents_directory") is None
