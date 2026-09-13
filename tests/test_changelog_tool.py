"""Tests for the tools/changelog generator.

Strategy (frozen in the plan): the IO boundary is only ``gitdata``; classify,
segments, render, gitee and translations run on synthetic data.  One optional
end-to-end test exercises a real throwaway git repository and skips when git
is unavailable.
"""

from __future__ import annotations

import json
import io
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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


class ClassifyTests(unittest.TestCase):
    def test_feat_is_feature_and_prefix_stripped(self) -> None:
        commit = classify_commit(_raw("a" * 40, "feat: add fuzzy search"))
        self.assertIs(commit.category, Category.FEATURE)
        self.assertEqual(commit.summary_en, "add fuzzy search")
        self.assertIsNone(commit.scope)
        self.assertFalse(commit.is_breaking)

    def test_fix_with_scope(self) -> None:
        commit = classify_commit(_raw("b" * 40, "fix(editor): keep cursor visible"))
        self.assertIs(commit.category, Category.FIX)
        self.assertEqual(commit.scope, "editor")
        self.assertEqual(commit.summary_en, "keep cursor visible")

    def test_bang_marks_breaking(self) -> None:
        commit = classify_commit(_raw("c" * 40, "refactor(core)!: drop old api"))
        self.assertTrue(commit.is_breaking)
        self.assertIs(commit.category, Category.REFACTOR)

    def test_breaking_change_footer(self) -> None:
        commit = classify_commit(
            _raw("d" * 40, "feat: new api", body="something\nBREAKING CHANGE: gone")
        )
        self.assertTrue(commit.is_breaking)

    def test_build_ci_chore_are_tooling(self) -> None:
        for subject in ("build: tweak", "ci: run nightly", "chore: tidy"):
            with self.subTest(subject=subject):
                commit = classify_commit(_raw("e" * 40, subject))
                self.assertIs(commit.category, Category.TOOLING)

    def test_unknown_type_and_no_prefix_are_other(self) -> None:
        # unknown type still parses as conventional → prefix stripped
        deploy = classify_commit(_raw("f" * 40, "deploy: ship it"))
        self.assertIs(deploy.category, Category.OTHER)
        self.assertEqual(deploy.summary_en, "ship it")
        # no prefix at all → full subject kept
        plain = classify_commit(_raw("9" * 40, "Add a plain subject"))
        self.assertIs(plain.category, Category.OTHER)
        self.assertEqual(plain.summary_en, "Add a plain subject")

    def test_release_bump_commit_is_not_an_entry(self) -> None:
        commit = classify_commit(_raw("1" * 40, "chore(release): v0.2.0"))
        self.assertFalse(is_changelog_entry(commit))
        self.assertTrue(is_changelog_entry(classify_commit(_raw("2" * 40, "feat: x"))))


class SegmentsTests(unittest.TestCase):
    def setUp(self) -> None:
        # topo order newest → oldest; dates are deliberately NOT monotonic
        self.full = [
            _raw("a" * 40, "feat: newest", date="2026-01-01"),
            _raw("b" * 40, "fix: middle", date="2026-06-01"),
            _raw("c" * 40, "feat: oldest", date="2026-03-01"),
        ]
        self.entries = _entries(*self.full)

    def test_tag_boundary(self) -> None:
        boundaries = segments.build_boundaries(
            [TagRef(name="v0.2.0", sha="b" * 40)], [], self.full, current_version="0.2.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.2.0"
        )
        self.assertEqual([s.version for s in result], [None, "0.2.0"])
        unreleased = result[0]
        versioned = result[1]
        self.assertEqual([c.sha[:1] for c in unreleased.commits], ["a"])
        # the boundary commit b belongs to the NEW version; older c folds in
        self.assertEqual([c.sha[:1] for c in versioned.commits], ["b", "c"])
        self.assertEqual(versioned.date, "2026-06-01")  # boundary commit date
        self.assertEqual(versioned.range_from, "ROOT")
        self.assertEqual(versioned.range_to, "v0.2.0")
        self.assertTrue(versioned.initial)

    def test_bump_fallback_without_tags(self) -> None:
        bumps = [VersionBump(sha="c" * 40, version="0.1.0"), VersionBump(sha="b" * 40, version="0.2.0")]
        boundaries = segments.build_boundaries(
            [], bumps, self.full, current_version="0.2.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.2.0"
        )
        self.assertEqual([s.version for s in result], [None, "0.2.0", "0.1.0"])
        self.assertEqual(result[1].range_from, "v0.1.0")
        self.assertEqual(result[1].range_to, "v0.2.0")
        self.assertFalse(result[1].initial)

    def test_repeated_bump_merges_into_one_segment(self) -> None:
        bumps = [
            VersionBump(sha="c" * 40, version="0.1.0"),
            VersionBump(sha="b" * 40, version="0.2.0"),
            VersionBump(sha="a" * 40, version="0.2.0"),  # re-bump of same version
        ]
        boundaries = segments.build_boundaries(
            [], bumps, self.full, current_version="0.2.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.2.0"
        )
        versions = [s.version for s in result]
        self.assertEqual(versions, [None, "0.2.0", "0.1.0"])
        self.assertEqual(versions.count("0.2.0"), 1)  # re-bump did not split

    def test_cold_start_single_segment(self) -> None:
        boundaries = segments.build_boundaries(
            [], [], self.full, current_version="0.1.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.1.0"
        )
        self.assertEqual(len(result), 1)
        segment = result[0]
        self.assertEqual(segment.version, "0.1.0")
        self.assertEqual(segment.date, "2026-01-01")  # newest commit's date
        self.assertTrue(segment.initial)
        self.assertEqual(len(segment.commits), 3)
        self.assertEqual(segment.range_from, "ROOT")

    def test_unreleased_only_when_commits_above_boundary(self) -> None:
        boundaries = segments.build_boundaries(
            [TagRef(name="v0.1.0", sha="a" * 40)], [], self.full, current_version="0.1.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.1.0"
        )
        self.assertEqual([s.version for s in result], ["0.1.0"])
        self.assertEqual(len(result[0].commits), 3)

    def test_boundaries_ignore_dates_and_follow_topo(self) -> None:
        # a is newest by topo although its date is the oldest of all three
        boundaries = segments.build_boundaries(
            [TagRef(name="v0.1.0", sha="c" * 40)], [], self.full, current_version="0.1.0"
        )
        result = segments.build_segments(
            self.full, self.entries, boundaries, current_version="0.1.0"
        )
        self.assertEqual([s.version for s in result], [None, "0.1.0"])
        self.assertEqual([c.sha[:1] for c in result[0].commits], ["a", "b"])


class RenderTests(unittest.TestCase):
    def _segments(self) -> list[segments.ReleaseSegment]:
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

    def test_english_document(self) -> None:
        doc = render.render_document(
            self._segments(), lang="en", remote=REMOTE, overrides={}
        )
        self.assertIn("## [0.2.0] - 2026-01-01", doc)
        self.assertIn("### ⚠ BREAKING CHANGES", doc)
        self.assertIn("### Features", doc)
        self.assertIn("### Bug Fixes", doc)
        self.assertIn("](https://gitee.com/demo/yate/commit/" + "a" * 40 + ")", doc)
        self.assertIn("](https://gitee.com/demo/yate/compare/ROOT...v0.2.0)", doc)
        self.assertIn("_Initial release._", doc)
        self.assertNotIn("[缺中文]", doc)
        # release bump commits are boundaries, never entries
        self.assertNotIn("chore(release)", doc)

    def test_breaking_changes_come_first(self) -> None:
        doc = render.render_document(
            self._segments(), lang="en", remote=REMOTE, overrides={}
        )
        self.assertLess(doc.index("BREAKING CHANGES"), doc.index("### Features"))

    def test_chinese_document_with_overrides(self) -> None:
        overrides = {
            "b" * 7: translations.OverrideEntry(summary="编辑器标签栏", detail="可点击切换"),
        }
        doc = render.render_document(
            self._segments(), lang="zh", remote=REMOTE, overrides=overrides
        )
        self.assertIn("### 新功能", doc)
        self.assertIn("### 问题修复", doc)
        self.assertIn("### ⚠ 破坏性变更", doc)
        self.assertIn("- 编辑器标签栏", doc)
        self.assertIn("  - 可点击切换", doc)
        self.assertIn("[缺中文]", doc)  # untranslated entries fall back
        self.assertIn("_首个版本。_", doc)

    def test_no_remote_renders_plain_hashes(self) -> None:
        doc = render.render_document(
            self._segments(), lang="en", remote=None, overrides={}
        )
        self.assertIn(f"(`{'a' * 7}`)", doc)
        self.assertNotIn("https://", doc)


class GiteeTests(unittest.TestCase):
    def test_parse_https_remote(self) -> None:
        remote = gitee.parse_remote("https://gitee.com/jermaine/yate.git")
        assert remote is not None
        self.assertEqual((remote.host, remote.owner, remote.repo), ("gitee.com", "jermaine", "yate"))
        self.assertEqual(remote.web_base, "https://gitee.com/jermaine/yate")

    def test_parse_ssh_remote(self) -> None:
        remote = gitee.parse_remote("git@gitee.com:jermaine/yate.git")
        assert remote is not None
        self.assertEqual(remote.owner, "jermaine")
        remote2 = gitee.parse_remote("ssh://git@gitee.com/jermaine/yate.git")
        assert remote2 is not None
        self.assertEqual(remote2.repo, "yate")

    def test_parse_unknown_returns_none(self) -> None:
        self.assertIsNone(gitee.parse_remote("https://example.org/only-owner"))

    def test_link_construction(self) -> None:
        self.assertEqual(
            gitee.commit_url(REMOTE, "abc123"),
            "https://gitee.com/demo/yate/commit/abc123",
        )
        self.assertEqual(
            gitee.compare_url(REMOTE, "v0.1.0", "v0.2.0"),
            "https://gitee.com/demo/yate/compare/v0.1.0...v0.2.0",
        )


class TranslationsTests(unittest.TestCase):
    def test_upsert_deduplicates(self) -> None:
        overrides: dict[str, translations.OverrideEntry] = {}
        self.assertTrue(translations.upsert_override(overrides, "abc1234", "摘要"))
        self.assertFalse(translations.upsert_override(overrides, "abc1234", "摘要"))
        self.assertTrue(translations.upsert_override(overrides, "abc1234", "新摘要"))

    def test_roundtrip_keeps_chinese_raw_and_sorted(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh_overrides.json"
            overrides: dict[str, translations.OverrideEntry] = {}
            translations.upsert_override(overrides, "bbb2222", "后写")
            translations.upsert_override(overrides, "aaa1111", "先写", detail="细节")
            translations.save_overrides(overrides, path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("先写", text)  # ensure_ascii=False
            self.assertLess(text.index("aaa1111"), text.index("bbb2222"))
            loaded = translations.load_overrides(path)
            self.assertEqual(loaded["aaa1111"].summary, "先写")
            self.assertEqual(loaded["aaa1111"].detail, "细节")
            data = json.loads(text)
            self.assertEqual(list(data), sorted(list(data)))  # sorted keys

    def test_load_missing_file_is_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(translations.load_overrides(Path(tmp) / "nope.json"), {})


class GitdataParserTests(unittest.TestCase):
    def test_parse_log_output_with_chinese_and_separators(self) -> None:
        sha1, sha2 = "a" * 40, "b" * 40
        record1 = f"{sha1}\x1f{sha1[:7]}\x1f2026-09-13\x1ffeat: 中文支持\x1f正文第一行\x1f嵌入分隔符\x1e"
        record2 = f"{sha2}\x1f{sha2[:7]}\x1f2026-09-12\x1ffix: something\x1f\x1e"
        commits = gitdata.parse_log_output(record1 + record2)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].subject, "feat: 中文支持")
        self.assertEqual(commits[0].short_sha, sha1[:7])
        self.assertIn("嵌入分隔符", commits[0].body)  # body keeps stray separators
        self.assertEqual(commits[1].body, "")

    def test_parse_log_output_rejects_malformed_record(self) -> None:
        with self.assertRaises(gitdata.GitError):
            gitdata.parse_log_output("only-two\x1ffields\x1e")

    def test_parse_bump_patch_only_counts_added_lines(self) -> None:
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
        self.assertEqual(bumps, [VersionBump(sha=sha1, version="0.2.0")])


class RenderTargetTests(unittest.TestCase):
    """Root vs bundle headers (section 4: two render targets)."""

    def _segments(self) -> list[segments.ReleaseSegment]:
        full = [_raw("a" * 40, "feat: thing", date="2026-02-02")]
        boundaries = segments.build_boundaries([], [], full, current_version="0.1.0")
        return segments.build_segments(
            full, _entries(*full), boundaries, current_version="0.1.0"
        )

    def test_root_header_has_maintainer_wording_and_sibling_link(self) -> None:
        doc = render.render_document(
            self._segments(), lang="en", remote=REMOTE, overrides={}
        )
        self.assertIn("do not edit by hand", doc)
        self.assertIn("[CHANGELOG.zh.md](CHANGELOG.zh.md)", doc)

    def test_bundle_header_is_end_user_facing(self) -> None:
        doc = render.render_document(
            self._segments(), lang="en", remote=REMOTE, overrides={},
            target="bundle", generated="Generated from the git history · yate 0.1.0",
        )
        self.assertTrue(doc.startswith("# Changelog\n\n> Generated from"))
        self.assertNotIn("do not edit", doc)
        self.assertNotIn("CHANGELOG.zh.md", doc)
        zh = render.render_document(
            self._segments(), lang="zh", remote=REMOTE, overrides={},
            target="bundle", generated="由 git 历史自动生成 · yate 0.1.0",
        )
        self.assertTrue(zh.startswith("# 变更日志"))
        self.assertNotIn("请勿手工编辑", zh)


class ReleasedSectionsDiffTests(unittest.TestCase):
    """The 4.1 gate semantics as pure functions on synthetic documents."""

    def _doc(self, body: str, *, unreleased: str = "") -> str:
        parts = ["# Changelog", ""]
        if unreleased:
            parts += ["## [Unreleased]", "", unreleased, ""]
        parts += ["## [0.1.0] - 2026-01-01", "", body]
        return "\n".join(parts) + "\n"

    def test_bootstrap_green_when_only_unreleased_lags(self) -> None:
        disk = self._doc("- old ([`a123456`](u))")
        fresh = self._doc(
            "- old ([`a123456`](u))",
            unreleased="- new ([`b765432`](u))",
        )
        self.assertEqual(render.released_sections_diff(disk, fresh), [])
        self.assertEqual(render.unreleased_lag(disk, fresh), 1)

    def test_missing_released_section_is_red(self) -> None:
        disk = self._doc("- old")
        fresh = (
            "# Changelog\n\n## [0.2.0] - 2026-02-02\n\n- new\n\n"
            "## [0.1.0] - 2026-01-01\n\n- old\n"
        )
        diff = render.released_sections_diff(disk, fresh)
        self.assertEqual(len(diff), 1)
        self.assertIn("0.2.0", diff[0])

    def test_drifted_released_section_is_red(self) -> None:
        fresh = self._doc("- old ([`a123456`](u))")
        disk = self._doc("- old tampered ([`a123456`](u))")
        self.assertEqual(
            render.released_sections_diff(disk, fresh),
            ["## [0.1.0] - 2026-01-01"],
        )

    def test_extra_disk_section_is_tolerated(self) -> None:
        # shallow clone: disk knows an older release the fresh render lacks
        disk = self._doc("- old") + "\n## [0.0.9] - 2025-12-31\n\n- older\n"
        fresh = self._doc("- old")
        self.assertEqual(render.released_sections_diff(disk, fresh), [])

    def test_crlf_and_trailing_whitespace_normalized(self) -> None:
        fresh = self._doc("- old\n- newer")
        disk = fresh.replace("\n", "\r\n").replace("- newer\r\n", "- newer  \r\n")
        self.assertEqual(render.released_sections_diff(disk, fresh), [])

    def test_unreleased_section_missing_on_disk_is_not_an_error(self) -> None:
        disk = self._doc("- old")
        fresh = self._doc("- old", unreleased="- new ([`b765432`](u))")
        self.assertEqual(render.released_sections_diff(disk, fresh), [])

    def test_unreleased_lag_counts_missing_hashes(self) -> None:
        disk = self._doc("- old ([`a123456`](u))")
        fresh = self._doc(
            "- old ([`a123456`](u))",
            unreleased="- x ([`b765432`](u))\n- y ([`c987654`](u))",
        )
        self.assertEqual(render.unreleased_lag(disk, fresh), 2)
        # no unreleased section anywhere → no lag
        self.assertEqual(render.unreleased_lag(disk, disk), 0)


class CliCheckTests(unittest.TestCase):
    """generate/check with stubbed git IO and a temporary output directory."""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        # newest → oldest: two unreleased entries, the v0.1.0 boundary (a
        # chore(release) commit that never renders as an entry) and one
        # released entry.
        self.full = [
            _raw("a" * 40, "feat: shiny thing", date="2026-02-01"),
            _raw("b" * 40, "fix: broken thing", date="2026-01-03"),
            _raw("c" * 40, "chore(release): v0.1.0", date="2026-01-02"),
            _raw("d" * 40, "feat: first thing", date="2026-01-01"),
        ]
        overrides_path = self.repo / "zh_overrides.json"
        overrides_path.write_text("{}\n", encoding="utf-8")
        self.overrides_path = overrides_path
        self._quiet_stdout()

    def _quiet_stdout(self) -> None:
        """The CLI prints stats; keep the unittest output clean."""
        patcher = patch("sys.stdout", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_gitdata(self) -> None:
        def fake_read_commits(
            repo: Path, *, include_merges: bool = False, limit: int | None = None
        ) -> list[RawCommit]:
            return self.full  # same set either way; boundaries drive the output

        def fake_read_tags(repo: Path) -> list[TagRef]:
            return [TagRef(name="v0.1.0", sha="c" * 40)]

        def fake_read_version_bumps(repo: Path) -> list[VersionBump]:
            return []

        def fake_read_current_version(repo: Path) -> str:
            return "0.1.0"

        def fake_remote_url(repo: Path) -> str:
            return "https://gitee.com/demo/yate.git"

        for target, replacement in (
            ("read_commits", fake_read_commits),
            ("read_tags", fake_read_tags),
            ("read_version_bumps", fake_read_version_bumps),
            ("read_current_version", fake_read_current_version),
            ("remote_url", fake_remote_url),
        ):
            patcher = patch.object(gitdata, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_generate_writes_files_and_check_is_idempotent(self) -> None:
        self._patch_gitdata()
        self.assertEqual(
            cli.generate(self.repo, overrides_path=self.overrides_path), 0
        )
        en = (self.repo / "CHANGELOG.md").read_text(encoding="utf-8")
        zh = (self.repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
        self.assertIn("## [0.1.0]", en)
        self.assertIn("shiny thing", en)
        self.assertNotIn("chore(release)", en)
        self.assertIn("## [0.1.0]", zh)
        self.assertEqual(
            cli.generate(
                self.repo, check=True, overrides_path=self.overrides_path
            ), 0
        )
        # tamper → drift is detected
        (self.repo / "CHANGELOG.md").write_text(en + "tampered\n", encoding="utf-8")
        self.assertEqual(
            cli.generate(
                self.repo, check=True, overrides_path=self.overrides_path
            ), 1
        )

    def test_check_ignores_unreleased_drift(self) -> None:
        self._patch_gitdata()
        self.assertEqual(
            cli.generate(self.repo, overrides_path=self.overrides_path), 0
        )
        # A newer commit lands in Unreleased; the files on disk lag behind —
        # the gate must stay green because released sections are unchanged.
        self.full.insert(0, _raw("e" * 40, "feat: post-commit addition"))
        self.assertEqual(
            cli.generate(
                self.repo, check=True, overrides_path=self.overrides_path
            ), 0
        )
        # Drift inside a released section still fails the gate.
        zh = (self.repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
        (self.repo / "CHANGELOG.zh.md").write_text(
            zh.replace("## [0.1.0]", "## [0.1.0] tampered"), encoding="utf-8"
        )
        self.assertEqual(
            cli.generate(
                self.repo, check=True, overrides_path=self.overrides_path
            ), 1
        )

    def test_target_selection_writes_exactly_the_requested_files(self) -> None:
        self._patch_gitdata()
        self.assertEqual(
            cli.generate(
                self.repo, targets=("root",), overrides_path=self.overrides_path
            ), 0
        )
        self.assertTrue((self.repo / "CHANGELOG.md").exists())
        self.assertFalse((self.repo / "yate" / "resources").exists())
        self.assertEqual(
            cli.generate(
                self.repo, targets=("bundle",), overrides_path=self.overrides_path
            ), 0
        )
        bundle = self.repo / "yate" / "resources"
        self.assertTrue((bundle / "changelog.en.md").exists())
        self.assertTrue((bundle / "changelog.zh.md").exists())
        self.assertTrue(
            (bundle / "changelog.en.md")
            .read_text(encoding="utf-8")
            .startswith("# Changelog")
        )

    def test_check_reports_each_target_independently(self) -> None:
        self._patch_gitdata()
        self.assertEqual(
            cli.generate(self.repo, overrides_path=self.overrides_path), 0
        )
        # drift only the bundle copy; the gate names the drifted target
        path = self.repo / "yate" / "resources" / "changelog.en.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("## [0.1.0]", "## [0.1.0] x"),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = cli.generate(
                self.repo, check=True, overrides_path=self.overrides_path
            )
        self.assertEqual(code, 1)
        out = buf.getvalue()
        self.assertIn("yate/resources/changelog.en.md", out)
        self.assertIn("0.1.0", out)

    def test_check_skips_when_git_history_is_unavailable(self) -> None:
        self._patch_gitdata()
        # a fresh checkout without history: git log raises
        error = gitdata.GitError("git log failed: not a repository")

        def boom(*_a: object, **_k: object) -> list[RawCommit]:
            raise error

        with patch.object(gitdata, "read_commits", boom):
            self.assertEqual(
                cli.check(self.repo, overrides_path=self.overrides_path), 0
            )
            # generate (write mode) still surfaces the error
            self.assertEqual(
                cli.generate(self.repo, overrides_path=self.overrides_path), 1
            )

    def test_require_zh_fails_when_translations_missing(self) -> None:
        self._patch_gitdata()
        # entries a, b, d are untranslated → strict mode fails
        self.assertEqual(
            cli.generate(
                self.repo, check=True, require_zh=True,
                overrides_path=self.overrides_path,
            ), 1  # also stale: files were never written
        )
        self.assertEqual(
            cli.generate(self.repo, overrides_path=self.overrides_path), 0
        )
        self.assertEqual(
            cli.generate(
                self.repo, check=True, require_zh=True,
                overrides_path=self.overrides_path,
            ), 1
        )
        # translating UNRELEASED entries keeps the gate red (missing d),
        # but does not make the released sections stale
        overrides = translations.load_overrides(self.overrides_path)
        translations.upsert_override(overrides, "a" * 7, "闪亮的新功能")
        translations.upsert_override(overrides, "b" * 7, "崩溃修复")
        translations.save_overrides(overrides, self.overrides_path)
        self.assertEqual(
            cli.generate(
                self.repo, check=True, require_zh=True,
                overrides_path=self.overrides_path,
            ), 1
        )
        # translating a RELEASED entry changes released sections → stale
        translations.upsert_override(overrides, "d" * 7, "最早的新功能")
        translations.save_overrides(overrides, self.overrides_path)
        self.assertEqual(
            cli.generate(
                self.repo, check=True, require_zh=True,
                overrides_path=self.overrides_path,
            ), 1  # stale: released zh doc changed
        )
        self.assertEqual(
            cli.generate(self.repo, overrides_path=self.overrides_path), 0
        )
        self.assertEqual(
            cli.generate(
                self.repo, check=True, require_zh=True,
                overrides_path=self.overrides_path,
            ), 0
        )


class RealGitEndToEndTests(unittest.TestCase):
    """One true end-to-end case against a throwaway git repository."""

    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git executable not available")
        patcher = patch("sys.stdout", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_generate_and_zh_commit_in_temp_repo(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
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

            self.assertEqual(
                cli.generate(repo, overrides_path=overrides_path), 0
            )
            en = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("## [0.2.0]", en)
            self.assertIn("## [0.1.0]", en)
            self.assertIn("first feature", en)
            self.assertIn("v0.2.0", en)  # compare links
            self.assertNotIn("chore(release)", en)

            self.assertEqual(
                cli.zh_commit(repo, sha[:7], "修复空输入崩溃", overrides_path=overrides_path),
                0,
            )
            data = json.loads(overrides_path.read_text(encoding="utf-8"))
            self.assertEqual(data[sha[:7]]["summary"], "修复空输入崩溃")
            self.assertEqual(
                cli.generate(repo, overrides_path=overrides_path), 0
            )
            zh = (repo / "CHANGELOG.zh.md").read_text(encoding="utf-8")
            self.assertIn("修复空输入崩溃", zh)
            self.assertIn("[缺中文]", zh)  # the other entries remain untranslated


if __name__ == "__main__":
    unittest.main()
