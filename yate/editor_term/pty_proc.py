"""Cross-platform pseudo terminal process management (no third-party deps).

* POSIX: the stdlib :mod:`pty` module plus a dedicated reader thread;
* Windows: the ConPTY API (Windows 10 1809+) driven through :mod:`ctypes`.

Both implementations share :class:`PtyProcess`: PTY bytes are delivered to an
``on_output`` callback and process termination to ``on_exit``, always on the
asyncio loop that called :meth:`start`, so UI code never crosses threads.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from yate.logs import tracing

#: Trace logger ("yate.editor_term.pty_proc"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

OutputFn = Callable[[bytes], None]
ExitFn = Callable[[Optional[int]], None]


class PtyProcessError(RuntimeError):
    """The PTY could not be created or the child process could not start."""


class PtyProcess:
    """A child process attached to a pseudo terminal."""

    def __init__(
        self,
        argv: list[str],
        cwd: Path,
        cols: int,
        rows: int,
        env: Optional[dict[str, str]] = None,
    ) -> None:
        if not argv:
            raise PtyProcessError("empty shell command")
        self.argv = list(argv)
        self.cwd = cwd
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.env = env
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_output: Optional[OutputFn] = None
        self._on_exit: Optional[ExitFn] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._closing = False
        self._detached = False
        self._exit_future: Optional[asyncio.Future[Optional[int]]] = None
        self._impl = _UnixPty(self) if os.name == "posix" else _ConPty(self)

    # ------------------------------------------------------------- lifecycle

    async def start(self, on_output: OutputFn, on_exit: ExitFn) -> None:
        """Spawn the process and start pumping PTY output.

        A spawn that fails (no ConPTY support, no PTY device, ...) leaves no
        reader thread behind, so the exit future is settled here: otherwise
        nobody would ever report the exit and :meth:`wait_closed` -- awaited by
        the application's shutdown -- would block for good.
        """
        self._loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[int]] = self._loop.create_future()
        self._exit_future = future
        self._on_output = on_output
        self._on_exit = on_exit
        try:
            await asyncio.to_thread(self._impl.spawn)
        except BaseException:
            self._closing = True
            if not future.done():
                future.set_result(None)
            raise
        self._thread = threading.Thread(
            target=self._impl.read_loop, name="yate-pty", daemon=True
        )
        self._thread.start()

    async def wait_closed(self) -> Optional[int]:
        if self._exit_future is None:
            return None
        return await self._exit_future

    def write(self, data: bytes) -> None:
        """Send keystrokes to the child; never raises on a dead PTY."""
        if not data or self._closing:
            return
        try:
            with self._lock:
                self._impl.write(data)
        except OSError:
            pass

    def resize(self, cols: int, rows: int) -> None:
        cols = max(1, cols)
        rows = max(1, rows)
        if cols == self.cols and rows == self.rows:
            return
        self.cols, self.rows = cols, rows
        try:
            self._impl.resize(cols, rows)
        except (OSError, PtyProcessError):
            pass

    def terminate(self) -> None:
        """Politely kill the child (best effort); reader thread follows."""
        if self._closing:
            return
        self._closing = True
        try:
            self._impl.terminate()
        except OSError:
            pass

    # Called from the reader thread only.
    def _emit(self, data: bytes) -> None:
        if self._detached:
            return
        callback = self._on_output
        loop = self._loop
        if loop is not None and callback is not None:
            self._post(loop, callback, data)

    def _finished(self, code: Optional[int]) -> None:
        try:
            self._impl.close()
        except OSError:
            pass
        if self._detached:
            return
        loop = self._loop
        if loop is None:
            return

        def _done() -> None:
            callback = self._on_exit
            if callback is not None:
                self._safe_call(callback, code)
            future = self._exit_future
            if future is not None and not future.done():
                try:
                    future.set_result(code)
                except asyncio.InvalidStateError:
                    pass

        self._post(loop, _done)

    @staticmethod
    def _safe_call(callback: Callable[..., Any], *args: Any) -> None:
        """Run a UI callback scheduled by a PTY thread without ever letting
        a torn-down widget take the teardown down with it."""
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 - PTY thread must not kill the loop
            log.exception("PTY callback failed")

    @staticmethod
    def _post(loop: asyncio.AbstractEventLoop, *args: Any) -> None:
        """Schedule a callback from a PTY thread; never raise when the app
        event loop is already closed/stopped (the reader thread can briefly
        outlive ``shutdown``, e.g. when ``wait_closed`` is cancelled)."""
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(*args)
        except RuntimeError:
            pass

    # Bridges used by the platform implementation objects.
    def emit_output(self, data: bytes) -> None:
        self._emit(data)

    def process_finished(self, code: Optional[int]) -> None:
        self._finished(code)

    @property
    def is_closing(self) -> bool:
        return self._closing

    def mark_closing(self) -> None:
        self._closing = True

    def detach(self) -> None:
        """Stop bridging PTY thread events to the (disappearing) event loop.

        Called once the owner has given up waiting for a clean exit; after
        this no thread will touch the loop, so a daemon thread outliving the
        app cannot surface ``RuntimeError: Event loop is closed``.
        """
        self._detached = True
        self._on_output = None
        self._on_exit = None


# ===================================================================== POSIX

if os.name == "posix":
    import fcntl  # type: ignore[import-not-found]
    import pty  # type: ignore[import-not-found]
    import signal  # type: ignore[import-not-found]
    import struct  # type: ignore[import-not-found]
    import termios  # type: ignore[import-not-found]

    class _UnixPty:
        def __init__(self, owner: PtyProcess) -> None:
            self._owner = owner
            self._master = -1
            self._proc: Optional[subprocess.Popen[bytes]] = None

        def _environment(self) -> dict[str, str]:
            env = dict(os.environ)
            if self._owner.env:
                env.update(self._owner.env)
            env.setdefault("TERM", "xterm-256color")
            return env

        def spawn(self) -> None:
            master, slave = pty.openpty()
            try:
                self._proc = subprocess.Popen(  # noqa: S603 - argv from config/user
                    self._owner.argv,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    cwd=str(self._owner.cwd),
                    env=self._environment(),
                    start_new_session=True,
                    close_fds=True,
                )
            except (OSError, ValueError) as exc:
                os.close(master)
                os.close(slave)
                raise PtyProcessError(
                    f"cannot start {self._owner.argv[0]!r}: {exc}"
                ) from exc
            os.close(slave)
            self._master = master
            self.resize(self._owner.cols, self._owner.rows)

        def read_loop(self) -> None:
            code: Optional[int] = None
            try:
                while True:
                    try:
                        chunk = os.read(self._master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    self._owner.emit_output(chunk)
            finally:
                proc = self._proc
                if proc is not None:
                    code = proc.wait()
                if self._master >= 0:
                    try:
                        os.close(self._master)
                    except OSError:
                        pass
                    self._master = -1
            self._owner.process_finished(code)

        def write(self, data: bytes) -> None:
            if self._master >= 0:
                os.write(self._master, data)

        def resize(self, cols: int, rows: int) -> None:
            if self._master >= 0:
                size = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._master, termios.TIOCSWINSZ, size)

        def terminate(self) -> None:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                return
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                try:
                    proc.terminate()
                except OSError:
                    pass

            def _kill_later() -> None:
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        pass

            threading.Thread(target=_kill_later, daemon=True).start()

        def close(self) -> None:
            pass


# =================================================================== Windows

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    _PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
    _STILL_ACTIVE = 259

    class _COORD(ctypes.Structure):
        _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class _STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class _STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", _STARTUPINFOW),
            ("lpAttributeList", ctypes.c_void_p),
        ]

    class _PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]


class _ConPty:
    """Windows Console Pseudo Terminal via kernel32."""

    def __init__(self, owner: PtyProcess) -> None:
        self._owner = owner
        self._hpc: Any = None
        self._in_write: Any = None   # our handle to write keystrokes
        self._out_read: Any = None  # our handle to read rendered output
        self._proc_info: Any = None
        self._attr_buffer: Any = None
        self._si_ex: Any = None
        self._hpc_lock = threading.Lock()
        self._kernel32 = self._load_functions()

    def _load_functions(self) -> dict[str, Any]:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]

        k32.CreatePseudoConsole.argtypes = [
            _COORD, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        k32.CreatePseudoConsole.restype = ctypes.c_long
        k32.ResizePseudoConsole.argtypes = [wintypes.HANDLE, _COORD]
        k32.ResizePseudoConsole.restype = ctypes.c_long
        k32.ClosePseudoConsole.argtypes = [wintypes.HANDLE]
        k32.ClosePseudoConsole.restype = None

        k32.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
            ctypes.c_void_p, wintypes.DWORD,
        ]
        k32.CreatePipe.restype = wintypes.BOOL
        k32.InitializeProcThreadAttributeList.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k32.UpdateProcThreadAttribute.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
            ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
        ]
        k32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
            ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
            wintypes.LPCWSTR, ctypes.POINTER(_STARTUPINFOW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ]
        k32.CreateProcessW.restype = wintypes.BOOL
        k32.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        k32.ReadFile.restype = wintypes.BOOL
        k32.WriteFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        k32.WriteFile.restype = wintypes.BOOL
        k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.TerminateProcess.restype = wintypes.BOOL
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)
        ]
        k32.GetExitCodeProcess.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        return {name: getattr(k32, name) for name in (
            "CreatePseudoConsole", "ResizePseudoConsole", "ClosePseudoConsole",
            "CreatePipe", "InitializeProcThreadAttributeList",
            "UpdateProcThreadAttribute", "DeleteProcThreadAttributeList",
            "CreateProcessW", "ReadFile", "WriteFile", "TerminateProcess",
            "WaitForSingleObject", "GetExitCodeProcess", "CloseHandle",
        )}

    def _check_hr(self, hr: int, what: str) -> None:
        if hr & 0x80000000:
            raise PtyProcessError(f"{what} failed: HRESULT 0x{hr & 0xFFFFFFFF:08X}")

    def spawn(self) -> None:
        k = self._kernel32
        in_read, in_write = wintypes.HANDLE(), wintypes.HANDLE()
        out_read, out_write = wintypes.HANDLE(), wintypes.HANDLE()
        if not k["CreatePipe"] (ctypes.byref(in_read), ctypes.byref(in_write), None, 0):
            raise PtyProcessError("CreatePipe (input) failed")
        if not k["CreatePipe"](ctypes.byref(out_read), ctypes.byref(out_write), None, 0):
            raise PtyProcessError("CreatePipe (output) failed")

        size = _COORD(self._owner.cols, self._owner.rows)
        hpc = wintypes.HANDLE()
        hr = k["CreatePseudoConsole"](size, in_read, out_write, 0, ctypes.byref(hpc))
        # The PTY owns these ends now.
        k["CloseHandle"](in_read)
        k["CloseHandle"](out_write)
        if hr & 0x80000000:
            k["CloseHandle"](in_write)
            k["CloseHandle"](out_read)
            self._check_hr(hr, "CreatePseudoConsole")
        self._hpc = hpc
        self._in_write = in_write
        self._out_read = out_read

        attr_size = ctypes.c_size_t(0)
        k["InitializeProcThreadAttributeList"](None, 1, 0, ctypes.byref(attr_size))
        self._attr_buffer = ctypes.create_string_buffer(attr_size.value)
        attr_ptr = ctypes.cast(self._attr_buffer, ctypes.c_void_p)
        try:
            if not k["InitializeProcThreadAttributeList"](
                attr_ptr, 1, 0, ctypes.byref(attr_size)
            ):
                raise PtyProcessError("InitializeProcThreadAttributeList failed")
            if not k["UpdateProcThreadAttribute"](
                attr_ptr, 0, _PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                hpc, ctypes.sizeof(wintypes.HANDLE), None, None
            ):
                raise PtyProcessError(
                    "UpdateProcThreadAttribute (pseudoconsole) failed"
                )

            si_ex = _STARTUPINFOEXW()
            si_ex.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
            si_ex.lpAttributeList = attr_ptr
            self._si_ex = si_ex
            proc_info = _PROCESS_INFORMATION()
            cmdline = subprocess.list2cmdline(self._owner.argv)
            cwd_arg = str(self._owner.cwd) if str(self._owner.cwd) else None
            flags = _EXTENDED_STARTUPINFO_PRESENT
            created = k["CreateProcessW"](
                None, ctypes.create_unicode_buffer(cmdline), None, None, False,
                flags, None, cwd_arg,
                ctypes.byref(si_ex.StartupInfo), ctypes.byref(proc_info),
            )
        except BaseException:
            k["DeleteProcThreadAttributeList"](attr_ptr)
            self._close_pty()
            k["CloseHandle"](in_write)
            k["CloseHandle"](out_read)
            self._in_write = self._out_read = None
            raise
        k["DeleteProcThreadAttributeList"](attr_ptr)
        if not created:
            err = ctypes.get_last_error()  # type: ignore[attr-defined]
            self._close_pty()
            k["CloseHandle"](in_write)
            k["CloseHandle"](out_read)
            self._in_write = self._out_read = None
            raise PtyProcessError(
                f"CreateProcess failed for {self._owner.argv[0]!r}: error {err}"
            )
        self._proc_info = proc_info

    def read_loop(self) -> None:
        k = self._kernel32
        info = self._proc_info
        watcher: Optional[threading.Thread] = None
        if info is not None:
            watcher = threading.Thread(target=self._watch_exit, daemon=True)
            watcher.start()
        buffer = ctypes.create_string_buffer(65536)
        read_bytes = wintypes.DWORD(0)
        try:
            while not self._owner.is_closing:
                ok = k["ReadFile"](
                    self._out_read, buffer, ctypes.sizeof(buffer),
                    ctypes.byref(read_bytes), None,
                )
                count = read_bytes.value
                if count:
                    self._owner.emit_output(buffer.raw[:count])
                if not ok or count == 0:
                    break
        finally:
            code = self._exit_code()
        if watcher is not None:
            watcher.join(timeout=3)
        self._owner.process_finished(code)

    def _watch_exit(self) -> None:
        """ConPTY output pipes do not EOF when the child exits; break the
        pending ReadFile by closing the pseudo console once the process dies."""
        k = self._kernel32
        info = self._proc_info
        if info is None:
            return
        k["WaitForSingleObject"](info.hProcess, 0xFFFFFFFF)
        self._owner.mark_closing()
        # Give the reader a moment to flush the final repaint.
        threading.Event().wait(0.2)
        self._close_pty()

    def _close_pty(self) -> None:
        with self._hpc_lock:
            if self._hpc is not None:
                self._kernel32["ClosePseudoConsole"](self._hpc)
                self._hpc = None

    def _exit_code(self) -> Optional[int]:
        k = self._kernel32
        info = self._proc_info
        if info is None:
            return None
        k["WaitForSingleObject"](info.hProcess, 5000)
        code = wintypes.DWORD(0)
        if k["GetExitCodeProcess"](info.hProcess, ctypes.byref(code)):
            return None if code.value == _STILL_ACTIVE else int(code.value)
        return None

    def write(self, data: bytes) -> None:
        if self._in_write is None:
            return
        written = wintypes.DWORD(0)
        self._kernel32["WriteFile"](
            self._in_write, data, len(data), ctypes.byref(written), None
        )

    def resize(self, cols: int, rows: int) -> None:
        if self._hpc is not None:
            hr = self._kernel32["ResizePseudoConsole"](
                self._hpc, _COORD(cols, rows)
            )
            self._check_hr(hr, "ResizePseudoConsole")

    def terminate(self) -> None:
        k = self._kernel32
        info = self._proc_info
        if info is not None:
            k["TerminateProcess"](info.hProcess, 1)
            k["WaitForSingleObject"](info.hProcess, 2000)
        self._close_pty()

    def close(self) -> None:
        k = self._kernel32
        self._close_pty()
        info = self._proc_info
        if info is not None:
            k["CloseHandle"](info.hThread)
            k["CloseHandle"](info.hProcess)
            self._proc_info = None
        if self._in_write is not None:
            k["CloseHandle"](self._in_write)
            self._in_write = None
        if self._out_read is not None:
            k["CloseHandle"](self._out_read)
            self._out_read = None


# Platform-specific placeholder types for static analysis.
if os.name != "posix":
    class _UnixPty:  # pragma: no cover - never instantiated on Windows
        def __init__(self, owner: PtyProcess) -> None:
            raise PtyProcessError("PTY support requires a POSIX platform")

if os.name != "nt":
    class _ConPty:  # pragma: no cover - never instantiated on POSIX
        def __init__(self, owner: PtyProcess) -> None:
            raise PtyProcessError("ConPTY support requires Windows")
