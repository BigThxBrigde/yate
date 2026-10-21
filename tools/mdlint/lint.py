"""Lint engine wrapping the pymarkdownlnt Python API.

The engine owns one configured ``PyMarkdownApi`` instance per language
profile and exposes string- and file-level scan/fix helpers. It depends
only on ``pymarkdown.api`` and :mod:`tools.mdlint.rules`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownScanFailure

from tools.mdlint.rules import RuleProfile, get_profile, plugin_dir

_LANGS_WITH_CUSTOM_PLUGINS = ("zh",)

#: pymarkdown logs its internal failures -- full tracebacks included -- on
#: its own logger.  The CLI owns error reporting, so those records must never
#: reach the terminal: silence the package logger and stop it from bubbling
#: into the host application's root handlers (the wiki publisher embeds this
#: engine too).
logging.getLogger("pymarkdown").addHandler(logging.NullHandler())
logging.getLogger("pymarkdown").propagate = False

#: Longest one-line error text the CLI prints for a failed file.
_MAX_ERROR_CHARS = 300


def error_message(exc: BaseException) -> str:
    """Render *exc* as one bounded line, never as a traceback.

    ``PyMarkdownApiException`` carries the library's whole formatted stack
    in its message, so the first line is the only useful part: it names the
    failure (``Unexpected Error(AssertionError): ...``) plus, for
    ``BadPluginError``, the location and plugin id.
    """
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    text = " ".join(lines[0].split()) if lines else type(exc).__name__
    if len(text) <= _MAX_ERROR_CHARS:
        return text
    return text[: _MAX_ERROR_CHARS - 3] + "..."


@dataclass(frozen=True)
class LintViolation:
    """One lint violation."""

    rule_id: str
    rule_name: str
    line: int
    column: int
    message: str


def _to_violation(failure: PyMarkdownScanFailure) -> LintViolation:
    """Map a pymarkdown scan failure to a :class:`LintViolation`."""
    message = failure.extra_error_information or failure.rule_name
    return LintViolation(
        rule_id=failure.rule_id,
        rule_name=failure.rule_name,
        line=failure.line_number,
        column=failure.column_number,
        message=message,
    )


def _configure_api(
    api: PyMarkdownApi, profile: RuleProfile, plugin_dir: Path
) -> PyMarkdownApi:
    """Apply a rule profile to a fresh pymarkdown API instance.

    pymarkdown enables most of its rules by default, so the profile is
    applied as an allowlist: ``*`` turns everything off, then the profile
    enables exactly the rules it owns (custom ``YM`` plugins included --
    they are resolved after the plugin path is registered below).
    """
    api = api.disable_rule_by_identifier("*")
    for rule_id in sorted(profile.enabled_rules):
        api = api.enable_rule_by_identifier(rule_id.lower())
    for name, value in sorted(profile.properties.items()):
        if isinstance(value, bool):
            api = api.set_boolean_property(name, value)
        elif isinstance(value, int):
            api = api.set_integer_property(name, value)
        else:
            api = api.set_string_property(name, str(value))
    if profile.lang in _LANGS_WITH_CUSTOM_PLUGINS:
        api = api.add_plugin_path(str(plugin_dir))
    return api


class LintEngine:
    """Scan and fix Markdown text using pymarkdown with a given rule profile."""

    def __init__(self, lang: str, *, custom_plugin_dir: Path | None = None) -> None:
        """Initialise with *lang* profile ('zh' or 'en').

        *custom_plugin_dir* overrides the shared plugin directory
        (:func:`tools.mdlint.rules.plugin_dir`).
        """
        self._profile = get_profile(lang)
        self._plugin_dir = (
            custom_plugin_dir if custom_plugin_dir is not None else plugin_dir()
        )
        self._api = _configure_api(PyMarkdownApi(), self._profile, self._plugin_dir)

    @property
    def lang(self) -> str:
        """The language profile this engine was built with."""
        return self._profile.lang

    def enabled_rule_ids(self) -> list[str]:
        """Sorted IDs of every rule enabled by the profile."""
        return sorted(self._profile.enabled_rules)

    def scan(self, text: str) -> list[LintViolation]:
        """Return every violation found in *text*."""
        # pymarkdown rejects blank documents as invalid arguments; a page
        # with no content has nothing to lint, so it is clean, not a failure.
        if not text.strip():
            return []
        result = self._api.scan_string(text)
        return [_to_violation(failure) for failure in result.scan_failures]

    def fix(self, text: str) -> tuple[str, list[LintViolation]]:
        """Auto-fix what pymarkdown can; return (fixed_text, remaining)."""
        if not text.strip():
            return text, []
        result = self._api.fix_string(text)
        fixed = result.fixed_file
        return fixed, self.scan(fixed)

    def scan_file(self, path: Path) -> list[LintViolation]:
        """Scan a file on disk."""
        return self.scan(path.read_text(encoding="utf-8"))

    def fix_file(self, path: Path) -> tuple[bool, list[LintViolation]]:
        """Fix a file in place; return (was_fixed, remaining)."""
        original = path.read_text(encoding="utf-8")
        fixed, remaining = self.fix(original)
        if fixed != original:
            # newline="" keeps LF: the default translation would rewrite the
            # file as CRLF on Windows and smuggle it into the commit.
            path.write_text(fixed, encoding="utf-8", newline="")
            return True, remaining
        return False, remaining
