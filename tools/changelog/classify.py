"""Conventional Commits parsing and categorisation."""

from __future__ import annotations

import re

from .model import Category, Commit, RawCommit

#: ``type(scope)!:: subject`` — bang marks a breaking change.
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?: (?P<subject>.+)$"
)
#: Footer line form: ``BREAKING CHANGE: ...`` (also ``BREAKING-CHANGE:``).
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)

_TYPE_TO_CATEGORY: dict[str, Category] = {
    "feat": Category.FEATURE,
    "fix": Category.FIX,
    "perf": Category.PERFORMANCE,
    "refactor": Category.REFACTOR,
    "docs": Category.DOCS,
    "test": Category.TEST,
    "build": Category.TOOLING,
    "ci": Category.TOOLING,
    "chore": Category.TOOLING,
}


def classify_commit(raw: RawCommit) -> Commit:
    """Parse the subject into ``(category, scope, breaking, summary_en)``.

    Subjects without a recognisable ``type(scope): `` prefix fall into
    :attr:`Category.OTHER` with the full subject kept as the summary.
    """
    is_breaking_footer = _BREAKING_FOOTER_RE.search(raw.body) is not None
    match = _CONVENTIONAL_RE.match(raw.subject)
    if match is None:
        return Commit(
            sha=raw.sha,
            short_sha=raw.short_sha,
            subject=raw.subject,
            body=raw.body,
            author_date=raw.author_date,
            category=Category.OTHER,
            scope=None,
            is_breaking=is_breaking_footer,
            summary_en=raw.subject,
        )
    commit_type = match.group("type").lower()
    bang = match.group("bang") is not None
    scope = match.group("scope")
    return Commit(
        sha=raw.sha,
        short_sha=raw.short_sha,
        subject=raw.subject,
        body=raw.body,
        author_date=raw.author_date,
        category=_TYPE_TO_CATEGORY.get(commit_type, Category.OTHER),
        scope=scope,
        is_breaking=bang or is_breaking_footer,
        summary_en=match.group("subject").strip(),
    )


def is_release_bump_commit(commit: Commit) -> bool:
    """``chore(release): vX.Y.Z`` commits define a boundary but are not entries."""
    return commit.category is Category.TOOLING and commit.scope == "release"


def is_changelog_entry(commit: Commit) -> bool:
    """Release-bump commits are boundaries only — never rendered entries."""
    return not is_release_bump_commit(commit)
