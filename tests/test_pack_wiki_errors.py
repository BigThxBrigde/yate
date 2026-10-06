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

import ast
import subprocess
from collections.abc import Callable
from io import StringIO
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


@pytest.mark.parametrize("returncode", [130, 0xC000013A, 0xC000013A - 0x100000000, -2])
def test_translate_via_cmd_maps_a_console_interrupt_to_keyboard_interrupt(
    returncode: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``Ctrl+C`` child raises instead of reporting a failed page.

    The console broadcasts the interrupt to the whole process group, so
    every translator of a run dies of it -- Windows with
    ``STATUS_CONTROL_C_EXIT`` (3221225786), POSIX with ``-SIGINT``, and the
    bundled translator itself with 130 once it handles the interrupt
    cleanly.  Treating that as a translation failure used to print one
    ``error[WIKI-0201]`` (traceback and all) per remaining page while the
    run kept going after the user asked to stop.
    """
    traceback = "Traceback (most recent call last):\nKeyboardInterrupt\n^C\n"

    def interrupted_run(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([str(cmd)], returncode, "", traceback)

    monkeypatch.setattr(wiki.subprocess, "run", interrupted_run)
    with pytest.raises(KeyboardInterrupt):
        wiki.translate_via_cmd("# zh in\n", "fake-cmd")
    err = capsys.readouterr().err
    assert f"error[{Code.WIKI_TRANSLATE_FAILED}]" not in err
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


def test_store_manifest_failure_reports_wiki_0105(tmp_path: Path) -> None:
    """A manifest that cannot be written says so with its own code.

    Review R-03: the store is read back on the next run, so a failed write
    there must be distinguishable from an ordinary page write -- both used
    to report ``WIKI-0106`` and ``WIKI_MANIFEST_WRITE`` was dead code.

    The manifest path is turned into a directory so the *real*
    ``_write_page_text`` fails: stubbing that helper instead would make the
    test pass whether or not the caller passes the code along.
    """
    (tmp_path / wiki.MANIFEST_NAME).mkdir()
    with pytest.raises(wiki.WikiError) as excinfo:
        wiki.store_manifest(tmp_path, {"page.zh.md": "abc"})
    assert excinfo.value.code == wiki.Code.WIKI_MANIFEST_WRITE


def test_source_read_oserror_reports_wiki_0103(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable source is not reported as a vanished one.

    Review R-04: a permission error or a failing disk used to surface as
    ``WIKI-0102`` ("Chinese source vanished"), sending the reader after a
    rename that never happened, and leaving ``WIKI-0103`` unreferenced.
    """
    source = tmp_path / "alpha-plan.md"
    source.write_text("# alpha\n", encoding="utf-8")

    def denied(path: Path) -> bytes:
        del path
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(wiki.WikiError) as excinfo:
        getattr(wiki, "_read_source_bytes")(source)
    assert excinfo.value.code == wiki.Code.WIKI_SOURCE_UNREADABLE
    assert "check file permissions" in (excinfo.value.hint or "")


def test_empty_translation_stage_reports_nothing(
    tmp_path: Path,
) -> None:
    """An empty plan list is a no-op, not ``max_workers=0``.

    Review R-07: ``min(resolve_jobs(...), 0)`` used to reach the pool as
    ``max_workers=0``, which raises.  ``run()`` filters empty plans out,
    so the guard is only reachable from a direct call -- which is why it is
    driven through ``getattr`` here (pyright forbids private access).
    """
    report = getattr(wiki, "_translate_pending")(
        [],
        "fake-cmd",
        target=tmp_path / "wiki",
        jobs=None,
        console=wiki.Console(file=StringIO()),
    )
    assert report.translated == 0
    assert report.missing == []
    assert report.stale == []


def test_translate_all_without_a_hook_says_it_has_no_effect(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--translate-all`` on its own is a no-op with a note (review R-23).

    The code has always printed the warning and carried on with the
    incremental path, but neither README said so and no test pinned it.
    """
    assert wiki.run(
        tmp_path / "wiki", None, translate_all=True, repo_root=repo
    ) == 0
    captured = capsys.readouterr()
    assert "--translate-all has no effect without --translate-cmd" in captured.err


def test_a_failing_pool_setup_does_not_strand_the_collect_policy(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A setup failure must not leave later failures queued into the void.

    Review R-21: the collect policy is process-global and used to be
    installed *before* the protected region, so a failure while starting
    the display or building the pool stranded it -- every translation
    failure after that was collected with nobody left to read the queue,
    which is silent error reporting.
    """

    def no_threads(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("cannot start new thread")

    monkeypatch.setattr(wiki, "ThreadPoolExecutor", no_threads)
    with pytest.raises(RuntimeError):
        wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=repo, jobs=1)
    # The policy is back to serial and the queue is empty, so a later
    # failure writes itself instead of disappearing into the collector.
    assert getattr(wiki, "_emit_mode") == "print"
    queue = getattr(wiki, "_COLLECTED_FAILURES")
    assert queue.qsize() == 0
    getattr(wiki, "_emit_translate_failure")("error[TEST]: still visible")
    captured = capsys.readouterr()
    assert "error[TEST]: still visible" in captured.err
    assert queue.qsize() == 0


def test_the_collect_policy_is_installed_inside_the_protected_region() -> None:
    """The collect switch and the fallible setup must sit inside the ``try``.

    Review R-21 is a structural defect, so it needs a structural guard: the
    process-global policy is restored by that ``finally``, therefore both the
    assignment that installs it and the steps that can fail before the pool
    exists (starting the display, creating the executor) must be inside the
    protected region.  An exception raised outside it would strand the
    policy, and every later failure would be queued with nobody to read it --
    which no behavioural test can provoke once the structure is correct.
    """
    source = Path(__file__).resolve().parents[1] / "tools" / "pack" / "wiki.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_translate_pending"
    )
    protected_ids = {
        id(child)
        for block in ast.walk(function)
        if isinstance(block, ast.Try)
        for statement in block.body
        for child in ast.walk(statement)
    }
    installs = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_emit_mode" for t in node.targets)
        # The install is the one that switches the policy on; the restore in
        # the finally block assigns "print" and must stay outside.
        and isinstance(node.value, ast.Constant)
        and node.value.value == "collect"
    ]
    starts = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "start"
    ]
    assert installs, "_emit_mode must still be installed in _translate_pending"
    assert starts, "the display must still be started there"
    assert all(id(node) in protected_ids for node in installs + starts), (
        "the collect policy and the display start must live inside the try "
        "that restores the policy"
    )


def test_a_failure_reported_after_the_drain_still_reaches_the_terminal(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A worker failing after the drain still shows its line.

    Review R-05 (second half, found by the third review round).  The main
    thread drains the collector while workers may still be running, then
    restores the serial policy.  Anything arriving afterwards used to be
    queued into a queue nobody would read again, i.e. lost silently.  The
    policy is now restored *before* the drain, so such a message writes
    itself.

    The late report is simulated at the exact seam -- right after the real
    drain call -- so the assertion is about terminal visibility rather than
    about the container's API.
    """
    real_drain = getattr(wiki, "_drain_collected_failures")

    def drain_then_report() -> list[str]:
        messages = real_drain()
        getattr(wiki, "_emit_translate_failure")("late failure line")
        return messages

    def succeeding(text: str, translate_cmd: str) -> str | None:
        del text, translate_cmd
        return "# en\n"

    monkeypatch.setattr(wiki, "_drain_collected_failures", drain_then_report)
    monkeypatch.setattr(wiki, "translate_via_cmd", succeeding)
    assert wiki.run(tmp_path / "wiki", "fake-cmd", repo_root=repo, jobs=1) == 0
    assert "late failure line" in capsys.readouterr().err
    # Nothing is left behind for a reader that will never come.
    assert getattr(wiki, "_COLLECTED_FAILURES").qsize() == 0
    assert getattr(wiki, "_emit_mode") == "print"
