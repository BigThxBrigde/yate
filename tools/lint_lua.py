"""Minimal Lua lint for the bundled extensions (``yate/extensions/**/*.lua``).

The repository has no ``luacheck`` / ``stylua`` / ``lua-language-server`` on
PATH, but the ``lupa`` bridge the runtime already uses parses real Lua.  This
tool therefore combines the authoritative syntax check (lupa compiles the
chunk) with the textual style guards the repository applies to Python:

  syntax        the chunk must compile (error carries the line number)
  tab           no tab characters
  trailing-space no trailing whitespace
  line-length   at most MAX_LINE_LENGTH display characters
  crlf          LF line endings only
  eof-newline   exactly one trailing newline
  banned-call   no print() / io. / os.execute / os.exit / dofile / loadfile
  global-leak   no bare top-level global assignment or global function
  require       require() only names "yate" or a bundled lib/*.lua module

Usage::

    python tools/lint_lua.py                 # the bundled extensions directory
    python tools/lint_lua.py path/to/file.lua

Exit codes: 0 clean, 1 issues found, 2 lupa missing (environment problem).
"""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yate.paths import bundled_extensions_dir

#: Exit code when every checked file is clean.
EXIT_OK: int = 0

#: Exit code when at least one issue was reported.
EXIT_ISSUES: int = 1

#: Exit code when the Lua parser dependency is unavailable.
EXIT_UNAVAILABLE: int = 2

#: Display width limit per line (matches the Python style rule).
MAX_LINE_LENGTH: int = 100

#: Top-level names an extension may assign or define as a global function.
ALLOWED_GLOBALS: frozenset[str] = frozenset(
    {"yate", "api", "mod", "setup", "teardown"}
)

#: Calls an extension must not make (the editor owns process and stdio).
BANNED_CALLS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bprint\s*\("),
    re.compile(r"\bio\s*\."),
    re.compile(r"\bos\s*\.\s*execute"),
    re.compile(r"\bos\s*\.\s*exit"),
    re.compile(r"\bdofile\s*\("),
    re.compile(r"\bloadfile\s*\("),
)

#: A bare top-level assignment: ``name = ...`` (not ``==``, not a local).
_GLOBAL_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*)\s*=(?!=)")

#: A bare top-level function definition (module-table methods have a dot).
_GLOBAL_FUNC_RE = re.compile(r"^function\s+([A-Za-z_]\w*)\s*\(")

#: ``local name`` / ``local name = ...`` declarations (forward declarations
#: included: ``local spawn_piece`` followed by ``spawn_piece = function()``).
_LOCAL_DECL_RE = re.compile(r"\blocal\s+([A-Za-z_]\w*)\s*(?:=|$)")

#: ``require("name")`` / ``require('name')``.
_REQUIRE_RE = re.compile(r"\brequire\s*\(\s*[\"']([^\"']+)[\"']\s*\)")

#: Line number inside a lupa syntax error, e.g. ``[string "x"]:12: ...``.
_SYNTAX_LINE_RE = re.compile(r":(\d+):")

#: Block comment opener / closer used by the comment stripper.
_BLOCK_OPEN: str = "--[["
_BLOCK_CLOSE: str = "]]"


@dataclass(frozen=True)
class Issue:
    """One lint finding: where, which rule, and why."""

    path: Path
    line: int
    rule: str
    message: str

    def format(self, root: Path) -> str:
        """Render as ``relative/path.lua:12: [rule] message``."""
        try:
            shown = self.path.relative_to(root).as_posix()
        except ValueError:
            shown = self.path.as_posix()
        return f"{shown}:{self.line}: [{self.rule}] {self.message}"


def lua_compiler() -> Callable[[str, str], None]:
    """Return a ``compile(source, name)`` callable backed by lupa.

    ``lupa`` stores no stubs, so the runtime object is typed ``Any`` with the
    documented reason: everything below it is the parsed Lua chunk, not data
    this tool inspects.  Raises :class:`ImportError` when the package is
    missing -- the caller turns that into exit code 2.
    """
    lupa = importlib.import_module("lupa")
    runtime: Any = lupa.LuaRuntime()  # noqa: Any - lupa ships no stubs

    def compile_source(source: str, name: str) -> None:
        """Compile one chunk, raising the lupa syntax error on failure."""
        runtime.compile(source, name)

    return compile_source


def allowed_modules() -> set[str]:
    """Module names a bundled script may ``require``: yate plus ``lib/*.lua``."""
    names = {"yate"}
    directory = bundled_extensions_dir() / "lib"
    if directory.is_dir():
        names.update(path.stem for path in directory.glob("*.lua"))
    return names


def strip_comments(source: str) -> list[str]:
    """Remove ``--`` and ``--[[ ]]`` comments, preserving the line count.

    A textual approximation: a ``--`` sequence inside a string literal ends
    the line early.  The rule set only scans bundled extension sources, and
    the approximation is pinned by tests instead of hidden.
    """
    stripped: list[str] = []
    in_block = False
    for line in source.split("\n"):
        if in_block:
            end = line.find(_BLOCK_CLOSE)
            if end == -1:
                stripped.append("")
                continue
            in_block = False
            line = line[end + len(_BLOCK_CLOSE) :]
        line = re.sub(r"--\[\[.*?\]\]", "", line)
        opener = line.find(_BLOCK_OPEN)
        if opener != -1:
            in_block = True
            line = line[:opener]
        stripped.append(line.split("--", 1)[0])
    return stripped


def check_source(
    path: Path,
    source: str,
    modules: set[str],
    compile_source: Callable[[str, str], None],
) -> list[Issue]:
    """Lint one Lua source text and return every finding."""
    issues: list[Issue] = []
    try:
        compile_source(source, path.name)
    except Exception as exc:  # noqa: BLE001 - lupa error types are not public
        message = str(exc)
        match = _SYNTAX_LINE_RE.search(message)
        line = int(match.group(1)) if match is not None else 1
        issues.append(Issue(path, line, "syntax", message.splitlines()[0]))

    if "\r" in source:
        issues.append(Issue(path, 1, "crlf", "file contains CR characters"))
    if not source.endswith("\n"):
        issues.append(Issue(path, len(source.split("\n")), "eof-newline", "missing final newline"))
    elif source.endswith("\n\n"):
        issues.append(Issue(path, len(source.split("\n")) - 1, "eof-newline", "extra blank line at end"))

    code_lines = strip_comments(source)
    for number, raw in enumerate(source.split("\n"), start=1):
        if "\t" in raw:
            issues.append(Issue(path, number, "tab", "tab character"))
        if raw != raw.rstrip():
            issues.append(Issue(path, number, "trailing-space", "trailing whitespace"))
        if len(raw) > MAX_LINE_LENGTH:
            issues.append(
                Issue(
                    path,
                    number,
                    "line-length",
                    f"{len(raw)} characters (limit {MAX_LINE_LENGTH})",
                )
            )

    locals_declared: set[str] = set()
    for code in code_lines:
        locals_declared.update(_LOCAL_DECL_RE.findall(code))

    for number, code in enumerate(code_lines, start=1):
        for pattern in BANNED_CALLS:
            if pattern.search(code):
                issues.append(
                    Issue(path, number, "banned-call", f"forbidden call: {pattern.pattern}")
                )
        assign = _GLOBAL_ASSIGN_RE.match(code)
        if (
            assign is not None
            and assign.group(1) not in ALLOWED_GLOBALS
            and assign.group(1) not in locals_declared
        ):
            issues.append(
                Issue(path, number, "global-leak", f"global assignment: {assign.group(1)}")
            )
        function = _GLOBAL_FUNC_RE.match(code)
        if (
            function is not None
            and function.group(1) not in ALLOWED_GLOBALS
            and function.group(1) not in locals_declared
        ):
            issues.append(
                Issue(
                    path,
                    number,
                    "global-leak",
                    f"global function: {function.group(1)}",
                )
            )
        for module in _REQUIRE_RE.findall(code):
            if module not in modules:
                issues.append(
                    Issue(path, number, "require", f"unknown module: {module}")
                )
    return issues


def check_paths(
    paths: Sequence[Path],
    modules: set[str],
    compile_source: Callable[[str, str], None],
) -> list[Issue]:
    """Lint every ``*.lua`` file under *paths* (files and directories)."""
    issues: list[Issue] = []
    for target in paths:
        files = sorted(target.rglob("*.lua")) if target.is_dir() else [target]
        for path in files:
            try:
                # newline="" keeps CR characters verbatim so the crlf rule
                # can see them; the default universal-newlines mode would
                # normalize CRLF away and hide the finding.
                with path.open(encoding="utf-8", newline="") as handle:
                    source = handle.read()
            except (OSError, UnicodeDecodeError) as exc:
                # A file the linter cannot read (missing, locked, or not
                # valid UTF-8) is a finding, never a traceback: the CLI
                # promises exit codes 0/1/2 only.
                issues.append(Issue(path, 1, "read", str(exc)))
                continue
            issues.extend(check_source(path, source, modules, compile_source))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    """Run the linter over the CLI arguments (default: bundled extensions)."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(argument) for argument in arguments] or [bundled_extensions_dir()]
    try:
        compile_source = lua_compiler()
    except ImportError:
        print("lint_lua: lupa is not installed; install with: pip install yate[lua]")
        return EXIT_UNAVAILABLE
    issues = check_paths(targets, allowed_modules(), compile_source)
    root = Path.cwd()
    for issue in issues:
        print(issue.format(root))
    print(f"{len(issues)} issue(s)")
    return EXIT_OK if not issues else EXIT_ISSUES


if __name__ == "__main__":
    raise SystemExit(main())
