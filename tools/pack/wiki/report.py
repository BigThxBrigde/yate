"""Wiki reporting: Home/_Sidebar navigation, page plans and progress rows.

Holds the navigation renderer :func:`_nav_documents`, the per-page
plan/outcome records the translation stage communicates with
(:class:`_PagePlan` / :class:`_PageOutcome` / :class:`_TranslationReport`),
the live row board :class:`_ProgressBoard` and the concurrency-clamp trio
(:func:`job_ceiling` / :func:`resolve_jobs` / :func:`chunk_pages`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import tools.pack.wiki as _wiki_facade
from rich.markup import escape
from rich.progress import Progress, TaskID

from tools.pack.wiki.lint import BATCH_SIZE, cpu_count
from tools.pack.wiki.sources import (
    SECTION_GUIDES,
    SECTION_NOTES,
    SECTION_PLANS,
    SECTION_REVIEWS,
    SECTION_SETS,
    WikiPage,
    _ZH_SUFFIX,
    _link,
    _page_base,
    _page_title,
)

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "BATCH_SIZE",
    "_EN_SECTION_LABELS",
    "_SECTION_ORDER",
    "_PageOutcome",
    "_PagePlan",
    "_ProgressBoard",
    "_TranslationReport",
    "_ZH_SECTION_LABELS",
    "_nav_documents",
    "chunk_pages",
    "job_ceiling",
    "resolve_jobs",
]

#: Navigation sections in their fixed sidebar/home order.
_SECTION_ORDER: Final[tuple[str, ...]] = (
    SECTION_GUIDES,
    SECTION_NOTES,
    SECTION_PLANS,
    SECTION_SETS,
    SECTION_REVIEWS,
)

_ZH_SECTION_LABELS: Final[dict[str, str]] = {
    SECTION_GUIDES: "指南",
    SECTION_NOTES: "架构与笔记",
    SECTION_PLANS: "重构计划",
    SECTION_SETS: "计划集",
    SECTION_REVIEWS: "评审记录",
}

_EN_SECTION_LABELS: Final[dict[str, str]] = {
    SECTION_GUIDES: "Guides",
    SECTION_NOTES: "Architecture notes",
    SECTION_PLANS: "Refactoring plans",
    SECTION_SETS: "Plan sets",
    SECTION_REVIEWS: "Review records",
}


def _nav_documents(pages: list[WikiPage]) -> tuple[str, str, str, str]:
    """Render Home and _Sidebar in both languages.

    Returns ``(home_zh, sidebar_zh, home_en, sidebar_en)``.  Guides
    entries carry an inline EN twin link; plan sets are grouped under
    their directory name in Home and collapsed to a single overview line
    in the sidebar.
    """
    by_section: dict[str, list[WikiPage]] = {section: [] for section in _SECTION_ORDER}
    for page in pages:
        by_section[page.section].append(page)
    for bucket in by_section.values():
        bucket.sort(key=lambda p: p.zh_target)
    groups = sorted(
        {p.group for p in by_section[SECTION_SETS] if p.group is not None},
        key=str.lower,
    )

    def zh_entry(page: WikiPage, with_en: bool) -> str:
        line = f"- [{_page_title(page.zh_source)}]({_link(page.zh_target)})"
        return f"{line} · [EN]({_link(page.en_target)})" if with_en else line

    def en_entry(page: WikiPage) -> str:
        return f"- [{_page_base(page)}]({_link(page.en_target)})"

    home_zh: list[str] = []
    sidebar_zh: list[str] = []
    home_en: list[str] = []
    sidebar_en: list[str] = []
    for section in _SECTION_ORDER:
        bucket = by_section[section]
        if not bucket:
            continue
        home_zh.append(f"## {_ZH_SECTION_LABELS[section]}")
        home_en.append(f"## {_EN_SECTION_LABELS[section]}")
        sidebar_zh.append(f"- **{_ZH_SECTION_LABELS[section]}**")
        sidebar_en.append(f"- **{_EN_SECTION_LABELS[section]}**")
        if section == SECTION_SETS:
            grouped: dict[str, list[WikiPage]] = {group: [] for group in groups}
            for page in bucket:
                group = page.group
                if group in grouped:
                    grouped[group].append(page)
            for group in groups:
                members = grouped[group]
                home_zh.append(f"### {group}")
                home_en.append(f"### {group}")
                home_zh.extend(zh_entry(p, False) for p in members)
                home_en.extend(en_entry(p) for p in members)
                overview = next(
                    (p for p in members if p.zh_target == f"{group}/overview{_ZH_SUFFIX}"),
                    None,
                )
                head = f"  - **{group}**"
                tail = f"（{len(members)} 篇）"
                if overview is not None:
                    sidebar_zh.append(f"{head} — [总纲]({_link(overview.zh_target)}){tail}")
                    sidebar_en.append(
                        f"  - **{group}** — [overview]({_link(overview.en_target)})"
                        f" ({len(members)} pages)"
                    )
                else:
                    sidebar_zh.append(f"{head}{tail}")
                    sidebar_en.append(f"  - **{group}** ({len(members)} pages)")
        else:
            with_en = section == SECTION_GUIDES
            home_zh.extend(zh_entry(p, with_en) for p in bucket)
            home_en.extend(en_entry(p) for p in bucket)
            sidebar_zh.extend(("  " + zh_entry(p, with_en)) for p in bucket)
            sidebar_en.extend(("  " + en_entry(p)) for p in bucket)
        home_zh.append("")
        home_en.append("")

    home_zh_doc = "\n".join(
        [
            "# yate Wiki",
            "",
            "yate（yet another terminal editor）项目的文档 Wiki，由"
            " `python -m tools.pack wiki` 从仓库源文档生成：中文页自源文档重建，"
            "英文页为对应译本。",
            "",
            *home_zh,
            "",
        ]
    )
    home_en_doc = "\n".join(
        [
            "# yate Wiki",
            "",
            "Documentation wiki for yate, yet another terminal editor built on"
            " Textual. Generated by `python -m tools.pack wiki` from the repo"
            " sources: Chinese pages are rebuilt from the sources and English"
            " pages are their translations.",
            "",
            *home_en,
            "",
        ]
    )
    sidebar_zh_doc = "\n".join([*sidebar_zh, ""])
    sidebar_en_doc = "\n".join([*sidebar_en, ""])
    return home_zh_doc, sidebar_zh_doc, home_en_doc, sidebar_en_doc


@dataclass(frozen=True)
class _PagePlan:
    """One page queued for translation, with everything a worker needs.

    The Chinese text is decoded once during preparation so workers never
    touch the filesystem: sources can vanish mid-run and that must fail
    before any translation starts (issue IKJPEK).
    """

    page: WikiPage
    digest: str
    text: str
    has_en: bool


@dataclass(frozen=True)
class _PageOutcome:
    """A worker's report for one planned page.

    *error* holds anything the worker caught (``BaseException`` included,
    see :func:`_run_batch`); the main thread re-raises it so ``Ctrl+C``
    still reaches :func:`tools.pack.cli.main` and maps to exit code 130.
    """

    plan: _PagePlan
    english: str | None
    error: BaseException | None
    elapsed: float


@dataclass(frozen=True)
class _TranslationReport:
    """Aggregated result of the parallel translation stage."""

    translated: int
    digests: dict[str, str]
    missing: list[str]
    stale: list[str]


def job_ceiling(*, cores: int | None = None) -> int:
    """Return the hard concurrency ceiling: CPU cores times two (issue IKJPEK)."""
    return max(1, (cpu_count() if cores is None else cores) * 2)


def resolve_jobs(jobs: int | None, *, cores: int | None = None) -> int:
    """Clamp *jobs* into ``[1, cores * 2]``; ``None`` means the ceiling itself.

    This is the single place the concurrency cap is enforced, so neither a
    generous ``--jobs`` nor a machine with many cores can start more than
    twice the core count of translators.
    """
    limit = _wiki_facade.job_ceiling(cores=cores)
    if jobs is None:
        return limit
    return max(1, min(jobs, limit))


def chunk_pages[T](items: Sequence[T], size: int = BATCH_SIZE) -> list[list[T]]:
    """Split *items* into consecutive chunks of at most *size* entries.

    The task-pool unit: one chunk is one unit of work handed to a pool
    worker, so a worker failure or an interrupt costs at most *size*
    translations.
    """
    if size < 1:
        raise ValueError(f"chunk size must be >= 1, got {size}")
    return [list(items[start : start + size]) for start in range(0, len(items), size)]


@dataclass
class _ProgressBoard:
    """Page-level progress reporting for the translation pool.

    Every batch row and the overall row move as each page lands, and the
    overall row also carries its own description (``pages done · batches
    queued · workers``): the bar and the sentence next to it used to
    disagree for minutes, because the text was only refreshed when a whole
    batch reported back.

    Workers call :meth:`page_started` / :meth:`page_done`; the main thread
    calls :meth:`batch_finished`.  rich updates task fields under
    ``Progress._lock`` and paints frames from its own refresh thread under
    ``Live._lock``, so one frame may show a row one step ahead of another
    -- cosmetic only.  Keeping the updates on the workers is what makes the
    bar live at all; the alternative (the main thread draining the pool)
    would mean either latency or a rewrite of the interrupt path.

    *queued* is the one field the main thread mutates; every other field is
    set once at construction.
    """

    progress: Progress
    overall: TaskID
    batch_tasks: dict[int, TaskID]
    batch_count: int
    total_pages: int
    workers: int
    queued: int

    def _description(self) -> str:
        """Render the overall row text from the live counters."""
        done = int(self.progress.tasks[self.overall].completed)
        return (
            f"translating {done}/{self.total_pages} page(s)"
            f" · {self.queued} batch(es) queued · {self.workers} worker(s)"
        )

    def page_started(self, index: int, page: WikiPage) -> None:
        """Show which page batch *index* is translating right now."""
        self.progress.update(
            self.batch_tasks[index],
            description=f"batch {index}/{self.batch_count} · {escape(page.en_target)}",
        )

    def page_done(self, index: int) -> None:
        """Advance the batch row and the overall row by one finished page.

        The text is rendered *after* the advance, never as an argument of
        the same call: arguments are evaluated first, so passing it inline
        would publish the pre-advance count and leave the row permanently
        one page behind its own bar.
        """
        self.progress.advance(self.batch_tasks[index])
        self.progress.update(self.overall, advance=1)
        self.progress.update(self.overall, description=self._description())

    def batch_finished(self) -> None:
        """Note that one batch reported back: one batch less queued."""
        self.queued -= 1
        self.progress.update(self.overall, description=self._description())
