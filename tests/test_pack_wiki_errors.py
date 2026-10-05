"""Error-code rendering and CLI exit codes of the packaging helpers.

Covers :mod:`tools.pack.errors` (``error[CODE]: message`` plus the optional
``hint:`` line, tracebacks only with ``--debug``) and the mapping of every
library failure onto a stable :class:`~tools.pack.errors.Code` -- including
the issue IKJPEK regression: a Chinese source deleted after collection must
abort the run with ``error[WIKI-0102]`` instead of a raw ``FileNotFoundError``
traceback.

Nothing here shells out: ``git`` and the external translation command are
monkeypatched, and the ``wiki`` subcommand is pointed at a throwaway checkout,
so the suite stays hermetic.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from tools.pack import cli, errors, wiki
from tools.pack.errors import Code, PackError

#: Text ``traceback`` prints as the head of a formatted trace.
_TRACEBACK_HEAD = "Traceback (most recent call last)"


def _touch(root: Path, rel: str, text: str = "# title\n\nbody\n") -> Path:
    """Create *rel* below *root* with *text*, parents included."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _raised_runtime_error() -> BaseException:
    """Return a ``RuntimeError`` that carries a real traceback.

    ``traceback.print_exception`` omits the ``Traceback`` header for an
    exception that was never raised, so the ``--debug`` assertions need an
    instance captured from an actual raise.
    """
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        return exc


def _missing_git(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Stand in for ``subprocess.run`` when git is absent from ``PATH``."""
    raise FileNotFoundError(2, "The system cannot find the file specified", str(cmd))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal fake checkout holding one Chinese-only document."""
    root = tmp_path / "repo"
    _touch(root, ".trae/documents/alpha-plan.md")
    return root


@pytest.fixture()
def cli_repo(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the ``wiki`` subcommand of :func:`tools.pack.cli.main` at *repo*.

    The CLI resolves the checkout through ``_util.repo_root()``; left alone it
    would walk the real repository and publish its documents into the test
    target, so the command has to be bound to the throwaway checkout.
    """
    monkeypatch.setattr("tools._util.repo_root", lambda: repo)
    return repo


def _collect_then_vanish(repo: Path) -> Callable[[Path], list[wiki.WikiPage]]:
    """Wrap ``wiki.collect_sources`` so the Chinese source disappears after it.

    Returns the wrapper to install with ``monkeypatch.setattr``; the file
    ``alpha-plan.md`` is unlinked right after collection, reproducing the
    issue IKJPEK timing window.
    """
    original_collect = wiki.collect_sources
    source = repo / ".trae" / "documents" / "alpha-plan.md"

    def collect_then_delete(repo_root: Path) -> list[wiki.WikiPage]:
        pages = original_collect(repo_root)
        source.unlink()
        return pages

    return collect_then_delete


# --------------------------------------------------------------------------
# errors.report: the terminal contract
# --------------------------------------------------------------------------


def test_report_pack_error_prints_code_message_and_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A PackError renders as ``error[CODE]: message`` followed by ``hint:``."""
    exc = PackError(
        Code.WIKI_ZH_SOURCE_MISSING,
        "Chinese source vanished: alpha-plan.md",
        hint="re-run once the source tree is complete",
    )
    errors.report(exc)
    err = capsys.readouterr().err
    assert "error[WIKI-0102]: Chinese source vanished: alpha-plan.md" in err
    assert "hint: re-run once the source tree is complete" in err
    assert _TRACEBACK_HEAD not in err


def test_report_pack_error_without_hint_prints_one_line_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An error without a hint stays a single ``error[CODE]`` line."""
    errors.report(PackError(Code.WIKI_PAGE_WRITE, "cannot write page Home.md"))
    err = capsys.readouterr().err
    assert err.strip() == "error[WIKI-0106]: cannot write page Home.md"
    assert "hint:" not in err


def test_report_unexpected_exception_uses_unexpected_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-PackError still honours the contract, under ``PKG-0001``."""
    errors.report(_raised_runtime_error())
    err = capsys.readouterr().err
    assert "error[PKG-0001]: boom" in err
    assert _TRACEBACK_HEAD not in err


def test_report_debug_enabled_prints_traceback_after_error_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``debug=True`` appends the traceback without touching the error line."""
    errors.report(_raised_runtime_error(), debug=True)
    err = capsys.readouterr().err
    assert "error[PKG-0001]: boom" in err
    assert _TRACEBACK_HEAD in err


# --------------------------------------------------------------------------
# issue IKJPEK: a Chinese source vanishing after collection
# --------------------------------------------------------------------------


def test_run_raises_wiki_error_when_zh_source_vanishes(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A source deleted after collection aborts the run with ``WIKI-0102``.

    Regression guard for the bare ``FileNotFoundError`` the issue reported:
    library code must raise a coded :class:`~tools.pack.wiki.WikiError`, never
    let a filesystem exception escape.
    """
    monkeypatch.setattr(wiki, "collect_sources", _collect_then_vanish(repo))
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.run(tmp_path / "wiki", None, repo_root=repo)
    rendered = excinfo.value.render()
    assert excinfo.value.code == Code.WIKI_ZH_SOURCE_MISSING
    assert rendered.startswith("error[WIKI-0102]: Chinese source vanished: alpha-plan.md")
    assert rendered.endswith("\nhint: re-run once the source tree is complete")


def test_cli_wiki_reports_vanished_source_as_wiki_0102_without_traceback(
    cli_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI renders the vanished source as ``error[WIKI-0102]``, exit 1."""
    monkeypatch.setattr(wiki, "collect_sources", _collect_then_vanish(cli_repo))
    code = cli.main(["wiki", "--target", str(tmp_path / "wiki")])
    assert code == 1
    err = capsys.readouterr().err
    assert "error[WIKI-0102]: Chinese source vanished: alpha-plan.md" in err
    assert "hint: re-run once the source tree is complete" in err
    assert _TRACEBACK_HEAD not in err


# --------------------------------------------------------------------------
# library failures mapped onto codes
# --------------------------------------------------------------------------


def test_collision_error_carries_collision_code_and_renders_hint(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A duplicate target yields ``WIKI-0101`` and renders its hint line.

    The collision is produced through the public collector (a second source
    of the same base name in another ``.trae`` collection); the sibling suite
    already covers the raise itself, so this one pins the code and the
    rendered ``hint:`` line -- the part a user actually sees.
    """
    _touch(repo, ".trae/wikis/alpha-plan.md", "# duplicate base name\n")
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.collect_sources(repo)
    assert excinfo.value.code == Code.WIKI_TARGET_COLLISION
    errors.report(excinfo.value)
    err = capsys.readouterr().err
    assert "error[WIKI-0101]: wiki target collision on 'alpha-plan.zh.md'" in err
    assert "hint: rename one of the colliding source documents" in err
    assert _TRACEBACK_HEAD not in err


def test_run_git_without_git_on_path_reports_git_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing git executable becomes ``PKG-0002`` plus an install hint."""
    monkeypatch.setattr(wiki.subprocess, "run", _missing_git)
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.run_git(tmp_path, "status")
    assert excinfo.value.code == Code.GIT_MISSING
    assert excinfo.value.hint == "install git or run without --push"


def test_cli_wiki_push_without_git_reports_pkg_0002(
    cli_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``--push`` without git exits 1 with ``error[PKG-0002]``."""
    monkeypatch.setattr(wiki.subprocess, "run", _missing_git)
    code = cli.main(["wiki", "--target", str(tmp_path / "wiki"), "--push"])
    assert code == 1
    err = capsys.readouterr().err
    assert "error[PKG-0002]: git executable not found on PATH" in err
    assert "hint: install git or run without --push" in err
    assert _TRACEBACK_HEAD not in err


def test_translate_via_cmd_failure_reports_wiki_0201_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A non-zero translator exit is reported as ``error[WIKI-0201]``."""

    def failing_run(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([str(cmd)], 3, "", "kaput")

    monkeypatch.setattr(wiki.subprocess, "run", failing_run)
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    err = capsys.readouterr().err
    assert "error[WIKI-0201]: translate-cmd failed (rc=3): kaput" in err
    assert _TRACEBACK_HEAD not in err


def test_translate_via_cmd_timeout_reports_wiki_0202_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A translator that exceeds its budget is reported as ``WIKI-0202``."""

    def timed_out_run(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=[str(cmd)], timeout=wiki.TRANSLATE_TIMEOUT_S)

    monkeypatch.setattr(wiki.subprocess, "run", timed_out_run)
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    err = capsys.readouterr().err
    assert "error[WIKI-0202]: translate-cmd timed out after 900s" in err
    assert _TRACEBACK_HEAD not in err


def test_load_manifest_unreadable_reports_wiki_0104(tmp_path: Path) -> None:
    """A manifest that cannot be read aborts with ``WIKI-0104``, not a reset.

    The manifest path is made a directory: ``exists()`` succeeds while
    ``read_text()`` raises ``IsADirectoryError`` (an ``OSError``).
    """
    (tmp_path / wiki.MANIFEST_NAME).mkdir()
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.load_manifest(tmp_path)
    assert excinfo.value.code == Code.WIKI_MANIFEST_READ
    assert "manifest read error" in str(excinfo.value)


def test_cli_icon_missing_source_reports_icon_0301(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing icon source exits 1 with ``error[ICON-0301]`` and no traceback.

    ``icon.build_icon`` raises ``FileNotFoundError`` (or ``RuntimeError`` when
    the optional Pillow extra is absent); both are mapped to ``ICON_BUILD`` by
    the ``icon`` handler, so only the code is asserted here.
    """
    code = cli.main([
        "icon",
        "--source", str(tmp_path / "absent.jpg"),
        "--target", str(tmp_path / "out.ico"),
    ])
    assert code == 1
    err = capsys.readouterr().err
    assert "error[ICON-0301]:" in err
    assert _TRACEBACK_HEAD not in err


def test_cli_rosters_unwritable_output_reports_rosters_0302(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A roster output that cannot be written exits 1 with ``ROSTERS-0302``.

    The output path is a directory, so ``write_text`` raises
    ``IsADirectoryError`` -- a portable ``OSError`` that needs no chmod games
    (unreliable under Windows ACLs).
    """
    blocked = tmp_path / "roster.svg"
    blocked.mkdir()
    code = cli.main(["rosters", "--output", str(blocked)])
    assert code == 1
    err = capsys.readouterr().err
    assert "error[ROSTERS-0302]:" in err
    assert _TRACEBACK_HEAD not in err


# --------------------------------------------------------------------------
# --debug only widens the output
# --------------------------------------------------------------------------


def test_cli_wiki_debug_adds_traceback_without_changing_error_line(
    cli_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--debug`` adds the traceback; the ``error[CODE]`` line is unchanged."""
    monkeypatch.setattr(wiki, "collect_sources", _collect_then_vanish(cli_repo))
    code = cli.main(["wiki", "--target", str(tmp_path / "wiki"), "--debug"])
    assert code == 1
    err = capsys.readouterr().err
    assert "error[WIKI-0102]: Chinese source vanished: alpha-plan.md" in err
    assert "hint: re-run once the source tree is complete" in err
    assert _TRACEBACK_HEAD in err
