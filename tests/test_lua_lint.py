"""Tests for the Lua lint used as the game pack's merge gate.

The linter itself is :mod:`tools.lint_lua`; the syntax rule runs through lupa,
so the whole module skips without the optional ``yate[lua]`` extra.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest

from tools import lint_lua
from yate.paths import bundled_extensions_dir

#: Live-lua marker: the syntax rule needs the real parser.
requires_lupa = pytest.mark.skipif(
    importlib.util.find_spec("lupa") is None,
    reason="lupa is not installed (live-lua group)",
)


@pytest.fixture(scope="module")
def compiler() -> Callable[[str, str], None]:
    """The lupa-backed ``compile(source, name)`` used by the syntax rule."""
    return lint_lua.lua_compiler()


@pytest.fixture(scope="module")
def modules() -> set[str]:
    """The require() whitelist (``yate`` plus bundled ``lib/*.lua``)."""
    return lint_lua.allowed_modules()


def _lint(
    tmp_path: Path,
    source: str,
    compiler: Callable[[str, str], None],
    modules: set[str],
) -> list[lint_lua.Issue]:
    """Write *source* to a temporary Lua file and lint it."""
    path = tmp_path / "probe.lua"
    path.write_text(source, encoding="utf-8", newline="")
    return lint_lua.check_source(path, source, modules, compiler)


@requires_lupa
def test_bundled_lua_files_pass_the_linter(
    compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """Every shipped Lua file is clean (the real merge gate)."""
    issues = lint_lua.check_paths([bundled_extensions_dir()], modules, compiler)

    assert issues == []


@requires_lupa
def test_syntax_error_is_reported_with_a_line_number(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """A broken chunk is reported as ``syntax`` with a usable line."""
    issues = _lint(tmp_path, "return (\n", compiler, modules)

    syntax = [issue for issue in issues if issue.rule == "syntax"]
    assert len(syntax) == 1
    assert syntax[0].line >= 1


@requires_lupa
def test_tabs_and_trailing_space_are_reported(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """Tabs and trailing whitespace each produce one finding."""
    rules = {issue.rule for issue in _lint(tmp_path, "\tlocal x = 1  \n", compiler, modules)}

    assert {"tab", "trailing-space"} <= rules


@requires_lupa
def test_long_line_is_reported(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """A line above the width limit is flagged."""
    source = "local x = " + '"' + "a" * 120 + '"' + "\n"

    rules = {issue.rule for issue in _lint(tmp_path, source, compiler, modules)}

    assert "line-length" in rules


@requires_lupa
def test_missing_final_newline_is_reported(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """A file not ending in exactly one newline is flagged."""
    rules = {issue.rule for issue in _lint(tmp_path, "local x = 1", compiler, modules)}

    assert "eof-newline" in rules


def test_crlf_file_is_reported(tmp_path: Path) -> None:
    """A CRLF file read through ``check_paths`` still trips the crlf rule.

    Exercises the read boundary (``newline=""``): universal-newline
    translation would normalize the CR characters away before
    :func:`lint_lua.check_source` ever sees them.
    """
    path = tmp_path / "crlf.lua"
    path.write_bytes(b"local x = 1\r\n")

    issues = lint_lua.check_paths([path], set(), lambda source, name: None)

    assert "crlf" in {issue.rule for issue in issues}


@requires_lupa
def test_banned_calls_are_reported(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """print / io / os.execute are all rejected."""
    source = 'print("x")\nio.open("y")\nos.execute("z")\n'

    issues = [issue for issue in _lint(tmp_path, source, compiler, modules) if issue.rule == "banned-call"]

    assert len(issues) == 3


@requires_lupa
def test_global_leak_is_reported_and_whitelisted_names_pass(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """A bare global assignment fails; a whitelisted name and a local pass."""
    leaked = _lint(tmp_path, "foo = 1\n", compiler, modules)
    allowed = _lint(tmp_path, "yate = {}\n", compiler, modules)
    local = _lint(tmp_path, "local bar = 1\nbar = 2\n", compiler, modules)

    assert [issue.rule for issue in leaked] == ["global-leak"]
    assert [issue.rule for issue in allowed] == []
    assert [issue.rule for issue in local] == []


@requires_lupa
def test_unknown_require_is_reported(
    tmp_path: Path, compiler: Callable[[str, str], None], modules: set[str]
) -> None:
    """Only ``yate`` and the bundled lib modules may be required."""
    unknown = _lint(tmp_path, 'local m = require("nope")\n', compiler, modules)
    known = _lint(
        tmp_path,
        'local yate = require("yate")\nlocal engine = require("game_engine")\n',
        compiler,
        modules,
    )

    assert [issue.rule for issue in unknown] == ["require"]
    assert known == []


@requires_lupa
def test_main_reports_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean tree exits 0; a dirty one exits 1 and prints the finding."""
    clean = tmp_path / "clean"
    clean.mkdir()
    # newline="" keeps the fixture LF: the default would translate "\n" to
    # CRLF on Windows and trip the crlf rule the read boundary now exposes.
    (clean / "ok.lua").write_text("local x = 1\nreturn x\n", encoding="utf-8", newline="")

    assert lint_lua.main([str(clean)]) == lint_lua.EXIT_OK
    assert "0 issue(s)" in capsys.readouterr().out

    (clean / "bad.lua").write_text(
        "local x = 1\n\tlocal y = 2\n", encoding="utf-8", newline=""
    )

    assert lint_lua.main([str(clean)]) == lint_lua.EXIT_ISSUES
    output = capsys.readouterr().out
    assert "bad.lua:2:" in output
    assert "1 issue(s)" in output
