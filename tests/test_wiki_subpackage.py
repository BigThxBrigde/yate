"""Structural guards for the ``tools.pack.wiki`` subpackage split.

The former single-file module (2149 lines) became a subpackage with a
re-exporting facade; these tests pin the facts the rest of the suite
relies on:

- the patched-name surface: the test suite couples to the module globals
  of the former single file (``monkeypatch.setattr(wiki, ...)``), so
  every name it patches must stay importable from the facade;
- the late-bound facade wiring: submodules read every patched name
  through ``import tools.pack.wiki as _wiki_facade`` at call time, so a
  patch on the facade actually reaches the production read site;
- the split layout: ``tools/pack/wiki.py`` is gone and each submodule is
  below the 800-line threshold (the guard's own convention).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import tools.pack.wiki as wiki

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE = _ROOT / "tools" / "pack" / "wiki"

#: Every name the wiki test suite replaces on the facade module object
#: (``monkeypatch.setattr(wiki, "<name>", ...)``).  The facade must keep
#: exporting each of them, and the submodule that reads it must resolve it
#: through the late-bound facade object, or the patch would not reach the
#: production call site.
PATCHED_NAMES: dict[str, str] = {
    "translate_via_cmd": "translate",
    "_run_translate": "translate",
    "as_completed": "translate",
    "TRANSLATE_TIMEOUT_S": "translate",
    "_STOP_POLL_S": "translate",
    "Progress": "lint",
    "ThreadPoolExecutor": "translate",
    "subprocess": "publish",
    "_emit_mode": "translate",
    "_drain_collected_failures": "translate",
    "_get_lint_engine": "lint",
    "PARALLEL_LINT_MIN_CHARS": "lint",
    "collect_sources": "run",
    "run_git": "publish",
    "job_ceiling": "report",
}

#: Patched names with no intra-package read site: ``run`` is the entry
#: point the CLI calls through the facade, so exporting it from the
#: facade is all the patching contract needs.
FACADE_ONLY_PATCHED_NAMES: frozenset[str] = frozenset({"run"})


def test_facade_still_exports_the_patched_name_surface() -> None:
    """Every name the suite patches resolves from the facade module object."""
    for name in {**PATCHED_NAMES} | {n: "" for n in FACADE_ONLY_PATCHED_NAMES}:
        assert hasattr(wiki, name), f"tools.pack.wiki.{name} must stay importable"


def test_patched_reads_go_through_the_late_bound_facade() -> None:
    """Each defining submodule resolves its patched names via ``_wiki_facade``.

    The facade is imported as a module object and the name is resolved at
    call time (``_wiki_facade.<name>``); a ``from ... import <name>``
    binding would freeze the pre-patch value at import time and silently
    break every ``monkeypatch.setattr(wiki, ...)`` in the suite.  This is
    the same late-binding contract the main plan's correction section
    prescribes for the split.
    """
    for name, module in PATCHED_NAMES.items():
        source = (_PACKAGE / f"{module}.py").read_text(encoding="utf-8")
        assert "import tools.pack.wiki as _wiki_facade" in source, (
            f"{module}.py must import the facade module object"
        )
        assert f"_wiki_facade.{name}" in source, (
            f"{module}.py must read the patched name {name!r} through the "
            "late-bound facade, not a frozen from-import binding"
        )


def test_single_file_module_is_gone_and_submodules_stay_below_threshold() -> None:
    """``tools/pack/wiki.py`` is gone; each submodule stays under 800 lines."""
    assert not (_ROOT / "tools" / "pack" / "wiki.py").exists(), (
        "the flat single-file module must be deleted after the split"
    )
    files = sorted(_PACKAGE.glob("*.py"))
    assert {path.name for path in files} == {
        "__init__.py",
        "lint.py",
        "sources.py",
        "report.py",
        "publish.py",
        "translate.py",
        "run.py",
    }, "the split layout (six submodules + facade) is frozen by this guard"
    for path in files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert lines < 800, f"{path.name} grew past the 800-line threshold: {lines}"


def test_submodules_import_only_through_the_facade_path() -> None:
    """Intra-package imports are absolute and the facade is the public path.

    Mirrors the R14 precedent: the facade import path
    ``tools.pack.wiki`` is the public surface; submodules are internal
    implementation.  Inside the package, cross-submodule references use
    absolute ``from tools.pack.wiki.<module> import ...`` imports only.
    """
    for path in sorted(_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level != 0:
                raise AssertionError(
                    f"{path.name}: relative imports are banned "
                    "(absolute imports only)"
                )
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                "tools.pack.wiki."
            ):
                tail = node.module.removeprefix("tools.pack.wiki.")
                assert "." not in tail and tail in {
                    "lint",
                    "sources",
                    "report",
                    "publish",
                    "translate",
                    "run",
                }, f"{path.name}: unexpected intra-package import {node.module}"


def test_facade_reexports_resolve_at_runtime() -> None:
    """The facade's ``__all__`` names all resolve (no stale export)."""
    module = importlib.import_module("tools.pack.wiki")
    for name in module.__all__:
        assert getattr(module, name) is not None, (
            f"facade export {name!r} does not resolve"
        )
