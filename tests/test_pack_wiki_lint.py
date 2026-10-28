"""Lint integration in the wiki publisher (mdlint wave-2, plan B).

Wiki output is linted right before it hits the disk: Chinese pages run
the ``zh`` profile, English pages (bilingual twins and translations) the
``en`` profile.  Fixable violations are repaired in the written copy,
unfixable ones only log warnings, and the translation manifest digest
keeps hashing the raw source bytes.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest
from tools.mdlint import batch as mdlint_batch
from tools.mdlint.batch import ProgressFn, TextOutcome
from tools.pack import wiki
from tools.pack.errors import Code


def _touch(root: Path, rel: str, text: str = "# title\n\nbody\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal fake checkout: one .trae document plus a bilingual pair."""
    root = tmp_path / "repo"
    _touch(root, ".trae/documents/alpha-plan.md")
    _touch(root, "yate/docs/topic.zh.md", "# topic zh\n")
    _touch(root, "yate/docs/topic.en.md", "# topic en\n")
    return root


def _widen(repo: Path) -> None:
    """Add enough pages that the run takes the parallel lint path."""
    for index in range(wiki.PARALLEL_LINT_MIN_TEXTS):
        _touch(repo, f".trae/documents/bulk-{index:02d}.md")


def test_zh_page_written_with_lint_fix(repo: Path, tmp_path: Path) -> None:
    """A fixable zh violation (MD012 blank run) is repaired on write."""
    _touch(repo, ".trae/documents/messy-plan.md", "# heading\n\n\n\nbody\n")
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    written = (target / "messy-plan.zh.md").read_text(encoding="utf-8")
    assert written == "# heading\n\nbody\n"


def test_en_twin_page_written_with_lint_fix(repo: Path, tmp_path: Path) -> None:
    """A fixable en twin violation (MD047 missing final newline) is repaired."""
    _touch(repo, "yate/docs/broken.zh.md", "# broken zh\n")
    _touch(repo, "yate/docs/broken.en.md", "# broken en")
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    written = (target / "broken.en.md").read_text(encoding="utf-8")
    assert written == "# broken en\n"


def test_translated_en_page_linted(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Translation output passes through the en fix pass before landing."""
    # The fake translation lacks its final newline (MD047).
    def fake_translate(text: str, translate_cmd: str) -> str | None:
        return "# alpha en\n\ntranslated"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    written = (target / "alpha-plan.en.md").read_text(encoding="utf-8")
    assert written == "# alpha en\n\ntranslated\n"


def test_nav_pages_linted(repo: Path, tmp_path: Path) -> None:
    """Nav documents are linted too; fixable residue is repaired."""
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    home = (target / "Home.md").read_text(encoding="utf-8")
    sidebar = (target / "_Sidebar.md").read_text(encoding="utf-8")
    # MD012 blank runs are auto-fixed; unfixable residue (MD022 etc. in
    # the generated nav markup) only logs warnings and keeps links intact.
    assert "\n\n\n" not in home
    assert "\n\n\n" not in sidebar
    assert "alpha-plan" in home and "alpha-plan" in sidebar
    for nav in ("Home.en.md", "_Sidebar.en.md"):
        assert (target / nav).is_file()


def test_lint_does_not_affect_manifest_digest(repo: Path, tmp_path: Path) -> None:
    """The manifest still hashes the raw source bytes, not the linted copy."""
    source = _touch(repo, ".trae/documents/messy-plan.md", "# heading\n\n\n\nbody\n")
    raw = source.read_bytes()
    target = tmp_path / "wiki"
    # An adopted en page keeps the page out of the translation pipeline.
    _touch(target, "messy-plan.en.md", "# messy en\n")
    assert wiki.run(target, None, repo_root=repo) == 0
    first = wiki.load_manifest(target)
    assert wiki.run(target, None, repo_root=repo) == 0
    second = wiki.load_manifest(target)
    expected = hashlib.sha256(raw).hexdigest()
    assert first["messy-plan.zh.md"] == second["messy-plan.zh.md"] == expected
    # The zh page on disk IS the linted copy (differs from the raw source).
    assert (target / "messy-plan.zh.md").read_text(encoding="utf-8") == (
        "# heading\n\nbody\n"
    )


def test_lint_engine_import_error_reported(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing/broken lint engine aborts with WIKI-0109, not a traceback."""
    monkeypatch.setitem(sys.modules, "tools.mdlint.lint", None)
    wiki.reset_lint_engine_cache()
    target = tmp_path / "wiki"
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.run(target, None, repo_root=repo)
    assert excinfo.value.code == Code.WIKI_LINT_FAILED
    assert "markdown lint engine unavailable" in str(excinfo.value)


def test_lint_violations_logged_not_aborting(
    repo: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Unfixable violations warn (with rule id) and never abort the run."""
    _touch(repo, ".trae/documents/cjk-plan.md", "# heading\n\n你好world\n")
    target = tmp_path / "wiki"
    with caplog.at_level(logging.WARNING, logger="yate.pack"):
        assert wiki.run(target, None, repo_root=repo) == 0
    assert any("YM001" in record.getMessage() for record in caplog.records)
    # The unfixable page is published unchanged (YM001 has no fix pass).
    written = (target / "cjk-plan.zh.md").read_text(encoding="utf-8")
    assert written == "# heading\n\n你好world\n"


def test_lint_skips_non_utf8_bytes(
    repo: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Undecodable source bytes pass through untouched with a warning."""
    raw = b"# \xff\xfe invalid utf-8\n"
    source = repo / ".trae" / "documents" / "binary-plan.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(raw)
    target = tmp_path / "wiki"
    with caplog.at_level(logging.WARNING, logger="yate.pack"):
        assert wiki.run(target, None, repo_root=repo) == 0
    assert (target / "binary-plan.zh.md").read_bytes() == raw
    assert any("not UTF-8" in record.getMessage() for record in caplog.records)


def test_lint_backend_crash_publishes_page_as_is(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A document pymarkdown chokes on is published unchanged, not fatal.

    pymarkdown raises its own exceptions on a few pathological inputs; a
    single odd page must never fail the whole publish.
    """
    from tools.mdlint.lint import LintEngine

    def explode(self: LintEngine, text: str) -> tuple[str, list[object]]:
        raise RuntimeError("rehydrate index mismatch")

    monkeypatch.setattr(LintEngine, "fix", explode)
    wiki.reset_lint_engine_cache()
    target = tmp_path / "wiki"
    with caplog.at_level(logging.WARNING, logger="yate.pack"):
        assert wiki.run(target, None, repo_root=repo) == 0
    assert (target / "alpha-plan.zh.md").read_text(encoding="utf-8") == (
        "# title\n\nbody\n"
    )
    assert any("could not be linted" in record.getMessage() for record in caplog.records)


def test_existing_wiki_tests_unaffected(repo: Path, tmp_path: Path) -> None:
    """Clean Markdown passes through byte-identical (lint zero-intervention).

    The plan's "original tests stay green" case: the existing suites run in
    the same acceptance command; this spot-check pins the zero-intervention
    contract on the clean fixture texts they rely on.
    """
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    assert (target / "alpha-plan.zh.md").read_text(encoding="utf-8") == (
        "# title\n\nbody\n"
    )
    assert (target / "topic.zh.md").read_text(encoding="utf-8") == "# topic zh\n"
    assert (target / "topic.en.md").read_text(encoding="utf-8") == "# topic en\n"


def test_bulk_lint_runs_through_the_process_pool(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run past the threshold really hands its pages to the mdlint pool.

    Small fixtures lint in this process (see
    :data:`tools.pack.wiki.PARALLEL_LINT_MIN_TEXTS`), so the pool path needs
    a widened checkout; the fake pool delegates to the real one, which keeps
    the write contract under test instead of only the wiring.
    """
    _widen(repo)
    _touch(repo, ".trae/documents/messy-bulk.md", "# heading\n\n\n\nbody\n")
    real = mdlint_batch.fix_texts
    seen: list[tuple[str, str]] = []

    def recording(
        items: Sequence[tuple[str, str]],
        *,
        pool: ProcessPoolExecutor | None,
        progress: ProgressFn | None,
    ) -> list[TextOutcome]:
        seen.extend(items)
        return real(items, pool=pool, progress=progress)

    monkeypatch.setattr(mdlint_batch, "fix_texts", recording)
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    assert len(seen) >= wiki.PARALLEL_LINT_MIN_TEXTS
    # The pool's fixes are what lands on disk, exactly as in the serial path.
    assert (target / "messy-bulk.zh.md").read_text(encoding="utf-8") == (
        "# heading\n\nbody\n"
    )


def test_one_lint_pool_serves_the_whole_run(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The page pass and the publish pass share one lazily created pool.

    The lint tool's API accepts an injected pool: the publisher creates one
    for the whole run and hands it to every pass, so the workers pay the
    pymarkdown import once instead of per pass (user directive).  Both pooled
    passes must receive the very same pool object.
    """
    _widen(repo)
    real = mdlint_batch.fix_texts
    pools: list[ProcessPoolExecutor | None] = []

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        return "# alpha en\n\ntranslated"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)

    def recording(
        items: Sequence[tuple[str, str]],
        *,
        pool: ProcessPoolExecutor | None,
        progress: ProgressFn | None,
    ) -> list[TextOutcome]:
        pools.append(pool)
        return real(items, pool=pool, progress=progress)

    monkeypatch.setattr(mdlint_batch, "fix_texts", recording)
    # The publish pass lints a single (small) page; the lowered char floor
    # routes it through the pool too, so the reuse assertion has two passes.
    monkeypatch.setattr(wiki, "PARALLEL_LINT_MIN_CHARS", 1)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert len(pools) >= 2
    assert pools[0] is not None
    assert pools[0] is pools[1]


def test_pool_lint_failure_publishes_page_as_is(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A page the pooled worker chokes on publishes unchanged, not fatal.

    The worker returns failures as values (``TextOutcome.error``); the
    publisher must log one warning and keep the page, mirroring the
    in-process crash path covered by
    ``test_lint_backend_crash_publishes_page_as_is``.
    """
    _widen(repo)
    _touch(repo, ".trae/documents/broken-page.md", "# keep me\n")

    def failing(
        items: Sequence[tuple[str, str]], **kwargs: object
    ) -> list[TextOutcome]:
        return [
            TextOutcome(text, [], error="rehydrate index mismatch")
            if "keep me" in text
            else TextOutcome(text, [])
            for _lang, text in items
        ]

    monkeypatch.setattr(mdlint_batch, "fix_texts", failing)
    target = tmp_path / "wiki"
    with caplog.at_level(logging.WARNING, logger="yate.pack"):
        assert wiki.run(target, None, repo_root=repo) == 0
    assert (target / "broken-page.zh.md").read_text(encoding="utf-8") == "# keep me\n"
    assert any(
        "could not be linted" in record.getMessage() for record in caplog.records
    )


def test_text_size_floor_lints_in_the_pool_below_the_count_floor(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A few *large* pages fan out even though their count is tiny.

    The count floor (``PARALLEL_LINT_MIN_TEXTS``) alone would keep a small
    repository of big documents on the serial path, where the fix pass --
    superlinear in document size -- costs minutes; the text floor
    (``PARALLEL_LINT_MIN_CHARS``) is what overrides it.  The floor is lowered
    here so the fixture stays tiny and the assertion is about routing only.
    """
    seen: list[tuple[str, str]] = []

    def recording(
        items: Sequence[tuple[str, str]], **kwargs: object
    ) -> list[TextOutcome]:
        seen.extend(items)
        return [TextOutcome(text, []) for _lang, text in items]

    monkeypatch.setattr(wiki, "PARALLEL_LINT_MIN_CHARS", 1)
    monkeypatch.setattr(mdlint_batch, "fix_texts", recording)
    target = tmp_path / "wiki"

    assert wiki.run(target, None, repo_root=repo) == 0
    assert seen
    assert len(seen) < wiki.PARALLEL_LINT_MIN_TEXTS
