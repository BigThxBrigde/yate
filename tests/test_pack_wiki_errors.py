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
import hashlib
import io
import subprocess
import sys
import threading
import time
import types
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


def _fake_subprocess(popen: Callable[..., object]) -> object:
    """Return a stand-in for the :mod:`subprocess` module with *popen*.

    ``wiki`` reaches ``subprocess`` through its module global, so the tests
    replace that name instead of patching attributes on the real module:
    patching ``subprocess.Popen`` would swap the constructor for the whole
    process -- pytest's own helpers, coverage and every other library in
    the run would then get the fake, which is how an earlier draft of these
    tests made a ``KeyboardInterrupt`` escape from an unrelated place.

    ``run`` and the exception/result types stay the real ones so git calls
    and the timeout branch keep working unchanged.
    """
    return types.SimpleNamespace(
        Popen=popen,
        run=subprocess.run,
        TimeoutExpired=subprocess.TimeoutExpired,
        CompletedProcess=subprocess.CompletedProcess,
        DEVNULL=subprocess.DEVNULL,
        PIPE=subprocess.PIPE,
    )


class _FakeProc:
    """Stand-in for :class:`subprocess.Popen` as used by ``_run_translate``.

    The translator is launched through ``Popen`` + a polling ``communicate``
    so that a run being torn down can kill its child (review R-15); these
    tests therefore stub the process, not ``subprocess.run``.
    """

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        *,
        hang: bool = False,
    ) -> None:
        self.returncode = returncode
        self.killed = False
        self._result = (stdout, stderr)
        self._hang = hang
        self.stdin = io.StringIO()

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        """Return the captured output, or keep hanging like a stuck child."""
        del timeout
        if self._hang:
            raise subprocess.TimeoutExpired(cmd="fake-cmd", timeout=0)
        return self._result

    def kill(self) -> None:
        """Record that the child was terminated."""
        self.killed = True

    def wait(self) -> int:
        """Return the exit code, as a reaped child would."""
        return self.returncode


def test_translate_via_cmd_failure_reports_wiki_0201_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A non-zero translator exit is reported as ``error[WIKI-0201]``."""

    def failing_popen(cmd: object, **kwargs: object) -> _FakeProc:
        del cmd, kwargs
        return _FakeProc(3, "", "kaput")

    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(failing_popen))
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    err = capsys.readouterr().err
    assert "error[WIKI-0201]: translate-cmd failed (rc=3): kaput" in err
    assert _TRACEBACK_HEAD not in err


def test_translate_via_cmd_timeout_reports_wiki_0202_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A translator that exceeds its budget is reported as ``WIKI-0202``."""
    monkeypatch.setattr(wiki, "TRANSLATE_TIMEOUT_S", 0.0)

    def hanging_popen(cmd: object, **kwargs: object) -> _FakeProc:
        del cmd, kwargs
        return _FakeProc(hang=True)

    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(hanging_popen))
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    err = capsys.readouterr().err
    assert "error[WIKI-0202]: translate-cmd timed out after 0s" in err
    assert _TRACEBACK_HEAD not in err


def _own_stop_signal(stop: threading.Event | None) -> None:
    """Attach *stop* to this thread as the translation stage that owns it.

    A stage publishes its cancel signal on the thread that runs its batch
    (see ``wiki._run_batch``), so a test standing in for a worker has to
    publish one too; ``None`` detaches it again.  ``getattr`` keeps the
    private name out of pyright's private-usage check, the same way the
    string-keyed patching above does.
    """
    getattr(wiki, "_stage_local").stop = stop


def test_a_page_larger_than_the_pipe_buffer_reaches_the_child_intact() -> None:
    """A page bigger than the pipe buffer round-trips through a real child.

    Review R-29: the page used to be written in full before the answer was
    read, so a hook that answers before draining stdin deadlocked at 64 KB in
    and 64 KB out -- and the repository's largest page is 72 KB.  The writer
    now runs alongside the reads, and the child echoes the *hash* of what it
    decoded: a prefix assertion would also accept an empty page, which is how
    an unverified writer thread survived the last round.
    """
    chunk = "中文正文 line that makes the page comfortably large\n"
    page = "# 大页\n\n" + chunk * 4096
    assert len(page.encode("utf-8")) > 128 * 1024
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
    # The hook is a stand-in for a translator: it decodes stdin as UTF-8 and
    # lets universal newlines undo the CRLF the text-mode pipe writes.
    script = (
        "import hashlib, sys;"
        " sys.stdin.reconfigure(encoding='utf-8');"
        " data = sys.stdin.read();"
        " sys.stdout.write(str(len(data)) + ' ' +"
        " hashlib.sha256(data.encode('utf-8')).hexdigest())"
    )
    command = subprocess.list2cmdline([sys.executable, "-c", script])
    result = wiki.translate_via_cmd(page, command)
    assert result == f"{len(page)} {digest}"


def test_a_streaming_hook_that_answers_before_reading_everything() -> None:
    """A hook that writes while it is being fed must not deadlock either.

    The shape that used to break: the child emits a big answer before it
    consumes the rest of stdin, so both pipes fill at once.  64 KB in and
    64 KB out reproduce it.
    """
    chunk = "x" * 1024
    page = chunk * 64
    script = (
        "import sys;"
        " sys.stdout.write('y' * 65536);"
        " sys.stdout.flush();"
        " sys.stdin.read()"
    )
    command = subprocess.list2cmdline([sys.executable, "-c", script])
    result = wiki.translate_via_cmd(page, command)
    assert result == "y" * 65536


def test_a_hook_that_exits_early_is_reported_not_raised(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A child dying mid-write degrades to a page failure, not a traceback.

    Review R-29: a page larger than the pipe buffer runs into a hook that has
    already exited, and the resulting :class:`BrokenPipeError` must not escape
    ``run()`` -- that would break the "one bad page never aborts the run"
    contract.  The page is 192 KB, so the writer really is mid-stream when
    the child goes away.
    """
    page = "中文" * 32768
    script = "import sys; sys.exit(3)"
    command = subprocess.list2cmdline([sys.executable, "-c", script])
    assert wiki.translate_via_cmd(page, command) is None
    err = capsys.readouterr().err
    assert f"error[{Code.WIKI_TRANSLATE_FAILED}]" in err
    assert "BrokenPipe" not in err
    assert _TRACEBACK_HEAD not in err


def test_an_unstartable_shell_is_reported_as_wiki_0201(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A shell that cannot start at all is a page failure, not a traceback.

    Reachable when the shell itself is missing (``shell=True``), which no
    other case covers -- a missing *command* comes back as a non-zero exit
    code instead.
    """

    def no_shell(cmd: object, **kwargs: object) -> object:
        del cmd, kwargs
        raise OSError(2, "The system cannot find the file specified")

    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(no_shell))
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    err = capsys.readouterr().err
    assert "error[WIKI-0201]: cannot start translate-cmd" in err
    assert _TRACEBACK_HEAD not in err


def test_a_torn_down_run_kills_the_child_it_is_waiting_for(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A translator still running when the stage tears down is terminated.

    Review R-15: the delay between "interrupted" and the process actually
    exiting used to be one full page per running worker, because the main
    thread could only stop waiting -- CPython joins the pool at teardown and
    the child kept going.  The stage now raises the stop signal, and a
    translator blocked in its polling loop kills its own child.
    """
    monkeypatch.setattr(wiki, "TRANSLATE_TIMEOUT_S", 900.0)
    monkeypatch.setattr(wiki, "_STOP_POLL_S", 0.01)
    # Stand in for the stage: it owns this translation, so it publishes the
    # signal to the thread that runs it.
    stage_stop = threading.Event()
    _own_stop_signal(stage_stop)
    proc = _FakeProc(hang=True)
    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(lambda *a, **k: proc))

    def tear_down() -> None:
        # Stand in for the stage's finally: the stop signal arrives while
        # the fake child is still "running".
        time.sleep(0.05)
        stage_stop.set()

    threading.Thread(target=tear_down, daemon=True).start()
    try:
        with pytest.raises(KeyboardInterrupt):
            wiki.translate_via_cmd("# zh in\n", "fake-cmd")
    finally:
        _own_stop_signal(None)
    assert proc.killed
    assert "error[" not in capsys.readouterr().err


def test_a_direct_call_ignores_another_stage_stop_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A signal published by another thread cannot cancel this call.

    Review R-28: the stop check used to be ANDed with the collect policy,
    which the stage restores on its way out -- a worker that polled after
    that point never saw the signal and its child ran to completion.  The
    signal now belongs to the stage that owns *this* thread, so the leftover
    of a foreign stage has to stay invisible and the call must end on its
    own timeout.
    """
    monkeypatch.setattr(wiki, "_STOP_POLL_S", 0.01)
    # The collect policy is what a running stage installs; it must not be
    # what makes a call cancellable.
    monkeypatch.setattr(wiki, "_emit_mode", "collect")
    stale = threading.Event()
    stale.set()
    other_stage = threading.Thread(target=_own_stop_signal, args=(stale,), daemon=True)
    other_stage.start()
    other_stage.join()
    proc = _FakeProc(hang=True)
    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(lambda *a, **k: proc))
    monkeypatch.setattr(wiki, "TRANSLATE_TIMEOUT_S", 0.1)
    assert wiki.translate_via_cmd("# zh in\n", "fake-cmd") is None
    assert proc.killed


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

    def interrupted_popen(cmd: object, **kwargs: object) -> _FakeProc:
        del cmd, kwargs
        return _FakeProc(returncode, "", traceback)

    monkeypatch.setattr(wiki, "subprocess", _fake_subprocess(interrupted_popen))
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
