"""Data models shared across the changelog toolchain."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(Enum):
    """Conventional-commit categories; the value is the canonical type name.

    ``build`` / ``ci`` / ``chore`` all fold into :attr:`TOOLING`.
    """

    FEATURE = "feat"
    FIX = "fix"
    PERFORMANCE = "perf"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    TOOLING = "tooling"
    OTHER = "other"


@dataclass(frozen=True)
class RawCommit:
    """A commit as collected from git, before classification."""

    sha: str
    short_sha: str
    author_date: str  # YYYY-MM-DD, display only — never used for segmentation
    subject: str
    body: str


@dataclass(frozen=True)
class Commit:
    """A classified commit entry ready for rendering."""

    sha: str
    short_sha: str
    subject: str
    body: str
    author_date: str
    category: Category
    scope: str | None
    is_breaking: bool
    summary_en: str  # subject without the type(scope): prefix


@dataclass(frozen=True)
class TagRef:
    """A git tag naming a version, e.g. ``v0.2.0``."""

    name: str
    sha: str


@dataclass(frozen=True)
class VersionBump:
    """A commit that added/changed ``__version__`` in ``yate/__init__.py``."""

    sha: str
    version: str


@dataclass(frozen=True)
class Boundary:
    """A version boundary commit: the version becomes effective HERE.

    The boundary commit itself belongs to the new version, i.e. its segment
    spans ``[boundary commit, next newer boundary)``.
    """

    version: str
    sha: str
    date: str
    from_tag: bool


@dataclass
class ReleaseSegment:
    """One version section of the changelog (newest first in output)."""

    version: str | None  # None = Unreleased
    date: str | None  # boundary commit date; None for Unreleased
    commits: list[Commit] = field(default_factory=list[Commit])
    range_from: str | None = None  # compare-range start (tag ref or ROOT)
    range_to: str | None = None  # compare-range end (tag ref or HEAD)
    initial: bool = False  # first release → renders the "Initial release" note
