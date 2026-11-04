"""Wiki source collection: wiki pages from the repo's markdown sources.

Holds :class:`WikiPage` (the published-page record), the ``.trae`` /
bilingual-pair collectors behind :func:`collect_sources`, the navigation
link helpers (:func:`_page_base` / :func:`_page_title` / :func:`_link`)
and the page file primitives shared by the later stages
(:func:`_read_source_bytes`, :func:`_write_page_bytes`,
:func:`_write_page_text`), every failure raised as
:class:`tools.pack.wiki.lint.WikiError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Final

from tools.pack.errors import Code
from tools.pack.wiki.lint import WikiError

# The shared surface of this submodule: the facade re-exports it and the
# sibling submodules consume it, so every name below is intentionally
# public within the subpackage (a leading underscore only keeps it out of
# the generator's documented plugin-facing API).
__all__ = [
    "EXCLUDED_TRAE_DIRS",
    "SECTION_GUIDES",
    "SECTION_NOTES",
    "SECTION_PLANS",
    "SECTION_REVIEWS",
    "SECTION_SETS",
    "WikiPage",
    "_EN_SUFFIX",
    "_MD_SUFFIX",
    "_ZH_SUFFIX",
    "_assert_unique",
    "_collect_bilingual",
    "_collect_trae_dir",
    "_link",
    "_page_base",
    "_page_title",
    "_read_source_bytes",
    "_strip_md",
    "_write_page_bytes",
    "_write_page_text",
    "collect_sources",
]

#: Top-level ``.trae`` members that are never published.
EXCLUDED_TRAE_DIRS: Final[frozenset[str]] = frozenset({"agents", "rules", "skills"})

_ZH_SUFFIX: Final[str] = ".zh.md"
_EN_SUFFIX: Final[str] = ".en.md"
_MD_SUFFIX: Final[str] = ".md"

SECTION_GUIDES: Final[str] = "guides"
SECTION_NOTES: Final[str] = "notes"
SECTION_PLANS: Final[str] = "plans"
SECTION_SETS: Final[str] = "sets"
SECTION_REVIEWS: Final[str] = "reviews"


def _read_source_bytes(path: Path, *, code: Code = Code.WIKI_ZH_SOURCE_MISSING) -> bytes:
    """Read a collected source file, reporting absence as a coded error.

    Sources can disappear between collection and use (issue IKJPEK: a plan
    renamed mid-run); a bare ``FileNotFoundError`` used to escape as a full
    traceback, so the run now aborts with ``error[WIKI-0102]`` instead.

    Any other :class:`OSError` -- permissions, a spinning disk, a network
    share -- reports ``WIKI-0103`` instead: it means "unreadable", and
    calling it "vanished" sent the reader after a rename that never
    happened (review R-04).
    """
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise WikiError(
            f"Chinese source vanished: {path.name}",
            code=code,
            hint="re-run once the source tree is complete",
        ) from exc
    except OSError as exc:
        raise WikiError(
            f"cannot read source {path.name}: {exc}",
            code=Code.WIKI_SOURCE_UNREADABLE,
            hint="check file permissions and disk availability",
        ) from exc


def _write_page_bytes(path: Path, data: bytes) -> None:
    """Write a generated page, reporting failures as ``error[WIKI-0106]``."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        raise WikiError(f"cannot write page {path.name}: {exc}", code=Code.WIKI_PAGE_WRITE) from exc


def _write_page_text(path: Path, text: str, *, code: Code = Code.WIKI_PAGE_WRITE) -> None:
    """Write a generated page as UTF-8 text.

    *code* lets the manifest report its own failure (``WIKI-0105``): the
    store is read back on the next run, so a write that failed silently
    there must be distinguishable from an ordinary page write (review
    R-03 -- ``WIKI_MANIFEST_WRITE`` existed but nothing ever raised it).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise WikiError(f"cannot write page {path.name}: {exc}", code=code) from exc


@dataclass(frozen=True)
class WikiPage:
    """One published page: its zh/en wiki targets and the zh source.

    ``en_source`` is set only for already-bilingual sources (``yate/docs``
    topic pairs and the manual) whose English page is copied verbatim;
    for every other page the English counterpart is maintained in the
    wiki repo itself (cache / translation store).
    """

    zh_target: str
    en_target: str
    zh_source: Path
    en_source: Path | None
    section: str
    group: str | None


def _strip_md(name: str) -> str:
    """Return *name* without its trailing ``.md`` suffix (if any)."""
    return name[: -len(_MD_SUFFIX)] if name.endswith(_MD_SUFFIX) else name


def _collect_trae_dir(collection: Path) -> list[WikiPage]:
    """Collect one ``.trae`` subdirectory into wiki pages.

    Depth-1 files land in the wiki root; deeper files keep their
    subdirectory structure.  ``documents`` splits its depth-1 files
    (plain refactoring plans) from the nested plan sets, which get their
    own section and are grouped by their first directory component.
    """
    if collection.name == "documents":
        plain_section = SECTION_PLANS
    elif collection.name == "reviews":
        plain_section = SECTION_REVIEWS
    else:
        plain_section = SECTION_NOTES
    pages: list[WikiPage] = []
    for src in sorted(collection.rglob("*.md")):
        rel_parts = src.relative_to(collection).parts
        sub = "/".join(rel_parts[:-1])
        if collection.name == "documents" and len(rel_parts) > 1:
            section, group = SECTION_SETS, rel_parts[0]
        else:
            section, group = plain_section, None
        base = _strip_md(src.name)
        pages.append(
            WikiPage(
                zh_target=f"{sub}/{base}{_ZH_SUFFIX}" if sub else f"{base}{_ZH_SUFFIX}",
                en_target=f"{sub}/{base}{_EN_SUFFIX}" if sub else f"{base}{_EN_SUFFIX}",
                zh_source=src,
                en_source=None,
                section=section,
                group=group,
            )
        )
    return pages


def _collect_bilingual(base: Path) -> list[WikiPage]:
    """Collect ``*.zh.md``/``*.en.md`` pairs from *base* (guides section).

    A ``*.zh.md`` file without its English twin is still collected; it
    simply becomes a translation target like any other Chinese page.
    ``changelog.*`` files are excluded by requirement.
    """
    pages: list[WikiPage] = []
    if not base.is_dir():
        return pages
    for zh_src in sorted(base.glob(f"*{_ZH_SUFFIX}")):
        if zh_src.name.startswith("changelog."):
            continue
        stem = zh_src.name[: -len(_ZH_SUFFIX)]
        en_src = base / f"{stem}{_EN_SUFFIX}"
        pages.append(
            WikiPage(
                zh_target=f"{stem}{_ZH_SUFFIX}",
                en_target=f"{stem}{_EN_SUFFIX}",
                zh_source=zh_src,
                en_source=en_src if en_src.exists() else None,
                section=SECTION_GUIDES,
                group=None,
            )
        )
    return pages


def _assert_unique(pages: list[WikiPage]) -> None:
    """Raise :class:`WikiError` when two sources map to the same page."""
    seen: dict[str, str] = {}
    for page in pages:
        for target in (page.zh_target, page.en_target):
            if target in seen:
                raise WikiError(
                    f"wiki target collision on {target!r}: "
                    f"{seen[target]!r} vs {page.zh_source.name!r}",
                    code=Code.WIKI_TARGET_COLLISION,
                    hint="rename one of the colliding source documents",
                )
            seen[target] = page.zh_source.name


def collect_sources(repo_root: Path) -> list[WikiPage]:
    """Collect every publishable markdown source below *repo_root*.

    Walks ``.trae`` (excluding :data:`EXCLUDED_TRAE_DIRS`), the bilingual
    manuals under ``yate/docs`` and ``yate/resources``, and returns the
    page list in a stable (sorted) order with collision checking applied.
    """
    pages: list[WikiPage] = []
    trae = repo_root / ".trae"
    if trae.is_dir():
        members = sorted(
            p for p in trae.iterdir() if p.is_dir() and p.name not in EXCLUDED_TRAE_DIRS
        )
        for member in members:
            pages.extend(_collect_trae_dir(member))
    pages.extend(_collect_bilingual(repo_root / "yate" / "docs"))
    pages.extend(_collect_bilingual(repo_root / "yate" / "resources"))
    _assert_unique(pages)
    return pages


def _page_base(page: WikiPage) -> str:
    """Return the ASCII base name of a page (stem without language suffix)."""
    name = page.zh_target.rsplit("/", 1)[-1]
    return name[: -len(_ZH_SUFFIX)] if name.endswith(_ZH_SUFFIX) else name


def _page_title(source: Path) -> str:
    """Return the first ``# `` heading of *source* (fallback: file stem)."""
    with source.open(encoding="utf-8", errors="replace") as fh:
        for line in islice(fh, 30):
            if line.startswith("# "):
                return line[2:].strip()
    return source.stem


def _link(target: str) -> str:
    """Convert a wiki page target into a gitee/github wiki link (no .md)."""
    return target[: -len(_MD_SUFFIX)]
