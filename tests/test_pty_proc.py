"""Tests for the pseudo terminal process wrapper.

Two layers are exercised here:

* the :class:`PtyProcess` facade, against a configurable stub backend, so its
  defensive branches (a dead PTY, a failing backend call, a torn-down loop)
  are covered deterministically;
* the real platform backends (``_UnixPty`` on POSIX, ``_ConPty`` on Windows),
  driven by a short-lived ``sys.executable -c`` child -- no shell, no external
  program, so both CI legs run the same scenarios.

Platform specific branches keep their assertions behind a guard: whatever the
local platform cannot reach (the POSIX half on Windows, and vice versa) is
covered by the other CI leg, never deleted to make a local run green.

Windows note: a ConPTY child receives the pseudoconsole's handles only when it
has nothing else to inherit.  A child spawned from a real console inherits
console handles, which the console subsystem swaps for the pseudoconsole's; a
child spawned with a *redirected* stdout (pytest capture, ``> log.txt``)
inherits that pipe instead and its output bypasses the panel.  The output-flow
tests therefore drop our standard handles for the duration of the spawn, which
reproduces the console case.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from collections.abc import Callable, Generator

import pytest

from yate.editor_term import PtyProcess, PtyProcessError
from yate.editor_term import pty_proc

#: Seconds a real child gets to produce output / exit before a test fails.
REAL_PTY_TIMEOUT = 20.0


def _child(code: str) -> list[str]:
    """Return an argv running *code* in this very interpreter."""
    return [sys.executable, "-c", code]


def _backend_name() -> str:
    """Attribute name of the platform backend inside :mod:`pty_proc`."""
    return "_ConPty" if os.name == "nt" else "_UnixPty"


async def _wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    """Poll *predicate* until it holds; ``False`` on timeout, never raising."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return predicate()


@contextlib.contextmanager
def _no_inherited_std_handles() -> Generator[None]:
    """Hide our standard handles while a ConPTY child is being created.

    No-op on POSIX (the child always gets the slave PTY).  On Windows this is
    what a console parent effectively looks like to the child: with nothing
    console-less to inherit, the pseudoconsole hands out its own handles.
    """
    if os.name != "nt":
        yield
        return
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.GetStdHandle.argtypes = [ctypes.c_uint32]
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.SetStdHandle.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    kernel32.SetStdHandle.restype = ctypes.c_int
    slots = (0xFFFFFFF6, 0xFFFFFFF5, 0xFFFFFFF4)  # input, output, error
    saved = [kernel32.GetStdHandle(slot) for slot in slots]
    try:
        for slot in slots:
            kernel32.SetStdHandle(slot, None)
        yield
    finally:
        for slot, handle in zip(slots, saved):
            kernel32.SetStdHandle(slot, handle)


# --- stub backend -----------------------------------------------------------


class _StubImpl:
    """Configurable stand-in for a platform PTY backend.

    The facade builds its backend inside ``PtyProcess.__init__``, so the knobs
    live on the class and the fixture resets them before each test.
    """

    instances: list[_StubImpl] = []
    spawn_error: BaseException | None = None
    write_error: BaseException | None = None
    resize_error: BaseException | None = None
    terminate_error: BaseException | None = None
    close_error: BaseException | None = None

    def __init__(self, owner: PtyProcess) -> None:
        self.owner = owner
        self.spawned = False
        self.closed = False
        self.sent: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self.terminated = False
        _StubImpl.instances.append(self)

    def spawn(self) -> None:
        if self.spawn_error is not None:
            raise self.spawn_error
        self.spawned = True

    def read_loop(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.sent.append(data)

    def resize(self, cols: int, rows: int) -> None:
        if self.resize_error is not None:
            raise self.resize_error
        self.resizes.append((cols, rows))

    def terminate(self) -> None:
        if self.terminate_error is not None:
            raise self.terminate_error
        self.terminated = True

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


@pytest.fixture
def stub_pty(monkeypatch: pytest.MonkeyPatch) -> type[_StubImpl]:
    """Swap in the stub backend and reset both its log and its knobs."""
    _StubImpl.instances = []
    _StubImpl.spawn_error = None
    _StubImpl.write_error = None
    _StubImpl.resize_error = None
    _StubImpl.terminate_error = None
    _StubImpl.close_error = None
    monkeypatch.setattr(pty_proc, _backend_name(), _StubImpl)
    return _StubImpl


def _stub_process(
    stub_pty: type[_StubImpl], argv: list[str] | None = None
) -> tuple[PtyProcess, _StubImpl]:
    """Build a facade over the stub backend and return both halves."""
    proc = PtyProcess(argv if argv is not None else ["shell"], Path.cwd(), 80, 24)
    return proc, stub_pty.instances[0]


def test_empty_argv_is_rejected_before_touching_the_backend() -> None:
    """A command with no words fails fast, without creating a backend."""
    with pytest.raises(PtyProcessError):
        PtyProcess([], Path.cwd(), 80, 24)


def test_cols_and_rows_are_clamped_to_at_least_one() -> None:
    """A zero-sized terminal is normalised, so the backend never sees it."""
    proc = PtyProcess(["shell"], Path.cwd(), 0, -3)
    assert (proc.cols, proc.rows) == (1, 1)


def test_wait_closed_before_start_returns_none(stub_pty: type[_StubImpl]) -> None:
    """Nothing was started, so there is no exit code to await."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        assert await proc.wait_closed() is None

    asyncio.run(_scenario())


def test_start_spawns_through_a_thread_and_reports_exit(
    stub_pty: type[_StubImpl],
) -> None:
    """The happy path: spawn, then a backend-reported exit settles the future."""

    async def _scenario() -> None:
        exits: list[int | None] = []
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, exits.append)
        assert impl.spawned
        impl.owner.process_finished(5)
        assert await asyncio.wait_for(proc.wait_closed(), 3) == 5
        assert exits == [5]

    asyncio.run(_scenario())


def test_failed_spawn_still_settles_the_exit_future(
    stub_pty: type[_StubImpl],
) -> None:
    """A backend that cannot spawn must not leave shutdown waiting forever."""

    async def _scenario() -> None:
        stub_pty.spawn_error = PtyProcessError("no ConPTY here")
        proc, _impl = _stub_process(stub_pty)
        with pytest.raises(PtyProcessError):
            await proc.start(lambda _data: None, lambda _code: None)
        assert proc.is_closing
        assert await asyncio.wait_for(proc.wait_closed(), 3) is None

    asyncio.run(_scenario())


def test_write_ignores_empty_data_and_a_closing_process(
    stub_pty: type[_StubImpl],
) -> None:
    """Nothing is pushed to a PTY that is closing, and empty writes are free."""

    async def _scenario() -> None:
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        proc.write(b"")
        proc.terminate()
        proc.write(b"ls\r")
        assert impl.sent == []
        assert impl.terminated

    asyncio.run(_scenario())


def test_write_swallows_a_backend_oserror(stub_pty: type[_StubImpl]) -> None:
    """A PTY that went away between two keystrokes must not raise at the UI."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        stub_pty.write_error = OSError("handle closed")
        proc.write(b"x")  # must not raise

    asyncio.run(_scenario())


def test_resize_skips_the_backend_when_the_size_is_unchanged(
    stub_pty: type[_StubImpl],
) -> None:
    """A redundant resize costs nothing and never reaches the PTY."""

    async def _scenario() -> None:
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        proc.resize(80, 24)
        assert impl.resizes == []
        proc.resize(81, 24)
        assert impl.resizes == [(81, 24)]

    asyncio.run(_scenario())


@pytest.mark.parametrize(
    "error",
    [OSError("bad handle"), PtyProcessError("ResizePseudoConsole failed")],
    ids=["oserror", "pty-error"],
)
def test_resize_swallows_backend_failures(
    stub_pty: type[_StubImpl], error: Exception
) -> None:
    """Neither a syscall error nor a refused HRESULT may break the UI."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        stub_pty.resize_error = error
        proc.resize(120, 40)  # must not raise
        assert (proc.cols, proc.rows) == (120, 40)

    asyncio.run(_scenario())


def test_resize_clamps_its_arguments(stub_pty: type[_StubImpl]) -> None:
    """A degenerate size is normalised before it reaches the backend."""

    async def _scenario() -> None:
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        proc.resize(0, -9)
        assert impl.resizes == [(1, 1)]

    asyncio.run(_scenario())


def test_terminate_is_idempotent(stub_pty: type[_StubImpl]) -> None:
    """The second terminate is a no-op, so teardown can be called twice."""

    async def _scenario() -> None:
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        proc.terminate()
        assert impl.terminated
        impl.terminated = False
        proc.terminate()
        assert not impl.terminated

    asyncio.run(_scenario())


def test_terminate_swallows_a_backend_oserror(stub_pty: type[_StubImpl]) -> None:
    """A child that is already gone must not raise on the way out."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        stub_pty.terminate_error = OSError("no such process")
        proc.terminate()  # must not raise
        assert proc.is_closing

    asyncio.run(_scenario())


def test_backend_close_failure_does_not_block_the_exit_report(
    stub_pty: type[_StubImpl],
) -> None:
    """Failing to release PTY handles still has to report the exit code."""

    async def _scenario() -> None:
        exits: list[int | None] = []
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, exits.append)
        stub_pty.close_error = OSError("close failed")
        impl.owner.process_finished(3)
        assert await asyncio.wait_for(proc.wait_closed(), 3) == 3
        assert exits == [3]

    asyncio.run(_scenario())


def test_output_without_a_loop_or_callback_is_dropped(
    stub_pty: type[_StubImpl],
) -> None:
    """A chunk arriving before start() (or after detach) is simply discarded."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        proc.emit_output(b"early\r\n")
        await proc.start(lambda _data: None, lambda _code: None)
        cast(Any, proc)._on_output = None
        proc.emit_output(b"dropped\r\n")
        cast(Any, proc)._on_exit = None
        cast(Any, proc)._exit_future = None
        proc.process_finished(1)  # no callback and no future to settle
        cast(Any, proc)._loop = None
        proc.process_finished(1)  # and then nowhere to report it at all
        assert not cast(Any, proc)._detached

    asyncio.run(_scenario())


def test_output_is_dropped_once_the_loop_is_closed(
    stub_pty: type[_StubImpl],
) -> None:
    """A reader thread outliving the loop must not schedule into it."""

    async def _scenario() -> None:
        chunks: list[bytes] = []
        proc, _impl = _stub_process(stub_pty)
        await proc.start(chunks.append, lambda _code: None)
        closed = asyncio.new_event_loop()
        closed.close()
        cast(Any, proc)._loop = closed
        proc.emit_output(b"late\r\n")
        await asyncio.sleep(0.05)
        assert chunks == []

    asyncio.run(_scenario())


class _RefusingLoop:
    """A loop that is open but refuses to schedule (as during shutdown)."""

    def is_closed(self) -> bool:
        return False

    def call_soon_threadsafe(
        self, callback: Callable[..., Any], *args: Any
    ) -> None:
        raise RuntimeError("event loop is closed")


def test_output_survives_a_loop_refusing_to_schedule(
    stub_pty: type[_StubImpl],
) -> None:
    """``call_soon_threadsafe`` may raise RuntimeError on a stopping loop."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        cast(Any, proc)._loop = _RefusingLoop()
        proc.emit_output(b"boom\r\n")  # must not raise
        proc.process_finished(2)  # must not raise either
        assert cast(Any, proc)._detached is False

    asyncio.run(_scenario())


def test_a_raising_ui_callback_is_contained(stub_pty: type[_StubImpl]) -> None:
    """A torn-down widget must not take the PTY teardown down with it."""

    async def _scenario() -> None:
        def _explode(_code: int | None) -> None:
            raise ValueError("widget is gone")

        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, _explode)
        impl.owner.process_finished(0)
        assert await asyncio.wait_for(proc.wait_closed(), 3) == 0

    asyncio.run(_scenario())


def test_a_racy_exit_future_is_tolerated(stub_pty: type[_StubImpl]) -> None:
    """The exit future may settle between the check and the set_result."""

    class _RacyFuture:
        def done(self) -> bool:
            return False

        def set_result(self, value: int | None) -> None:
            raise asyncio.InvalidStateError(str(value))

    async def _scenario() -> None:
        exits: list[int | None] = []
        proc, impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, exits.append)
        loop = asyncio.get_running_loop()
        logged: list[dict[str, Any]] = []
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, ctx: logged.append(ctx))
        cast(Any, proc)._exit_future = _RacyFuture()
        impl.owner.process_finished(4)
        assert await _wait_for(lambda: exits == [4])
        await asyncio.sleep(0.05)
        loop.set_exception_handler(previous)
        assert logged == []

    asyncio.run(_scenario())


def test_mark_closing_and_detach_drive_the_public_flags(
    stub_pty: type[_StubImpl],
) -> None:
    """``is_closing`` / ``detach`` are the teardown hooks the owner waits on."""

    async def _scenario() -> None:
        proc, _impl = _stub_process(stub_pty)
        await proc.start(lambda _data: None, lambda _code: None)
        assert not proc.is_closing
        proc.mark_closing()
        assert proc.is_closing
        proc.detach()
        proc.emit_output(b"never\r\n")
        proc.process_finished(11)

    asyncio.run(_scenario())


# --- real backends: end to end ---------------------------------------------


def test_real_pty_streams_child_output_and_reports_its_exit_code() -> None:
    """The platform backend really spawns a child, reads it and reports exit."""

    async def _scenario() -> None:
        chunks: list[bytes] = []
        exits: list[int | None] = []
        proc = PtyProcess(_child("print('pty-ping')"), Path.cwd(), 80, 24)
        with _no_inherited_std_handles():
            await proc.start(chunks.append, exits.append)
        assert await _wait_for(lambda: b"pty-ping" in b"".join(chunks))
        assert await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT) == 0
        assert exits == [0]

    asyncio.run(_scenario())


def test_real_pty_delivers_typed_input_to_the_child() -> None:
    """Keystrokes written to the PTY come back out of the child's stdin."""

    async def _scenario() -> None:
        chunks: list[bytes] = []
        proc = PtyProcess(
            _child(
                "import sys\n"
                "print('pty-ready', flush=True)\n"
                "for line in sys.stdin:\n"
                "    print('pty-got:' + line.strip(), flush=True)\n"
            ),
            Path.cwd(),
            80,
            24,
        )
        with _no_inherited_std_handles():
            await proc.start(chunks.append, lambda _code: None)
        assert await _wait_for(lambda: b"pty-ready" in b"".join(chunks))
        proc.write(b"hello\r")
        assert await _wait_for(lambda: b"pty-got:hello" in b"".join(chunks))
        proc.terminate()
        await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT)

    asyncio.run(_scenario())


def test_real_pty_resize_keeps_the_child_running() -> None:
    """Resizing a live PTY reaches the backend and leaves the child healthy."""

    async def _scenario() -> None:
        chunks: list[bytes] = []
        proc = PtyProcess(
            _child("print('pty-ready', flush=True)\nimport time\ntime.sleep(30)\n"),
            Path.cwd(),
            80,
            24,
        )
        with _no_inherited_std_handles():
            await proc.start(chunks.append, lambda _code: None)
        assert await _wait_for(lambda: b"pty-ready" in b"".join(chunks))
        proc.resize(100, 30)
        proc.resize(100, 30)  # unchanged: skipped by the facade
        assert (proc.cols, proc.rows) == (100, 30)
        proc.terminate()
        code = await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT)
        assert code is not None and code != 0

    asyncio.run(_scenario())


def test_real_pty_terminate_stops_a_sleeping_child() -> None:
    """Terminating the PTY really kills the child and settles the exit."""

    async def _scenario() -> None:
        exits: list[int | None] = []
        proc = PtyProcess(
            _child("print('pty-ready', flush=True)\nimport time\ntime.sleep(30)\n"),
            Path.cwd(),
            80,
            24,
        )
        await proc.start(lambda _data: None, exits.append)
        await asyncio.sleep(0.2)
        proc.terminate()
        code = await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT)
        assert code is not None and code != 0
        assert exits == [code]

    asyncio.run(_scenario())


def test_real_pty_reports_a_missing_executable(tmp_path: Path) -> None:
    """A child that cannot be started raises instead of hanging the shell."""

    async def _scenario() -> None:
        missing = tmp_path / "definitely-not-here"
        proc = PtyProcess([str(missing)], tmp_path, 80, 24)
        with pytest.raises(PtyProcessError):
            await proc.start(lambda _data: None, lambda _code: None)
        assert proc.is_closing
        assert await asyncio.wait_for(proc.wait_closed(), 3) is None

    asyncio.run(_scenario())


def test_real_pty_write_after_exit_is_a_noop() -> None:
    """Writing into a finished session must not raise at the caller."""

    async def _scenario() -> None:
        proc = PtyProcess(_child("print('pty-bye')"), Path.cwd(), 80, 24)
        await proc.start(lambda _data: None, lambda _code: None)
        await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT)
        proc.write(b"late\r")  # must not raise
        proc.resize(90, 20)  # must not raise either

    asyncio.run(_scenario())


# --- Windows backend internals ---------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
def test_conpty_check_hr_accepts_success_and_rejects_failure() -> None:
    """The HRESULT guard passes 0 and raises with the code for a failure."""
    cls = getattr(pty_proc, "_ConPty")
    impl = cls.__new__(cls)
    impl._check_hr(0, "CreatePipe")
    with pytest.raises(PtyProcessError) as caught:
        impl._check_hr(-2147467259, "ResizePseudoConsole")  # 0x80004005
    assert "ResizePseudoConsole" in str(caught.value)
    assert "0x80004005" in str(caught.value)


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
def test_conpty_operations_without_a_spawned_child_are_safe() -> None:
    """Before spawn (or after close) every handle is None and calls no-op."""

    async def _scenario() -> None:
        proc = PtyProcess(["cmd"], Path.cwd(), 80, 24)
        impl = cast(Any, proc)._impl
        impl.read_loop()  # no process info: no watcher, exit code is None
        impl._watch_exit()  # ditto: nothing to wait for
        assert impl._exit_code() is None
        impl.write(b"x")  # no input pipe yet
        impl.resize(90, 20)  # no pseudo console yet
        impl._close_pty()
        impl._close_pty()  # idempotent
        impl.close()
        impl.terminate()  # no process info: nothing to kill

    asyncio.run(_scenario())


def _conpty_exit_query_impl(hprocess: int) -> Any:
    """Return a real ``_ConPty`` whose exit query sees *hprocess*.

    Only the attributes the exit-code query touches are wired up: the
    kernel32 table is the real one loaded by ``PtyProcess.__init__`` and
    the process-info record carries the caller's handle.
    """
    proc = PtyProcess(["cmd"], Path.cwd(), 80, 24)
    impl = cast(Any, proc)._impl
    impl._proc_info = SimpleNamespace(hProcess=hprocess)
    return impl


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
def test_conpty_exit_query_reports_running_for_a_live_child() -> None:
    """A child that is still alive reports ``running``, not a code."""
    child = subprocess.Popen(_child("import time; time.sleep(30)"))
    impl = _conpty_exit_query_impl(cast(Any, child)._handle)

    def _skip_wait(*_args: Any) -> int:
        return 258  # WAIT_TIMEOUT: treat the bounded liveness wait as done

    impl._kernel32["WaitForSingleObject"] = _skip_wait
    try:
        assert impl._exit_code_or_failed() == "running"
        assert impl._exit_code() is None  # the compatibility wrapper
    finally:
        child.kill()
        child.wait(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
def test_conpty_exit_query_reports_the_code_after_the_child_is_gone() -> None:
    """A finished child yields its real exit code through both methods."""
    child = subprocess.Popen(_child("import sys; sys.exit(7)"))
    impl = _conpty_exit_query_impl(cast(Any, child)._handle)
    assert child.wait(timeout=10) == 7
    assert impl._exit_code_or_failed() == 7
    assert impl._exit_code() == 7


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
def test_conpty_exit_query_reports_failed_for_an_unusable_handle() -> None:
    """A bogus handle fails both API calls and collapses to ``failed``."""
    # 0xDEADBEEF is outside the handle table (note: -1 would be the valid
    # current-process pseudo-handle, so it must not be used here).
    impl = _conpty_exit_query_impl(0xDEADBEEF)
    assert impl._exit_code_or_failed() == "failed"
    assert impl._exit_code() is None


class _FakeKernel32:
    """Scripted kernel32 stand-in, used to walk the ConPTY error paths."""

    def __init__(self, **results: object) -> None:
        self.calls: list[str] = []
        self._results: dict[str, object] = results

    def __getitem__(self, name: str) -> Callable[..., Any]:
        def _call(*_args: Any) -> Any:
            self.calls.append(name)
            result = self._results.get(name, True)
            if isinstance(result, list):
                return cast(list[Any], result).pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        return _call


@pytest.mark.skipif(os.name != "nt", reason="ConPTY backend")
@pytest.mark.parametrize(
    "results, expected",
    [
        ({"CreatePipe": [False]}, PtyProcessError),
        ({"CreatePipe": [True, False]}, PtyProcessError),
        ({"CreatePseudoConsole": -2147467259}, PtyProcessError),
        ({"InitializeProcThreadAttributeList": [True, False]}, PtyProcessError),
        ({"UpdateProcThreadAttribute": False}, PtyProcessError),
        ({"CreateProcessW": False}, PtyProcessError),
        ({"CreateProcessW": OSError("cannot create")}, OSError),
    ],
    ids=[
        "input-pipe",
        "output-pipe",
        "pseudo-console",
        "attribute-list",
        "update-attribute",
        "create-process",
        "create-process-raises",
    ],
)
def test_conpty_setup_failures_raise_and_release_handles(
    tmp_path: Path, results: dict[str, Any], expected: type[BaseException]
) -> None:
    """A failed ConPTY setup step reports it and releases what it opened.

    ``CreateProcessW`` never raises in the real API (it returns FALSE); the
    raising variant proves the cleanup path re-raises as-is instead of
    swallowing the error.
    """

    async def _scenario() -> None:
        proc = PtyProcess(["cmd"], tmp_path, 80, 24)
        impl = cast(Any, proc)._impl
        fake = _FakeKernel32(**results)
        impl._kernel32 = fake
        with pytest.raises(expected):
            impl.spawn()
        assert impl._hpc is None  # the pseudo console never leaks
        assert impl._in_write is None
        assert impl._out_read is None

    asyncio.run(_scenario())


# --- POSIX backend internals -----------------------------------------------


@pytest.mark.skipif(os.name != "posix", reason="POSIX PTY backend")
def test_unix_pty_environment_fills_in_term(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The child environment inherits ours, adds TERM and honours overrides."""
    monkeypatch.delenv("TERM", raising=False)
    plain = PtyProcess(["sh"], tmp_path, 80, 24)
    env = cast(Any, plain)._impl._environment()
    assert env["TERM"] == "xterm-256color"

    monkeypatch.setenv("TERM", "screen")
    custom = PtyProcess(
        ["sh"], tmp_path, 80, 24, env={"YATE_PTY_TEST": "1", "TERM": "dumb"}
    )
    merged = cast(Any, custom)._impl._environment()
    assert merged["TERM"] == "dumb"
    assert merged["YATE_PTY_TEST"] == "1"


@pytest.mark.skipif(os.name != "posix", reason="POSIX PTY backend")
def test_unix_pty_calls_before_spawn_are_safe(tmp_path: Path) -> None:
    """Without a master fd, write and resize do not touch the device."""

    async def _scenario() -> None:
        proc = PtyProcess(["sh"], tmp_path, 80, 24)
        impl = cast(Any, proc)._impl
        impl.write(b"x")
        impl.resize(90, 20)
        impl.close()

    asyncio.run(_scenario())


@pytest.mark.skipif(os.name != "posix", reason="POSIX PTY backend")
def test_unix_pty_escalates_to_sigkill_when_the_child_ignores_sigterm() -> None:
    """A child trapping SIGTERM is still reaped, via the SIGKILL fallback."""

    async def _scenario() -> None:
        proc = PtyProcess(
            _child(
                "import signal, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "print('pty-ready', flush=True)\n"
                "time.sleep(60)\n"
            ),
            Path.cwd(),
            80,
            24,
        )
        chunks: list[bytes] = []
        await proc.start(chunks.append, lambda _code: None)
        assert await _wait_for(lambda: b"pty-ready" in b"".join(chunks))
        proc.terminate()
        code = await asyncio.wait_for(proc.wait_closed(), REAL_PTY_TIMEOUT)
        assert code is not None and code < 0

    asyncio.run(_scenario())
