"""Tests for the tools/changelog generator.

Strategy (frozen in the plan): the IO boundary is only ``gitdata``; classify,
segments, render, gitee and translations run on synthetic data.  One optional
end-to-end test exercises a real throwaway git repository and skips when git
is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.changelog import cli, gitee, gitdata, render, segments, translations
from tools.changelog.classify import classify_commit, is_changelog_entry
from tools.changelog.model import (
    Category,
    Commit,
    RawCommit,
    TagRef,
    VersionBump,
)

REMOTE = gitee.RemoteInfo(host="gitee.com", owner="demo", repo="yate")


def _raw(sha: str, subject: str, *, body: str = "", date: str = "2026-01-01") -> RawCommit:
    return RawCommit(
        sha=sha, short_sha=sha[:7], author_date=date, subject=subject, body=body
    )


def _entries(*raws: RawCommit) -> list[Commit]:
    return [c for c in map(classify_commit, raws) if is_changelog_entry(c)]


# --- classify ---------------------------------------------------------------


def test_feat_is_feature_and_prefix_stripped() -> None:
    commit = classify_commit(_raw("a" * 40, "feat: add fuzzy search"))
    assert commit.category is Category.FEATURE
    assert commit.summary_en == "add fuzzy search"
    assert commit.scope is None
    assert not commit.is_breaking


def test_fix_with_scope() -> None:
    commit = classify_commit(_raw("b" * 40, "fix(editor): keep cursor visible"))
    assert commit.category is Category.FIX
    assert commit.scope == "editor"
    assert commit.summary_en == "keep cursor visible"


def test_bang_marks_breaking() -> None:
    commit = classify_commit(_raw("c" * 40, "refactor(core)!: drop old api"))
    assert commit.is_breaking
    assert commit.category is Category.REFACTOR


def test_breaking_change_footer() -> None:
    commit = classify_commit(
        _raw("d" * 40, "feat: new api", body="something\nBREAKING CHANGE: gone")
    )
    assert commit.is_breaking


@pytest.mark.parametrize("subject", ["build: tweak", "ci: run nightly", "chore: tidy"])
def test_build_ci_chore_are_tooling(subject: str) -> None:
    commit = classify_commit(_raw("e" * 40, subject))
    assert commit.category is Category.TOOLING


def test_unknown_type_and_no_prefix_are_other() -> None:
    # unknown type still parses as conventional → prefix stripped
    deploy = classify_commit(_raw("f" * 40, "deploy: ship it"))
    assert deploy.category is Category.OTHER
    assert deploy.summary_en == "ship it"
    # no prefix at all → full subject kept
    plain = classify_commit(_raw("9" * 40, "Add a plain subject"))
    assert plain.category is Category.OTHER
    assert plain.summary_en == "Add a plain subject"


def test_release_bump_commit_is_not_an_entry() -> None:
    commit = classify_commit(_raw("1" * 40, "chore(release): v0.2.0"))
    assert not is_changelog_entry(commit)
    assert is_changelog_entry(classify_commit(_raw("2" * 40, "feat: x")))


# --- segments ---------------------------------------------------------------


@pytest.fixture
def topo_commits() -> list[RawCommit]:
    # topo order newest → oldest; dates are deliberately NOT monotonic
    return [
        _raw("a" * 40, "feat: newest", date="2026-01-01"),
        _raw("b" * 40, "fix: middle", date="2026-06-01"),
        _raw("c" * 40, "feat: oldest", date="2026-03-01"),
    ]


@pytest.fixture
def topo_entries(topo_commits: list[RawCommit]) -> list[Commit]:
    return _entries(*topo_commits)


def test_tag_boundary(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    boundaries = segments.build_boundaries(
        [TagRef(name="v0.2.0", sha="b" * 40)], [], topo_commits, current_version="0.2.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.2.0"
    )
    assert [s.version for s in result] == [None, "0.2.0"]
    unreleased = result[0]
    versioned = result[1]
    assert [c.sha[:1] for c in unreleased.commits] == ["a"]
    # the boundary commit b belongs to the NEW version; older c folds in
    assert [c.sha[:1] for c in versioned.commits] == ["b", "c"]
    assert versioned.date == "2026-06-01"  # boundary commit date
    assert versioned.range_from == "ROOT"
    assert versioned.range_to == "v0.2.0"
    assert versioned.initial


def test_bump_fallback_without_tags(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    bumps = [
        VersionBump(sha="c" * 40, version="0.1.0"),
        VersionBump(sha="b" * 40, version="0.2.0"),
    ]
    boundaries = segments.build_boundaries(
        [], bumps, topo_commits, current_version="0.2.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.2.0"
    )
    assert [s.version for s in result] == [None, "0.2.0", "0.1.0"]
    assert result[1].range_from == "v0.1.0"
    assert result[1].range_to == "v0.2.0"
    assert not result[1].initial


def test_repeated_bump_merges_into_one_segment(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    bumps = [
        VersionBump(sha="c" * 40, version="0.1.0"),
        VersionBump(sha="b" * 40, version="0.2.0"),
        VersionBump(sha="a" * 40, version="0.2.0"),  # re-bump of same version
    ]
    boundaries = segments.build_boundaries(
        [], bumps, topo_commits, current_version="0.2.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.2.0"
    )
    versions = [s.version for s in result]
    assert versions == [None, "0.2.0", "0.1.0"]
    assert versions.count("0.2.0") == 1  # re-bump did not split


def test_cold_start_single_segment(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    boundaries = segments.build_boundaries(
        [], [], topo_commits, current_version="0.1.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.1.0"
    )
    assert len(result) == 1
    segment = result[0]
    assert segment.version == "0.1.0"
    assert segment.date == "2026-01-01"  # newest commit's date
    assert segment.initial
    assert len(segment.commits) == 3
    assert segment.range_from == "ROOT"


def test_unreleased_only_when_commits_above_boundary(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    boundaries = segments.build_boundaries(
        [TagRef(name="v0.1.0", sha="a" * 40)], [], topo_commits, current_version="0.1.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.1.0"
    )
    assert [s.version for s in result] == ["0.1.0"]
    assert len(result[0].commits) == 3


def test_boundaries_ignore_dates_and_follow_topo(
    topo_commits: list[RawCommit], topo_entries: list[Commit]
) -> None:
    # a is newest by topo although its date is the oldest of all three
    boundaries = segments.build_boundaries(
        [TagRef(name="v0.1.0", sha="c" * 40)], [], topo_commits, current_version="0.1.0"
    )
    result = segments.build_segments(
        topo_commits, topo_entries, boundaries, current_version="0.1.0"
    )
    assert [s.version for s in result] == [None, "0.1.0"]
    assert [c.sha[:1] for c in result[0].commits] == ["a", "b"]


# --- render -----------------------------------------------------------------


@pytest.fixture
def breaking_segments() -> list[segments.ReleaseSegment]:
    full = [
        _raw("a" * 40, "feat!: new config format", body="BREAKING CHANGE: old keys gone"),
        _raw("b" * 40, "feat(editor): tab bar", date="2026-02-02"),
        _raw("c" * 40, "fix: crash"),
        _raw("d" * 40, "chore(release): v0.2.0"),
    ]
    boundaries = segments.build_boundaries(
        [], [VersionBump(sha="d" * 40, version="0.2.0")], full, current_version="0.2.0"
    )
    return segments.build_segments(
        full, _entries(*full), boundaries, current_version="0.2.0"
    )


def test_english_document(breaking_segments: list[segments.ReleaseSegment]) -> None:
    doc = render.render_document(
        breaking_segments, lang="en", remote=REMOTE, overrides={}
    )
    assert "## [0.2.0] - 2026-01-01" in doc
    assert "### ⚠ BREAKING CHANGES" in doc
    assert "### Features" in doc
    assert "### Bug Fixes" in doc
    assert "](https://gitee.com/demo/yate/commit/" + "a" * 40 + ")" in doc
    assert "](https://gitee.com/demo/yate/compare/ROOT...v0.2.0)" in doc
    assert "_Initial release._" in doc
    assert "[缺中文]" not in doc
    # release bump commits are boundaries, never entries
    assert "chore(release)" not in doc


def test_breaking_changes_come_first(
    breaking_segments: list[segments.ReleaseSegment],
) -> None:
    doc = render.render_document(
        breaking_segments, lang="en", remote=REMOTE, overrides={}
    )
    assert doc.index("BREAKING CHANGES") < doc.index("### Features")


def test_chinese_document_with_overrides(
    breaking_segments: list[segments.ReleaseSegment],
) -> None:
    overrides = {
        "b" * 7: translations.OverrideEntry(summary="编辑器标签栏", detail="可点击切换"),
    }
    doc = render.render_document(
        breaking_segments, lang="zh", remote=REMOTE, overrides=overrides
    )
    assert "### 新功能" in doc
    assert "### 问题修复" in doc
    assert "### ⚠ 破坏性变更" in doc
    assert "- 编辑器标签栏" in doc
    assert "  - 可点击切换" in doc
    assert "[缺中文]" in doc  # untranslated entries fall back
    assert "_首个版本。_" in doc


def test_no_remote_renders_plain_hashes(
    breaking_segments: list[segments.ReleaseSegment],
) -> None:
    doc = render.render_document(
        breaking_segments, lang="en", remote=None, overrides={}
    )
    assert f"(`{'a' * 7}`)" in doc
    assert "https://" not in doc


# --- gitee ------------------------------------------------------------------


def test_parse_https_remote() -> None:
    remote = gitee.parse_remote("https://gitee.com/jermaine/yate.git")
    assert remote is not None
    assert (remote.host, remote.owner, remote.repo) == ("gitee.com", "jermaine", "yate")
    assert remote.web_base == "https://gitee.com/jermaine/yate"


def test_parse_ssh_remote() -> None:
    remote = gitee.parse_remote("git@gitee.com:jermaine/yate.git")
    assert remote is not None
    assert remote.owner == "jermaine"
    remote2 = gitee.parse_remote("ssh://git@gitee.com/jermaine/yate.git")
    assert remote2 is not None
    assert remote2.repo == "yate"


def test_parse_unknown_returns_none() -> None:
    assert gitee.parse_remote("https://example.org/only-owner") is None


def test_link_construction() -> None:
    assert (
        gitee.commit_url(REMOTE, "abc123")
        == "https://gitee.com/demo/yate/commit/abc123"
    )
    assert (
        gitee.compare_url(REMOTE, "v0.1.0", "v0.2.0")
        == "https://gitee.com/demo/yate/compare/v0.1.0...v0.2.0"
    )


# --- translations -----------------------------------------------------------


def test_upsert_deduplicates() -> None:
    overrides: dict[str, translations.OverrideEntry] = {}
    assert translations.upsert_override(overrides, "abc1234", "摘要")
    assert not translations.upsert_override(overrides, "abc1234", "摘要")
    assert translations.upsert_override(overrides, "abc1234", "新摘要")


def test_roundtrip_keeps_chinese_raw_and_sorted(tmp_path: Path) -> None:
    path = tmp_path / "zh_overrides.json"
    overrides: dict[str, translations.OverrideEntry] = {}
    translations.upsert_override(overrides, "bbb2222", "后写")
    translations.upsert_override(overrides, "aaa1111", "先写", detail="细节")
    translations.save_overrides(overrides, path)
    text = path.read_text(encoding="utf-8")
    assert "先写" in text  # ensure_ascii=False
    assert text.index("aaa1111") < text.index("bbb2222")
    loaded = translations.load_overrides(path)
    assert loaded["aaa1111"].summary == "先写"
    assert loaded["aaa1111"].detail == "细节"
    data = json.loads(text)
    assert list(data) == sorted(list(data))  # sorted keys


def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    assert translations.load_overrides(tmp_path / "nope.json") == {}


# --- gitdata parsers --------------------------------------------------------


def test_parse_log_output_with_chinese_and_separators() -> None:
    sha1, sha2 = "a" * 40, "b" * 40
    record1 = f"{sha1}\x1f{sha1[:7]}\x1f2026-09-13\x1ffeat: 中文支持\x1f正文第一行\x1f嵌入分隔符\x1e"
    record2 = f"{sha2}\x1f{sha2[:7]}\x1f2026-09-12\x1ffix: something\x1f\x1e"
    commits = gitdata.parse_log_output(record1 + record2)
    assert len(commits) == 2
    assert commits[0].subject == "feat: 中文支持"
    assert commits[0].short_sha == sha1[:7]
    assert "嵌入分隔符" in commits[0].body  # body keeps stray separators
    assert commits[1].body == ""


def test_parse_log_output_rejects_malformed_record() -> None:
    with pytest.raises(gitdata.GitError):
        gitdata.parse_log_output("only-two\x1ffields\x1e")


def test_parse_bump_patch_only_counts_added_lines() -> None:
    sha1, sha2 = "c" * 40, "d" * 40
    text = (
        f"\x1e{sha1}\n"
        "diff --git a/yate/__init__.py b/yate/__init__.py\n"
        "--- a/yate/__init__.py\n"
        "+++ b/yate/__init__.py\n"
        '-__version__ = "0.1.0"\n'
        '+__version__ = "0.2.0"\n'
        "+# comment mentioning __version__ = \"9.9.9\" on an added comment line\n"
        f"\x1e{sha2}\n"
        " context line __version__ = \"3.0.0\"\n"
        '+docstring = "nope"\n'
    )
    bumps = gitdata.parse_bump_patch(text)
    assert bumps == [VersionBump(sha=sha1, version="0.2.0")]


# --- render targets (root vs bundle headers, section 4) ---------------------


@pytest.fixture
def cold_start_segments() -> list[segments.ReleaseSegment]:
    full = [_raw("a" * 40, "feat: thing", date="2026-02-02")]
    boundaries = segments.build_boundaries([], [], full, current_version="0.1.0")
    return segments.build_segments(
        full, _entries(*full), boundaries, current_version="0.1.0"
    )


def test_root_header_has_maintainer_wording_and_sibling_link(
    cold_start_segments: list[segments.ReleaseSegment],
) -> None:
    doc = render.render_document(
        cold_start_segments, lang="en", remote=REMOTE, overrides={}
    )
    assert "do not edit by hand" in doc
    assert "[CHANGELOG.zh.md](CHANGELOG.zh.md)" in doc


def test_bundle_header_is_end_user_facing(
    cold_start_segments: list[segments.ReleaseSegment],
) -> None:
    doc = render.render_document(
        cold_start_segments, lang="en", remote=REMOTE, overrides={},
        target="bundle", generated="Generated from the git history · yate 0.1.0",
    )
    assert doc.startswith("# Changelog\n\n> Generated from")
    assert "do not edit" not in doc
    assert "CHANGELOG.zh.md" not in doc
    zh = render.render_document(
        cold_start_segments, lang="zh", remote=REMOTE, overrides={},
        target="bundle", generated="由 git 历史自动生成 · yate 0.1.0",
    )
    assert zh.startswith("# 变更日志")
    assert "请勿手工编辑" not in zh


# --- released-section gate (4.1 semantics as pure functions) ----------------


def _doc(body: str, *, unreleased: str = "") -> str:
    parts = ["# Changelog", ""]
    if unreleased:
        parts += ["## [Unreleased]", "", unreleased, ""]
    parts += ["## [0.1.0] - 2026-01-01", "", body]
    return "\n".join(parts) + "\n"


def test_bootstrap_green_when_only_unreleased_lags() -> None:
    disk = _doc("- old ([`a123456`](u))")
    fresh = _doc(
        "- old ([`a123456`](u))",
        unreleased="- new ([`b765432`](u))",
    )
    assert render.released_sections_diff(disk, fresh) == []
    assert render.unreleased_lag(disk, fresh) == 1


def test_missing_released_section_is_red() -> None:
    disk = _doc("- old")
    fresh = (
        "# Changelog\n\n## [0.2.0] - 2026-02-02\n\n- new\n\n"
        "## [0.1.0] - 2026-01-01\n\n- old\n"
    )
    diff = render.released_sections_diff(disk, fresh)
    assert len(diff) == 1
    assert "0.2.0" in diff[0]


def test_drifted_released_section_is_red() -> None:
    fresh = _doc("- old ([`a123456`](u))")
    disk = _doc("- old tampered ([`a123456`](u))")
    assert render.released_sections_diff(disk, fresh) == [
        "## [0.1.0] - 2026-01-01"
    ]


def test_extra_disk_section_is_tolerated() -> None:
    # shallow clone: disk knows an older release the fresh render lacks
    disk = _doc("- old") + "\n## [0.0.9] - 2025-12-31\n\n- older\n"
    fresh = _doc("- old")
    assert render.released_sections_diff(disk, fresh) == []


def test_crlf_and_trailing_whitespace_normalized() -> None:
    fresh = _doc("- old\n- newer")
    disk = fresh.replace("\n", "\r\n").replace("- newer\r\n", "- newer  \r\n")
    assert render.released_sections_diff(disk, fresh) == []


def test_unreleased_section_missing_on_disk_is_not_an_error() -> None:
    disk = _doc("- old")
    fresh = _doc("- old", unreleased="- new ([`b765432`](u))")
    assert render.released_sections_diff(disk, fresh) == []


def test_unreleased_lag_counts_missing_hashes() -> None:
    disk = _doc("- old ([`a123456`](u))")
    fresh = _doc(
        "- old ([`a123456`](u))",
        unreleased="- x ([`b765432`](u))\n- y ([`c987654`](u))",
    )
    assert render.unreleased_lag(disk, fresh) == 2
    # no unreleased section anywhere → no lag
    assert render.unreleased_lag(disk, disk) == 0


# --- cli generate/check with stubbed git IO ---------------------------------


@pytest.fixture
def cli_repo(tmp_path: Path) -> Path:
    (tmp_path / "zh_overrides.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def overrides_path(cli_repo: Path) -> Path:
    return cli_repo / "zh_overrides.json"


@pytest.fixture
def cli_commits() -> list[RawCommit]:
    # newest → oldest: two unreleased entries, the v0.1.0 boundary (a
    # chore(release) commit that never renders as an entry) and one
    # released entry.
    return [
        _raw("a" * 40, "feat: shiny thing", date="2026-02-01"),
        _raw("b" * 40, "fix: broken thing", date="2026-01-03"),
        _raw("c" * 40, "chore(release): v0.1.0", date="2026-01-02"),
        _raw("d" * 40, "feat: first thing", date="2026-01-01"),
    ]


@pytest.fixture
def stub_gitdata(cli_commits: list[RawCommit], monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_commits(
        repo: Path, *, include_merges: bool = False, limit: int | None = None
    ) -> list[RawCommit]:
        return cli_commits  # same set either way; boundaries drive the output

    def fake_read_tags(repo: Path) -> list[TagRef]:
        return [TagRef(name="v0.1.0", sha="c" * 40)]

    def fake_read_version_bumps(repo: Path) -> list[VersionBump]:
        return []

    def fake_read_current_version(repo: Path) -> str:
        return "0.1.0"

    def fake_remote_url(repo: Path) -> str:
        return "https://gitee.com/demo/yate.git"

    monkeypatch.setattr(gitdata, "read_commits", fake_read_commits)
    monkeypatch.setattr(gitdata, "read_tags", fake_read_tags)
    monkeypatch.setattr(gitdata, "read_version_bumps", fake_read_version_bumps)
    monkeypatch.setattr(gitdata, "read_current_version", fake_read_current_version)
    monkeypatch.setattr(gitdata, "remote_url", fake_remote_url)


def test_generate_writes_files_and_check_is_idempotent(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None
) -> None:
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 0
    en = (cli_repo / "CHANGELOG.md").read_text(encoding="utf-8")
    zh = (cli_repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
    assert "## [0.1.0]" in en
    assert "shiny thing" in en
    assert "chore(release)" not in en
    assert "## [0.1.0]" in zh
    assert cli.generate(cli_repo, check=True, overrides_path=overrides_path) == 0
    # tamper → drift is detected
    (cli_repo / "CHANGELOG.md").write_text(en + "tampered\n", encoding="utf-8")
    assert cli.generate(cli_repo, check=True, overrides_path=overrides_path) == 1


def test_check_ignores_unreleased_drift(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None,
    cli_commits: list[RawCommit],
) -> None:
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 0
    # A newer commit lands in Unreleased; the files on disk lag behind —
    # the gate must stay green because released sections are unchanged.
    cli_commits.insert(0, _raw("e" * 40, "feat: post-commit addition"))
    assert cli.generate(cli_repo, check=True, overrides_path=overrides_path) == 0
    # Drift inside a released section still fails the gate.
    zh = (cli_repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
    (cli_repo / "CHANGELOG.zh.md").write_text(
        zh.replace("## [0.1.0]", "## [0.1.0] tampered"), encoding="utf-8"
    )
    assert cli.generate(cli_repo, check=True, overrides_path=overrides_path) == 1


def test_target_selection_writes_exactly_the_requested_files(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None
) -> None:
    assert cli.generate(
        cli_repo, targets=("root",), overrides_path=overrides_path
    ) == 0
    assert (cli_repo / "CHANGELOG.md").exists()
    assert not (cli_repo / "yate" / "resources").exists()
    assert cli.generate(
        cli_repo, targets=("bundle",), overrides_path=overrides_path
    ) == 0
    bundle = cli_repo / "yate" / "resources"
    assert (bundle / "changelog.en.md").exists()
    assert (bundle / "changelog.zh.md").exists()
    assert (
        bundle / "changelog.en.md"
    ).read_text(encoding="utf-8").startswith("# Changelog")


def test_check_reports_each_target_independently(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 0
    # drift only the bundle copy; the gate names the drifted target
    path = cli_repo / "yate" / "resources" / "changelog.en.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("## [0.1.0]", "## [0.1.0] x"),
        encoding="utf-8",
    )
    code = cli.generate(cli_repo, check=True, overrides_path=overrides_path)
    out = capsys.readouterr().out
    assert code == 1
    assert "yate/resources/changelog.en.md" in out
    assert "0.1.0" in out


def test_check_skips_when_git_history_is_unavailable(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a fresh checkout without history: git log raises
    error = gitdata.GitError("git log failed: not a repository")

    def boom(*_a: object, **_k: object) -> list[RawCommit]:
        raise error

    monkeypatch.setattr(gitdata, "read_commits", boom)
    assert cli.check(cli_repo, overrides_path=overrides_path) == 0
    # generate (write mode) still surfaces the error
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 1


def test_require_zh_fails_when_translations_missing(
    cli_repo: Path, overrides_path: Path, stub_gitdata: None
) -> None:
    # entries a, b, d are untranslated → strict mode fails
    assert cli.generate(
        cli_repo, check=True, require_zh=True, overrides_path=overrides_path,
    ) == 1  # also stale: files were never written
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 0
    assert cli.generate(
        cli_repo, check=True, require_zh=True, overrides_path=overrides_path,
    ) == 1
    # translating UNRELEASED entries keeps the gate red (missing d),
    # but does not make the released sections stale
    overrides = translations.load_overrides(overrides_path)
    translations.upsert_override(overrides, "a" * 7, "闪亮的新功能")
    translations.upsert_override(overrides, "b" * 7, "崩溃修复")
    translations.save_overrides(overrides, overrides_path)
    assert cli.generate(
        cli_repo, check=True, require_zh=True, overrides_path=overrides_path,
    ) == 1
    # translating a RELEASED entry changes released sections → stale
    translations.upsert_override(overrides, "d" * 7, "最早的新功能")
    translations.save_overrides(overrides, overrides_path)
    assert cli.generate(
        cli_repo, check=True, require_zh=True, overrides_path=overrides_path,
    ) == 1  # stale: released zh doc changed
    assert cli.generate(cli_repo, overrides_path=overrides_path) == 0
    assert cli.generate(
        cli_repo, check=True, require_zh=True, overrides_path=overrides_path,
    ) == 0


# --- real git end-to-end ----------------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_generate_and_zh_commit_in_temp_repo(tmp_path: Path) -> None:
    repo = tmp_path
    overrides_path = repo / "overrides.json"

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True
        )

    git("init")
    git("config", "user.name", "tester")
    git("config", "user.email", "tester@example.com")
    git("remote", "add", "origin", "https://gitee.com/demo/yate.git")
    (repo / "yate").mkdir()
    (repo / "yate" / "__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "feat: first feature")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "fix: crash on empty input")
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    (repo / "yate" / "__init__.py").write_text(
        '__version__ = "0.2.0"\n', encoding="utf-8"
    )
    git("add", "-A")
    git("commit", "-m", "chore(release): v0.2.0")

    assert cli.generate(repo, overrides_path=overrides_path) == 0
    en = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.2.0]" in en
    assert "## [0.1.0]" in en
    assert "first feature" in en
    assert "v0.2.0" in en  # compare links
    assert "chore(release)" not in en

    assert (
        cli.zh_commit(repo, sha[:7], "修复空输入崩溃", overrides_path=overrides_path)
        == 0
    )
    data = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert data[sha[:7]]["summary"] == "修复空输入崩溃"
    assert cli.generate(repo, overrides_path=overrides_path) == 0
    zh = (repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
    assert "修复空输入崩溃" in zh
    assert "[缺中文]" in zh  # the other entries remain untranslated
