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
import re
import sys
import tomllib
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
#: ``"<path>:<callee>(<argument source>)"``.  The tree-sitter ones load
#: grammar modules, which :data:`pack._common._TS_PACKAGES` collects
#: explicitly; the lupa one is collected via
#: :data:`pack._common._LUA_PACKAGES` (issue IKL2G6).  They are listed here so
#: that a *new* dynamic import has to be reviewed and justified rather than
#: slipping past the premise guard.
_REVIEWED_DYNAMIC_IMPORTS: frozenset[str] = frozenset(
    {
        "editor_syntax/ts_backend/languages.py:importlib.import_module(module_name)",
        "editor_syntax/ts_backend/languages.py:importlib.import_module(grammar)",
        # lupa is imported dynamically so a lupa-less install pays no import
        # cost and pyright stays stub-free (Any only at the bridge boundary).
        "services/extensions/lua/runtime.py:importlib.import_module('lupa')",
        # POSIX identity modules are unavailable on Windows: loaded through
        # importlib so the module import never fails there (workspace.py
        # _load_posix_identity_modules, entry-stats owner/group display).
        "services/workspace.py:importlib.import_module('pwd')",
        "services/workspace.py:importlib.import_module('grp')",
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

    ``*.py`` covers ordinary modules.  The remaining suffixes cover the
    templates that ship as data yet run at runtime through Python
    ``compile()``/``exec()``:

    * ``yate/extensions/*.py.example`` -- bundled extensions, imported via
      ``importlib.util.spec_from_file_location`` (``yate/services/extensions/loader.py``);
    * ``yate/yaterc.example`` -- an rc file (``yate/config.py``);
    * ``yate/resources/theme_examples/*.example`` -- themes (``yate/editor_components/theme.py``).

    ``yate/extensions/lua.example`` is deliberately absent: it is a Lua chunk
    compiled by the lupa runtime, never by Python, so a Python import scan
    does not apply to it.
    """
    package = _REPO_ROOT / "yate"
    sources = sorted({
        *package.rglob("*.py"),
        *package.rglob("*.py.example"),
        *package.rglob("yaterc.example"),
        *(package / "resources" / "theme_examples").glob("*.example"),
    })
    # Completeness guard: every shipped ``*.example`` template must be in
    # this scan except the Lua one -- a new Python-semantics template whose
    # suffix this list does not name would otherwise silently escape the
    # Python import scan.
    scanned = set(sources)
    exempt = {Path("extensions") / "lua.example"}
    for template in package.rglob("*.example"):
        if template.relative_to(package) in exempt:
            continue  # Lua chunk, compiled by lupa -- never by Python
        assert template in scanned, (
            f"{template} ships as an .example template but is not collected "
            "by _yate_sources(); add it to the scan or justify the exemption"
        )
    return sources


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


# --- the optional dynamic-import package inventories (pack/_common.py) --------


def _lua_packages() -> list[str]:
    """The shared lupa inventory as ``pack/_common.py`` declares it.

    Read out of the module namespace with the same narrowing discipline as
    :func:`_excludes`: the dynamically loaded module defeats pyright's
    inference, so the :func:`cast` carries the narrowing and the asserts keep
    a non-string entry from slipping past silently.
    """
    raw: object = _load_common().__dict__["_LUA_PACKAGES"]
    assert isinstance(raw, tuple), (
        f"_LUA_PACKAGES must stay a tuple, got {type(raw).__name__}"
    )
    items = cast("tuple[object, ...]", raw)
    entries = [entry for entry in items if isinstance(entry, str)]
    assert len(entries) == len(items), (
        f"_LUA_PACKAGES must hold strings only, got {items!r}"
    )
    return entries


def test_lua_packages_when_common_loaded_pin_the_lupa_bridge_inventory() -> None:
    """``pack/_common._LUA_PACKAGES`` must keep collecting exactly ``lupa``.

    lupa is imported dynamically (``yate/services/lua_extensions.py``), so
    PyInstaller's static analysis never sees it: without the explicit
    inventory the frozen exe ships without the Lua bridge and ``yate --diag``
    reports it as ``not installed`` (issue IKL2G6).  Pinning the exact tuple
    makes adding another package a deliberate, reviewable act.
    """
    assert _lua_packages() == ["lupa"]


def test_lua_packages_when_pinned_match_the_pyproject_lua_extra() -> None:
    """The lupa inventory and the pyproject ``[lua]`` extra must not drift.

    ``[lua]`` is the only installable source of lupa: a package present on
    one side only is either uninstallable or invisible to a frozen build --
    the same three-way agreement the ts side enforces in
    ``tests/test_ts_backend.py::test_builtin_packs_match_packaging_manifests``.
    """
    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = cast("dict[str, list[str]]", pyproject["project"]["optional-dependencies"])

    def modules(requirements: list[str]) -> set[str]:
        return {
            re.split(r"[<>=!~\[; ]", requirement.strip(), maxsplit=1)[0].replace("-", "_")
            for requirement in requirements
        }

    lua = set(_lua_packages())
    assert modules(extras["lua"]) == lua
    # ``dev`` is a superset: it adds the test/type tooling on top of [lua].
    assert lua <= modules(extras["dev"])


#: Every file that carries a ``pip install -e ".[build,...]"``-style extras
#: hint: the two specs' build instructions, the pack scripts' auto-install
#: messages, and the README / shipped manuals (bilingual).
_EXTRA_HINT_FILES: tuple[Path, ...] = (
    _ONEFOLDER_SPEC,
    _ONEFILE_SPEC,
    _REPO_ROOT / "pack" / "pack.ps1",
    _REPO_ROOT / "pack" / "pack.sh",
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "README.zh.md",
    _REPO_ROOT / "yate" / "resources" / "manual.en.md",
    _REPO_ROOT / "yate" / "resources" / "manual.zh.md",
)


@pytest.mark.parametrize("path", _EXTRA_HINT_FILES, ids=lambda path: path.name)
def test_build_extra_hints_when_scanned_always_name_the_lua_extra(path: Path) -> None:
    """Every build-extras hint must include the ``[lua]`` extra (issue IKL2G6).

    The direct-PyInstaller path documented in the specs and the README has
    the user install extras by hand; a hint that predates the lua extra
    reproduces the issue's silent lupa-less bundle -- ``pack/_common.py``'s
    ``find_spec`` gate simply skips the missing package, so nothing in the
    build output points at the stale hint.  The negative lookahead keeps the
    matching ``build,ts,lua`` spellings out of the findings.  Scope: every
    file currently carrying such a hint (verified by repo-wide scan) -- a
    new hint-carrying file must be added to :data:`_EXTRA_HINT_FILES`.
    """
    text = path.read_text(encoding="utf-8")
    stale = re.findall(r"build,ts(?!,lua)", text)
    assert stale == [], f"{path.name} still hints `build,ts` without lua"


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


# --- the --no-zip contract of the three build scripts --------------------------


#: The three build scripts whose ``--no-zip`` contract is pinned here.
_PS1_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.ps1"
_SH_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.sh"
_BAT_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.bat"


def _script_text(path: Path) -> str:
    """The full text of a build script (or the zip helper), read as UTF-8."""
    return path.read_text(encoding="utf-8")


def _after(text: str, marker: str, path: Path) -> str:
    """The text after the single occurrence of *marker*, asserted not guessed.

    The count is asserted instead of silently taking ``text.split(marker)[1]``:
    a marker that drifted to zero or duplicated occurrences must fail loudly
    with the offending file named, not return some unrelated slice.
    """
    count = text.count(marker)
    assert count == 1, (
        f"{path.name} must contain {marker!r} exactly once, found {count}"
    )
    return text[text.index(marker) + len(marker):]


def test_no_zip_switch_when_scripts_parsed_is_declared_and_mapped_in_all_three() -> None:
    """All three scripts must declare, document and map the ``--no-zip`` switch.

    Each platform spells the switch differently, so each is pinned in its own
    spelling; the shared ``zip`` substring only checks that the feature is
    present in all three at all.
    """
    ps1 = _script_text(_PS1_SCRIPT)
    sh = _script_text(_SH_SCRIPT)
    bat = _script_text(_BAT_SCRIPT)
    assert "[switch]$NoZip" in ps1
    assert ".PARAMETER NoZip" in ps1
    assert "--no-zip" in ps1
    assert "by default" in ps1
    assert "--no-zip)" in sh
    assert "no_zip=0" in sh
    assert "no_zip=1" in sh
    assert 'if /i "%arg%"=="--no-zip" set "arg=-NoZip"' in bat
    assert all("zip" in text for text in (ps1, sh, bat))


def test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist() -> None:
    """Zip generation must live only inside the ``--dist`` branch, after the guard.

    Everything after the dist guard is *tail*; the helper invocation must
    appear exactly once there and nowhere before it, so a stray archive call
    outside ``--dist`` (or a second one) fails loudly.  Each tail must keep
    the no-zip guard, which is what makes "no switch" mean "produce a zip".
    Within the tail the smoke test (its timeout / cleanup) and the collected
    message must precede the archive call, and the call must stay inside the
    dist block (before its closing delimiter).
    """
    ps1 = _script_text(_PS1_SCRIPT)
    sh = _script_text(_SH_SCRIPT)
    ps1_tail = _after(ps1, 'if ($Dist -ne "")', _PS1_SCRIPT)
    sh_tail = _after(sh, 'if [ -n "$dist_arg" ]; then', _SH_SCRIPT)
    for name, tail, prefix in (
        (_PS1_SCRIPT.name, ps1_tail, ps1[: ps1.index('if ($Dist -ne "")')]),
        (_SH_SCRIPT.name, sh_tail, sh[: sh.index('if [ -n "$dist_arg" ]; then')]),
    ):
        assert tail.count("tools.pack.zip_dist") == 1, (
            f"{name} must invoke the zip helper exactly once in its dist tail"
        )
        assert prefix.count("tools.pack.zip_dist") == 0, (
            f"{name} must not invoke the zip helper before its dist guard"
        )
    assert "if ($NoZip)" in ps1_tail
    assert 'if [ "$no_zip" -eq 1 ]; then' in sh_tail
    # Order guard: the smoke test (its 30s timeout and temp-file cleanup) and
    # the "Collected ->" message must run before the archive call, and the
    # call must stay inside the --dist block (before its closing delimiter).
    # Note: a bare "finally" also occurs inside the dist block (nested try),
    # so the ps1 closer is pinned as the block-closing "} finally {" pair.
    assert ps1_tail.index("WaitForExit(30000)") < ps1_tail.index("tools.pack.zip_dist")
    assert ps1_tail.index("Remove-Item $smokeOut") < ps1_tail.index("tools.pack.zip_dist")
    assert ps1_tail.index("Collected ->") < ps1_tail.index("tools.pack.zip_dist")
    assert sh_tail.index("timeout 30") < sh_tail.index("tools.pack.zip_dist")
    assert sh_tail.index("Collected ->") < sh_tail.index("tools.pack.zip_dist")
    assert ps1_tail.index("tools.pack.zip_dist") < ps1_tail.index("\n}\nfinally {")
    assert sh_tail.index("tools.pack.zip_dist") < sh_tail.index("\nfi")


def test_no_zip_when_requested_skips_archive_without_touching_existing_files() -> None:
    """The ``--no-zip`` branch must only report the skip; the helper stays in else.

    The skip branch must not clean up, rewrite or hash anything: the stage and
    ``SHA256SUMS.txt`` already produced by the --dist collection must survive
    untouched, which is what "skip the archive" promises.
    """
    ps1 = _script_text(_PS1_SCRIPT)
    sh = _script_text(_SH_SCRIPT)
    ps1_tail = _after(ps1, "if ($NoZip)", _PS1_SCRIPT)
    sh_tail = _after(sh, 'if [ "$no_zip" -eq 1 ]; then', _SH_SCRIPT)
    ps1_skip, _, ps1_else = ps1_tail.partition("} else {")
    sh_skip, _, sh_else = sh_tail.partition("else")
    for name, skip in ((_PS1_SCRIPT.name, ps1_skip), (_SH_SCRIPT.name, sh_skip)):
        assert "skipped" in skip, f"{name} skip branch must report the skip"
        for banned in ("Remove-Item", "rm -rf", "Set-Content", "SHA256SUMS.txt", "zip_dist"):
            assert banned not in skip, (
                f"{name} skip branch must not contain {banned!r}"
            )
    assert "tools.pack.zip_dist" in ps1_else
    assert "tools.pack.zip_dist" in sh_else


def test_help_text_when_scripts_scanned_covers_new_switch() -> None:
    """The sh help slice must reach past every usage, ``--no-zip`` and default line.

    ``show_help()`` prints a fixed ``sed -n '2,Np'`` range; the guard parses N
    out of the script instead of duplicating it, so new header usage lines
    cannot silently fall outside the printed help.  The old ``2,19p`` range is
    banned outright to catch a revert of the endpoint.
    """
    sh = _script_text(_SH_SCRIPT)
    ps1 = _script_text(_PS1_SCRIPT)
    bat = _script_text(_BAT_SCRIPT)
    match = re.search(r"sed -n '2,(\d+)p'", sh)
    assert match is not None, "pack.sh show_help() lost its sed range"
    endpoint = int(match.group(1))
    header = sh.splitlines()[:40]
    usage_lines = [
        number
        for number, line in enumerate(header, start=1)
        if re.match(r"^#\s+\./pack/pack\.sh", line)
    ]
    no_zip_lines = [
        number
        for number, line in enumerate(header, start=1)
        if "--no-zip" in line
    ]
    default_lines = [
        number
        for number, line in enumerate(header, start=1)
        if "by default" in line
    ]
    assert usage_lines, "pack.sh header lost its usage lines"
    assert no_zip_lines, "pack.sh header lost its --no-zip line"
    assert default_lines, "pack.sh header lost its by-default line"
    assert max(usage_lines) <= endpoint, (
        f"usage line {max(usage_lines)} exceeds the sed endpoint {endpoint}"
    )
    assert max(no_zip_lines) <= endpoint, (
        f"--no-zip line {max(no_zip_lines)} exceeds the sed endpoint {endpoint}"
    )
    assert max(default_lines) <= endpoint, (
        f"by-default line {max(default_lines)} exceeds the sed endpoint {endpoint}"
    )
    assert "sed -n '2,19p'" not in sh, "the old help range 2,19p must stay gone"
    assert ".PARAMETER NoZip" in ps1
    assert "by default" in ps1
    assert "--no-zip" in "\n".join(bat.splitlines()[:40])
    assert "by default" in "\n".join(bat.splitlines()[:40])


def test_unknown_arguments_when_sh_parsed_still_exit_two() -> None:
    """Unknown arguments must stay rejected with exit 2; no ``--zip`` flag may exist.

    The catch-all ``*)`` branch is sliced out explicitly so a reordering of
    the ``case`` arms cannot move the rejection away.  The issue's rejected
    ``--zip`` / ``--zip=value`` spellings are banned from the whole script.
    """
    sh = _script_text(_SH_SCRIPT)
    # Anchored to a standalone arm: `--dist=*)` also contains the `*)`
    # substring, so an unanchored index() would slice the wrong branch.
    start_match = re.search(r"^\s+\*\)\s*$", sh, flags=re.MULTILINE)
    assert start_match is not None, "pack.sh lost its `*)` catch-all arm"
    start = start_match.start()
    end = sh.index(";;", start)
    catch_all = sh[start:end]
    assert "unknown argument" in catch_all
    assert "exit 2" in catch_all
    assert "--zip)" not in sh
    assert "--zip=" not in sh


def test_dist_and_smoke_semantics_when_scripts_scanned_are_unchanged() -> None:
    """The pre-existing ``--dist`` collection and smoke-test wiring must survive.

    Pinned as fixed literal checklists per script: the timeout, the checksum
    file, the smoke-test cleanup, the versioned directory name and the summary
    line, plus the spec-interpreted layout copy on POSIX.
    """
    ps1 = _script_text(_PS1_SCRIPT)
    sh = _script_text(_SH_SCRIPT)
    for required in (
        "WaitForExit(30000)",
        "SHA256SUMS.txt",
        "Remove-Item $smokeOut",
        "Collected ->",
        "yate-$version-windows-$arch",
        "Set-Content -Encoding ascii",
    ):
        assert required in ps1, f"pack.ps1 lost {required!r}"
    for required in (
        "timeout 30",
        "sha256sum yate > SHA256SUMS.txt",
        "chmod 0755",
        "yate-$version-linux-$arch",
        "Collected ->",
        "cp -a",
    ):
        assert required in sh, f"pack.sh lost {required!r}"


def test_bat_wrapper_when_mapping_scanned_keeps_existing_mappings() -> None:
    """The bat wrapper must keep every existing mapping and its quoting logic.

    Adding the ``--no-zip`` mapping must not crowd out the four pre-existing
    ones, the early ``SCRIPT`` resolution, the trailing-backslash doubling,
    the exit-code propagation or the PowerShell startup-failure notice.
    """
    bat = _script_text(_BAT_SCRIPT)
    for mapping in ("--onefile", "--skip-changelog", "--dist", "--help"):
        assert f'if /i "%arg%"=="{mapping}"' in bat, (
            f"pack.bat lost its {mapping} mapping"
        )
    assert 'set "SCRIPT=%~dp0pack.ps1"' in bat
    assert 'if "%arg:~-1%"=="\\" set "arg=%arg%\\"' in bat
    assert "exit /b %ERRORLEVEL%" in bat
    assert "if errorlevel 1" in bat, "pack.bat lost its failure notice"
    assert "error: pack.ps1 failed" in bat


def test_zip_helper_when_scanned_keeps_atomic_replace_and_unix_mode() -> None:
    """The zip helper must keep its atomic-swap and mode-bit guarantees.

    Pinned by shape: same-directory ``mkstemp`` temporaries swapped in with
    ``os.replace``, explicit ``external_attr`` mode bits, ``ZIP_DEFLATED``
    compression, exclusion of the smoke-test output and a ``missing_ok``
    cleanup.  The helper stays stdlib-only -- no shell-outs and no third-party
    dependency may appear.
    """
    helper = _script_text(_REPO_ROOT / "tools" / "pack" / "zip_dist.py")
    for required in (
        "os.replace(",
        "external_attr",
        "ZIP_DEFLATED",
        "smoke-out.txt",
        "mkstemp",
        "unlink(missing_ok=True)",
    ):
        assert required in helper, f"zip_dist.py lost {required!r}"
    assert "Compress-Archive" not in helper
    assert "subprocess" not in helper
    allowed_roots = frozenset({
        "argparse", "hashlib", "os", "shutil", "stat", "sys", "tempfile",
        "time", "zipfile", "collections", "pathlib", "typing", "__future__",
    })
    import_roots: set[str] = set()
    for node in ast.walk(ast.parse(helper)):
        if isinstance(node, ast.Import):
            import_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            import_roots.add(node.module.split(".")[0])
    offenders = sorted(import_roots - allowed_roots)
    assert offenders == [], f"zip_dist.py gained non-stdlib imports: {offenders}"
