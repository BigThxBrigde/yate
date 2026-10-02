"""Guards for the bundled Textual stylesheets under ``yate/resources``.

Every widget ``DEFAULT_CSS`` must come from :func:`yate.paths.load_tcss` (no
inline CSS literals anywhere in ``yate/``), every bundled ``*.tcss`` must be
a real stylesheet, and the loader keeps its cache and fail-fast contracts --
plus the shell-level guards for ``app.tcss`` itself.
"""

from __future__ import annotations

import ast
from importlib.resources import files
from pathlib import Path

import pytest

from yate.app import YateApp
from yate.paths import load_tcss

#: Repository root / the ``yate`` package, for the AST-based scans below.
PROJECT: Path = Path(__file__).resolve().parent.parent
YATE: Path = PROJECT / "yate"


def test_app_tcss_resource_exists_and_is_nonempty() -> None:
    """resources/app.tcss ships with the package and holds real rules."""
    text = files("yate.resources").joinpath("app.tcss").read_text(encoding="utf-8")
    assert "#editor-col" in text


def test_yateapp_css_matches_bundled_tcss() -> None:
    """``YateApp.CSS`` comes from the bundled tcss, not an inline literal."""
    text = files("yate.resources").joinpath("app.tcss").read_text(encoding="utf-8")
    assert YateApp.CSS == text


def _called_name(func: ast.expr) -> str:
    """A short readable name for a ``Call`` node's callee (violation reports)."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return type(func).__name__


def _default_css_violations(path: Path) -> list[str]:
    """``file:line`` reports for ``DEFAULT_CSS`` assignments in *path* that
    are not ``load_tcss("<name>.tcss")`` calls pointing at a bundled
    resource."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "DEFAULT_CSS"
                for target in stmt.targets
            ):
                continue
            where = f"{path.relative_to(PROJECT).as_posix()}:{stmt.lineno}"
            value = stmt.value
            if not isinstance(value, ast.Call):
                out.append(
                    f"{where}: DEFAULT_CSS must be a load_tcss(...) call, "
                    f"got inline {type(value).__name__}"
                )
                continue
            called = _called_name(value.func)
            if called != "load_tcss":
                out.append(
                    f"{where}: DEFAULT_CSS must be loaded via load_tcss, "
                    f"got {called}"
                )
                continue
            arg = value.args[0] if len(value.args) == 1 else None
            raw = arg.value if isinstance(arg, ast.Constant) else None
            if value.keywords or not isinstance(raw, str):
                out.append(
                    f"{where}: load_tcss must take exactly one str constant"
                )
                continue
            if not (YATE / "resources" / raw).is_file():
                out.append(
                    f"{where}: load_tcss({raw!r}) target "
                    f"yate/resources/{raw} does not exist"
                )
    return out


def test_widget_default_css_comes_from_load_tcss() -> None:
    """No inline CSS literals: every ``DEFAULT_CSS`` in ``yate/`` is a
    ``load_tcss("<name>.tcss")`` call whose resource really is bundled, so a
    typo'd stylesheet name fails statically before any runtime fail-fast."""
    violations: list[str] = []
    for path in YATE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        violations.extend(_default_css_violations(path))
    assert violations == [], "\n".join(violations)


def test_bundled_tcss_resources_are_nonempty() -> None:
    """Every bundled ``*.tcss`` holds real rules: non-blank text with at
    least one ``{`` -- a blanked or truncated stylesheet trips here before
    any UI smoke does."""
    resources = sorted(
        (r for r in files("yate.resources").iterdir() if r.name.endswith(".tcss")),
        key=lambda r: r.name,
    )
    assert resources, "no bundled .tcss resources found"
    for resource in resources:
        text = resource.read_text(encoding="utf-8")
        assert text.strip(), f"{resource.name} is empty"
        assert "{" in text, f"{resource.name} holds no rule"


def test_load_tcss_returns_cached_string() -> None:
    """A second ``load_tcss`` call returns the very same object: the
    ``lru_cache`` reads each stylesheet from disk at most once per process
    (``str`` is immutable, so identity is a safe assertion)."""
    first = load_tcss("app.tcss")
    second = load_tcss("app.tcss")
    assert first is second


def test_load_tcss_missing_resource_raises_runtime_error() -> None:
    """A missing stylesheet fails fast with the actionable message --
    exceptions are not cached, so every call re-raises."""
    with pytest.raises(RuntimeError, match="could not be read"):
        load_tcss("no-such-stylesheet.tcss")
