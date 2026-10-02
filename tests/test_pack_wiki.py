"""Tests for the bilingual wiki generator (:mod:`tools.pack.wiki`)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.pack import wiki


def _touch(root: Path, rel: str, text: str = "# title\n\nbody\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A fake yate checkout with one document of every collection kind."""
    root = tmp_path / "repo"
    _touch(root, ".trae/documents/alpha-plan.md")
    _touch(root, ".trae/documents/set-plans/overview.md")
    _touch(root, ".trae/documents/set-plans/beta-plan.md")
    _touch(root, ".trae/documents/set-plans/nested/deep-plan.md")
    _touch(root, ".trae/documents/notes.txt")
    _touch(root, ".trae/reviews/2026-09-01-review.md")
    _touch(root, ".trae/reviews/README.md")
    _touch(root, ".trae/wikis/architecture.md")
    _touch(root, ".trae/agents/secret.md")
    _touch(root, ".trae/rules/secret.md")
    _touch(root, ".trae/skills/secret.md")
    _touch(root, "yate/docs/topic.zh.md", "# topic zh\n")
    _touch(root, "yate/docs/topic.en.md", "# topic en\n")
    _touch(root, "yate/docs/orphan.zh.md", "# orphan zh\n")
    _touch(root, "yate/resources/manual.zh.md", "# manual zh\n")
    _touch(root, "yate/resources/manual.en.md", "# manual en\n")
    _touch(root, "yate/resources/changelog.zh.md", "# changelog\n")
    return root


def test_collect_covers_sources_and_excludes_rest(repo: Path) -> None:
    pages = {page.zh_target: page for page in wiki.collect_sources(repo)}
    assert "alpha-plan.zh.md" in pages
    assert "set-plans/overview.zh.md" in pages
    assert "set-plans/nested/deep-plan.zh.md" in pages
    assert "2026-09-01-review.zh.md" in pages
    assert "README.zh.md" in pages
    assert "architecture.zh.md" in pages
    assert "topic.zh.md" in pages and "orphan.zh.md" in pages
    assert "manual.zh.md" in pages
    assert all("changelog" not in target for target in pages)
    assert all("secret" not in target for target in pages)
    assert pages["topic.zh.md"].en_source is not None
    assert pages["orphan.zh.md"].en_source is None
    assert pages["manual.zh.md"].en_source is not None
    assert pages["topic.zh.md"].section == wiki.SECTION_GUIDES
    assert pages["alpha-plan.zh.md"].section == wiki.SECTION_PLANS
    assert pages["set-plans/overview.zh.md"].section == wiki.SECTION_SETS
    assert pages["set-plans/overview.zh.md"].group == "set-plans"
    assert pages["2026-09-01-review.zh.md"].section == wiki.SECTION_REVIEWS
    assert pages["architecture.zh.md"].section == wiki.SECTION_NOTES


def test_collect_rejects_duplicate_targets(repo: Path) -> None:
    _touch(repo, ".trae/documents/architecture.md")
    with pytest.raises(ValueError, match="architecture.zh.md"):
        wiki.collect_sources(repo)


def test_run_writes_zh_pages_paired_en_and_nav(repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "wiki"
    code = wiki.run(target, None, repo_root=repo)
    assert code == 0
    assert (target / "alpha-plan.zh.md").read_text(encoding="utf-8").startswith("# title")
    assert (target / "set-plans/nested/deep-plan.zh.md").exists()
    assert (target / "topic.en.md").read_text(encoding="utf-8") == "# topic en\n"
    assert (target / "manual.en.md").exists()
    assert not (target / "orphan.en.md").exists()
    for nav in ("Home.md", "Home.en.md", "_Sidebar.md", "_Sidebar.en.md"):
        assert (target / nav).exists()
    assert wiki.load_manifest(target) == {}


def test_run_reports_missing_without_translator(repo: Path, tmp_path: Path) -> None:
    code = wiki.run(tmp_path / "wiki", None, repo_root=repo)
    assert code == 0


def test_en_source_deleted_after_collect_takes_missing_path(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An en source vanishing after collect must not crash the run.

    Regression guard for the collect-time ``exists()`` TOCTOU: the page
    keeps a non-``None`` ``en_source`` whose file is already gone by the
    time ``run()`` reads it -- it must degrade to the missing/translation
    path instead of raising ``FileNotFoundError``.
    """
    original_collect = wiki.collect_sources

    def collect_then_delete_en(repo_root: Path) -> list[wiki.WikiPage]:
        pages = original_collect(repo_root)
        (repo / "yate" / "docs" / "topic.en.md").unlink()
        return pages

    monkeypatch.setattr(wiki, "collect_sources", collect_then_delete_en)

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        return "# topic en\n\ntranslated after vanishing\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert (target / "topic.en.md").read_text(
        encoding="utf-8"
    ) == "# topic en\n\ntranslated after vanishing\n"
    assert "topic.zh.md" in wiki.load_manifest(target)


def test_check_fails_while_missing(repo: Path, tmp_path: Path) -> None:
    code = wiki.run(tmp_path / "wiki", None, check=True, repo_root=repo)
    assert code == 1


def test_translate_cmd_fills_missing_pages(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_translate(text: str, translate_cmd: str) -> str | None:
        calls.append(translate_cmd)
        return "# orphan en\n\ntranslated\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", fake_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert calls == ["fake-cmd"] * 8
    assert (target / "orphan.en.md").read_text(encoding="utf-8") == "# orphan en\n\ntranslated\n"
    assert "orphan.zh.md" in wiki.load_manifest(target)
    # Fresh pages are kept by default, so no further calls happen.
    assert wiki.run(target, "fake-cmd", check=True, repo_root=repo) == 0
    assert calls == ["fake-cmd"] * 8


def test_existing_en_is_adopted_not_overwritten(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "wiki"
    target.mkdir()
    _touch(target, "orphan.en.md", "# kept\n")
    seen: list[str] = []

    def fail_translate(text: str, translate_cmd: str) -> str | None:
        seen.append(text)
        return "# en\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", fail_translate)
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert (target / "orphan.en.md").read_text(encoding="utf-8") == "# kept\n"
    assert all("# orphan zh" not in text for text in seen)
    assert "orphan.zh.md" in wiki.load_manifest(target)


def test_stale_is_reported_then_retranslated(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def v1_translate(text: str, translate_cmd: str) -> str | None:
        return "# orphan en v1\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", v1_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    _touch(repo, ".trae/documents/set-plans/beta-plan.md", "# beta v2\n")

    # A failing hook keeps the outdated page stale (reported, not blessed).
    def failing_translate(text: str, translate_cmd: str) -> str | None:
        return None

    monkeypatch.setattr(wiki, "translate_via_cmd", failing_translate)
    assert wiki.run(target, "fake-cmd", check=True, repo_root=repo) == 1

    # A working hook re-translates exactly the stale page, nothing else.
    calls: list[str] = []

    def v2_translate(text: str, translate_cmd: str) -> str | None:
        calls.append(translate_cmd)
        return "# beta en v2\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", v2_translate)
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    assert calls == ["fake-cmd"]
    assert (
        (target / "set-plans/beta-plan.en.md").read_text(encoding="utf-8")
        == "# beta en v2\n"
    )


def test_failed_fresh_retranslation_does_not_bless_manifest(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed default-mode re-translation must not record the new digest.

    The externally maintained page (no manifest entry) keeps its ``None``
    marker on failure instead of being silently blessed as fresh.
    """
    target = tmp_path / "wiki"
    target.mkdir()
    _touch(target, "orphan.en.md", "# kept from an older source\n")

    def failing_translate(text: str, translate_cmd: str) -> str | None:
        return None

    monkeypatch.setattr(wiki, "translate_via_cmd", failing_translate)
    assert wiki.run(target, "fake-cmd", check=True, translate_all=True, repo_root=repo) == 1
    assert wiki.load_manifest(target) == {}
    assert (target / "orphan.en.md").read_text(encoding="utf-8") == (
        "# kept from an older source\n"
    )


def test_translate_all_mode_retranslates_every_page(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    counter = {"n": 0}

    def counting_translate(text: str, translate_cmd: str) -> str | None:
        counter["n"] += 1
        return "# en v1\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", counting_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    first = counter["n"]
    assert first == 8
    # --translate-all sends every non-bilingual page again, overwriting
    # even fresh English pages.
    assert wiki.run(target, "fake-cmd", translate_all=True, repo_root=repo) == 0
    assert counter["n"] == first * 2


def test_translate_all_with_force_is_accepted(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def any_translate(text: str, translate_cmd: str) -> str | None:
        return "# en\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", any_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, None, repo_root=repo) == 0
    _touch(repo, ".trae/documents/set-plans/beta-plan.md", "# beta v2\n")
    assert wiki.run(target, "fake-cmd", force=True, translate_all=True, repo_root=repo) == 0
    assert (target / "set-plans/beta-plan.en.md").read_text(
        encoding="utf-8"
    ) == "# en\n"


def test_force_without_translator_reports_stale(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def v1_translate(text: str, translate_cmd: str) -> str | None:
        return "# orphan en v1\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", v1_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    _touch(repo, ".trae/documents/set-plans/beta-plan.md", "# beta v2\n")

    # Without a translator hook the outdated page must still count as
    # stale so --check gates on it (blocking review finding #1).
    assert wiki.run(target, None, check=True, repo_root=repo) == 1
    assert (
        target / "set-plans/beta-plan.en.md"
    ).read_text(encoding="utf-8") == "# orphan en v1\n"


def test_load_manifest_tolerates_corruption(repo: Path, tmp_path: Path) -> None:
    assert wiki.load_manifest(tmp_path) == {}

    corrupt = tmp_path / wiki.MANIFEST_NAME
    corrupt.write_text("{not json", encoding="utf-8")
    assert wiki.load_manifest(tmp_path) == {}

    corrupt.write_text('["not", "an", "object"]', encoding="utf-8")
    assert wiki.load_manifest(tmp_path) == {}

    corrupt.write_text('{"a.zh.md": "deadbeef"}', encoding="utf-8")
    assert wiki.load_manifest(tmp_path) == {"a.zh.md": "deadbeef"}


def test_translate_helper_survives_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timed_out_run(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=[str(cmd)], timeout=900)

    monkeypatch.setattr(wiki.subprocess, "run", timed_out_run)
    assert wiki.translate_via_cmd("# zh in\n", "slow-cmd") is None


def test_nav_links_resolve_to_pages(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re

    def any_translate(text: str, cmd: str) -> str | None:
        return "# translated\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", any_translate)
    target = tmp_path / "wiki"
    wiki.run(target, "fake-cmd", repo_root=repo)
    pattern = re.compile(r"\]\(([^)]+)\)")
    for nav in ("Home.md", "_Sidebar.md", "Home.en.md", "_Sidebar.en.md"):
        for link in pattern.findall((target / nav).read_text(encoding="utf-8")):
            assert (target / f"{link}.md").exists(), link


def test_push_sequence_commits_and_pushes_both_remotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:2] == ("remote", "get-url"):
            return subprocess.CompletedProcess(args, 1, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.push_wiki(tmp_path) == 0
    assert ("add", "-A") in calls
    assert ("commit", "-m", wiki.COMMIT_MESSAGE) in calls
    assert ("remote", "add", "github", wiki.GITHUB_WIKI_URL) in calls
    assert ("push", "origin", wiki.WIKI_BRANCH) in calls
    assert ("push", "github", wiki.WIKI_BRANCH) in calls


def test_push_aborts_when_git_add_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ("add", "-A"):
            return subprocess.CompletedProcess(args, 128, "", "disk full")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.push_wiki(tmp_path) == 1
    assert calls == [("add", "-A")]


def test_push_aborts_when_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ("commit",):
            return subprocess.CompletedProcess(args, 128, "", "fatal: no identity")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.push_wiki(tmp_path) == 1
    assert ("push", "origin", wiki.WIKI_BRANCH) not in calls
    assert ("push", "github", wiki.WIKI_BRANCH) not in calls


def test_push_continues_on_empty_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("commit",):
            return subprocess.CompletedProcess(args, 1, "", "nothing to commit, working tree clean\n")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.push_wiki(tmp_path) == 0


def test_load_manifest_aborts_on_read_error(tmp_path: Path) -> None:
    manifest = tmp_path / wiki.MANIFEST_NAME
    manifest.mkdir()  # a directory: exists() is True, read_text() raises OSError
    with pytest.raises(SystemExit):
        wiki.load_manifest(tmp_path)


def test_force_retranslate_failure_reports_stale(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def v1_translate(text: str, translate_cmd: str) -> str | None:
        return "# en v1\n"

    monkeypatch.setattr(wiki, "translate_via_cmd", v1_translate)
    target = tmp_path / "wiki"
    assert wiki.run(target, "fake-cmd", repo_root=repo) == 0
    _touch(repo, ".trae/documents/set-plans/beta-plan.md", "# beta v2\n")

    def failing_translate(text: str, translate_cmd: str) -> str | None:
        return None

    monkeypatch.setattr(wiki, "translate_via_cmd", failing_translate)
    assert wiki.run(target, "fake-cmd", force=True, check=True, repo_root=repo) == 1
    out = capsys.readouterr().out
    assert "stale en: set-plans/beta-plan.en.md" in out
    assert "missing 0" in out
    assert (target / "set-plans/beta-plan.en.md").read_text(
        encoding="utf-8"
    ) == "# en v1\n"


def test_push_reports_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("push", "github"):
            return subprocess.CompletedProcess(args, 128, "", "boom")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.push_wiki(tmp_path) == 1


def test_default_target_uses_origin_url(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "https://gitee.com/jermaine/yate.git\n", "")

    monkeypatch.setattr(wiki, "run_git", fake_git)
    assert wiki.default_target(repo) == repo.parent / "yate.wiki"

    def no_remote(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "not a repo")

    monkeypatch.setattr(wiki, "run_git", no_remote)
    assert wiki.default_target(repo) == repo.parent / f"{repo.name}.wiki"


def test_translate_helper_runs_shell_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(
        cmd: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = cmd
        recorded.update(kwargs)
        return subprocess.CompletedProcess([str(cmd)], 0, "# en out\n", "")

    monkeypatch.setattr(wiki.subprocess, "run", fake_run)
    assert wiki.translate_via_cmd("# zh in\n", "cat") == "# en out\n"
    assert recorded["cmd"] == "cat"
    assert recorded["shell"] is True
    assert recorded["input"] == "# zh in\n"

    def failing_run(
        cmd: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([str(cmd)], 3, "", "kaput")

    monkeypatch.setattr(wiki.subprocess, "run", failing_run)
    assert wiki.translate_via_cmd("# zh in\n", "cat") is None

    def empty_run(
        cmd: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([str(cmd)], 0, "   \n", "")

    monkeypatch.setattr(wiki.subprocess, "run", empty_run)
    assert wiki.translate_via_cmd("# zh in\n", "cat") is None


def test_cli_wiki_subcommand_wiring(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.pack import cli

    seen: dict[str, object] = {}

    def fake_run(
        target: Path,
        translate_cmd: str | None,
        *,
        force: bool = False,
        translate_all: bool = False,
        check: bool = False,
        push: bool = False,
        repo_root: Path | None = None,
    ) -> int:
        seen["target"] = target
        seen["translate_cmd"] = translate_cmd
        seen["flags"] = (force, translate_all, check, push)
        seen["repo_root"] = repo_root
        return 0

    monkeypatch.setattr(wiki, "run", fake_run)
    argv = [
        "wiki",
        "--target",
        str(tmp_path / "w"),
        "--translate-cmd",
        "tr",
        "--force",
        "--translate-all",
        "--check",
        "--push",
    ]
    assert cli.main(argv) == 0
    assert seen["target"] == tmp_path / "w"
    assert seen["translate_cmd"] == "tr"
    assert seen["flags"] == (True, True, True, True)
    assert seen["repo_root"] == Path(cli.__file__).resolve().parents[2]
