"""Rule profiles for the en and zh languages.

Each profile is a mapping of pymarkdown rule IDs to their configuration.
Built-in rules are configured via the pymarkdown API; custom plugins
(loaded only for ``zh``) are enabled/disabled via the same mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_EN_PROPERTIES: dict[str, str | int | bool] = {
    # Config keys are "plugins.<plugin_name>.<item>": pymarkdown resolves
    # them by rule *name*, not by the MDnnn identifier.
    "plugins.heading-style.style": "atx",  # MD003
    "plugins.ul-style.style": "dash",  # MD004
    "plugins.ul-indent.indent": 4,  # MD007
    "plugins.no-multiple-blanks.maximum": 1,  # MD012
    "plugins.line-length.line_length": 100,  # MD013
    "plugins.no-duplicate-heading.siblings_only": True,  # MD024
    "plugins.no-trailing-punctuation.punctuation": ".,;:!?",  # MD026
    "plugins.ol-prefix.style": "one_or_ordered",  # MD029
    "plugins.hr-style.style": "---",  # MD035
    "plugins.code-block-style.style": "fenced",  # MD046
    "plugins.code-fence-style.style": "backtick",  # MD048
}

_ZH_PROPERTIES: dict[str, str | int | bool] = {
    **_EN_PROPERTIES,
    "plugins.no-trailing-punctuation.punctuation": ".;:!?。，；：！？",
}

#: The profile is an **allowlist**: pymarkdown enables most of its ~60
#: rules by default, so the engine disables every rule first and then
#: enables exactly this set.  Toggling a handful of rules off (the old
#: approach) silently left the remaining defaults active -- MD027, MD028,
#: MD030, MD044 and friends reported violations the profile never asked
#: for, and several of them are quadratic enough to quadruple the run
#: time on large documents.
#:
#: Deliberately absent: MD002/MD006 (deprecated), MD011 (reversed links),
#: MD014 (commands show output), MD020/MD021 (closed ATX spacing), MD033
#: (inline HTML), MD036 (emphasis as heading), MD043 (required headings),
#: MD044/MD045 (proper names, alt text), MD049/MD050 (emphasis style),
#: MD051/MD053/MD054 (link fragments/definitions/style), MD055/MD056/
#: MD058/MD059/MD060 (tables).
_EN_ENABLED: frozenset[str] = frozenset(
    {
        "MD001", "MD003", "MD004", "MD005", "MD007", "MD009", "MD010",
        "MD012", "MD013", "MD018", "MD019", "MD022", "MD023", "MD024",
        "MD025", "MD026", "MD029", "MD031", "MD032", "MD034", "MD035",
        "MD037", "MD038", "MD039", "MD040", "MD041", "MD042", "MD046",
        "MD047", "MD048",
    }
)

_ZH_ENABLED: frozenset[str] = (
    (_EN_ENABLED - {"MD013", "MD041"}) | {"YM001", "YM002", "YM003", "YM004"}
)


@dataclass(frozen=True)
class RuleProfile:
    """A set of rule configurations for one language."""

    lang: str
    enabled_rules: frozenset[str]
    properties: dict[str, str | int | bool]


_EN_PROFILE = RuleProfile(
    lang="en",
    enabled_rules=_EN_ENABLED,
    properties=_EN_PROPERTIES,
)

_ZH_PROFILE = RuleProfile(
    lang="zh",
    enabled_rules=_ZH_ENABLED,
    properties=_ZH_PROPERTIES,
)

#: The supported language profiles; the CLI feeds this to ``choices``.
LANGS: tuple[str, ...] = ("zh", "en")


def get_profile(lang: str) -> RuleProfile:
    """Return the rule profile for *lang* ('zh' or 'en')."""
    if lang == "zh":
        return _ZH_PROFILE
    if lang == "en":
        return _EN_PROFILE
    raise ValueError(
        f"unknown language profile: {lang!r} (expected one of {LANGS})"
    )


def plugin_dir() -> Path:
    """Return the path to the custom plugins directory."""
    return Path(__file__).parent / "plugins"


def lang_for_path(path: str) -> str:
    """Infer the lint profile for *path*; one of ``'zh'`` or ``'en'``.

    Contract (mirrored by ``.githooks/pre-commit`` and the tests):

    - ``*.zh.md`` -> ``zh``
    - ``*.en.md`` -> ``en`` (checked before the ``.trae`` rule, so an
      English file stays English wherever it lives)
    - any file below a ``.trae`` directory -> ``zh``
    - everything else -> ``en``
    """
    normalized = path.replace("\\", "/").lower()
    if normalized.endswith(".zh.md"):
        return "zh"
    if normalized.endswith(".en.md"):
        return "en"
    if ".trae" in PurePosixPath(normalized).parts:
        return "zh"
    return "en"
