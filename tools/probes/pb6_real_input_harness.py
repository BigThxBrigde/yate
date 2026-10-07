"""Unattended real-machine key delivery harness for the chord driver.

Spawns a real Windows Terminal window running yate (trace enabled), injects
REAL keystrokes via ``SendInput`` (OS-level input, not pilot synthesis),
then parses the ``YATE_TRACE`` log to assert what actually reached the app.
This is the PB5/PB6 verification loop a human would otherwise do by hand.

Usage (from the worktree root, any shell):

    .venv/Scripts/python.exe ^
        tools/probes/pb6_real_input_harness.py

Exit code 0 = all hard assertions passed; 1 = delivery failures; 2 = could
not set up (window/focus).  Requires: Windows Terminal (``wt``), a desktop
session (no focus stealing during the run).
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ctypes import wintypes

# ---------------------------------------------------------------- Win32 glue

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_OEM_3 = 0xC0  # grave / backtick (US layout)
WM_INPUTLANGCHANGEREQUEST = 0x0050
VK_KEY_1 = 0x31
VK_KEY_E = 0x45
VK_KEY_P = 0x50
VK_KEY_Q = 0x51
VK_KEY_X = 0x58
VK_ESCAPE = 0x1B


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTUnion(ctypes.Union):
    # Must match the real INPUT union size (MOUSEINPUT is the largest
    # member, 32 bytes on x64) or SendInput rejects cbSize with
    # ERROR_INVALID_PARAMETER (87) -- seen live before this fix.
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_ubyte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUnion)]


assert ctypes.sizeof(INPUT) == 40, "INPUT layout must match winuser.h on x64"


def send_vk(vk: int, up: bool = False) -> None:
    """Inject one virtual-key event through the OS input stack."""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if up else 0,
        time=0,
        dwExtraInfo=ctypes.POINTER(ctypes.c_ulong)(),
    )
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        # SendInput returns 0 when blocked by UIPI: the foreground window is
        # elevated while this process is not.  Run the harness elevated
        # (UAC silent-approve on this machine: ConsentPromptBehaviorAdmin=0).
        raise OSError(
            "SendInput failed -- foreground process likely elevated; "
            "run this harness elevated"
        )


def tap(vk: int) -> None:
    send_vk(vk)
    time.sleep(0.05)
    send_vk(vk, up=True)


def chord(mods: list[int], vk: int) -> None:
    """Press and release *vk* with *mods* held (real modifier key events)."""
    for mod in mods:
        send_vk(mod)
    time.sleep(0.05)
    tap(vk)
    for mod in reversed(mods):
        send_vk(mod, up=True)


def visible_windows() -> dict[int, str]:
    """Snapshot {hwnd: title} of all visible top-level windows."""
    result: dict[int, str] = {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def on_window(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1) if length else None
            if buf is not None:
                user32.GetWindowTextW(hwnd, buf, length + 1)
                result[hwnd] = buf.value
        return True

    user32.EnumWindows(on_window, 0)
    return result


def find_new_window(
    before: dict[int, str], title_fragment: str
) -> int:
    """Return the best new visible window since the *before* snapshot.

    Prefers a title containing *title_fragment* (the ``--title`` tab name
    may be overridden by the TUI's own title escape sequences, so any new
    window is accepted as fallback -- within the launch window nothing else
    creates top-level windows).
    """
    time.sleep(0.5)
    matches: list[int] = []
    titled: list[int] = []
    for hwnd, title in visible_windows().items():
        if hwnd not in before:
            matches.append(hwnd)
            if title_fragment in title:
                titled.append(hwnd)
    if titled:
        return titled[0]
    return matches[0] if matches else 0


def focus_window(hwnd: int) -> bool:
    """Bring *hwnd* to the foreground, working around the foreground lock."""
    for _ in range(10):
        foreground = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(foreground, None)
        this_thread = kernel32.GetCurrentThreadId()
        if fg_thread != this_thread:
            user32.AttachThreadInput(this_thread, fg_thread, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if fg_thread != this_thread:
            user32.AttachThreadInput(this_thread, fg_thread, False)
        time.sleep(0.3)
        if user32.GetForegroundWindow() == hwnd:
            return True
    return False


# ------------------------------------------------------------------- harness

TRACE_DIR = Path.home() / ".yate" / "data" / "logs"
MARKER = "yate-kbtest-marker"


def newest_trace(start_ts: float) -> Path | None:
    """Return the newest yate trace log created after *start_ts*."""
    if not TRACE_DIR.is_dir():
        return None
    candidates = [
        p for p in TRACE_DIR.glob("yate-*.log") if p.stat().st_mtime >= start_ts
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def kill_marker_processes() -> None:
    """Force-kill leftover yate processes spawned for this run."""
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | "
            f"Where-Object CommandLine -like '*{MARKER}*' | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
        ],
        check=False,
        capture_output=True,
    )


def ensure_english_layout(hwnd: int) -> bool:
    """Switch the foreground thread's keyboard layout to plain US English.

    A Chinese IME in Chinese mode hijacks harness keys: letters arrive as
    composed hanzi (live evidence: ``x`` -> ``key=先``), arrows are candidate
    selectors, and ctrl+space is the IME open/close hotkey.  Requesting the
    bare US layout makes every injected key bypass the IME regardless of its
    mode -- required for unattended determinism.
    """
    user32.LoadKeyboardLayoutW("00000409", 0x0002)  # KLF_SUBSTITUTE_OK
    user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, 0x04090409)
    for _ in range(10):
        time.sleep(0.2)
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        if user32.GetKeyboardLayout(tid) & 0xFFFF == 0x0409:
            return True
    return False


def marker_process_count() -> int:
    """Count live yate processes spawned for this run (0 = app exited)."""
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Process | "
            f"Where-Object CommandLine -like '*{MARKER}*').Count",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        return int(result.stdout.strip() or "0")
    except ValueError:
        return -1


def main() -> int:
    worktree = Path(__file__).resolve().parents[3]
    python = Path(".venv/Scripts/python.exe")
    if not python.exists():
        python = worktree / ".venv" / "Scripts" / "python.exe"
    found = subprocess.run(
        ["where", "wt.exe"], capture_output=True, text=True, check=False
    )
    if found.returncode != 0 or not found.stdout.strip():
        print("FAIL: wt.exe not found (Windows Terminal required)")
        return 2

    test_dir = Path(tempfile.mkdtemp(prefix=f"{MARKER}-"))
    (test_dir / "sample.py").write_text("print('hello')\n", encoding="utf-8")
    snapshot = visible_windows()
    start_ts = time.time()
    env = dict(os.environ)
    env["YATE_TRACE"] = "1"
    # Unique window name per run: a leftover window from an earlier run would
    # host the new tab without creating a new top-level window, which would
    # defeat the snapshot-diff window discovery below.
    wt_window = f"yatekbtest-{int(time.time())}"
    proc = subprocess.Popen(
        [
            "wt.exe",
            "-w",
            wt_window,
            "new-tab",
            "--title",
            "yate-kbtest",
            str(python),
            "-m",
            "yate",
            str(test_dir),
        ],
        cwd=str(worktree),
        env=env,
    )
    print(f"harness: launched wt (pid={proc.pid}), test dir {test_dir}")

    try:
        # -- wait for yate to start writing its trace
        trace: Path | None = None
        for _ in range(60):
            trace = newest_trace(start_ts)
            if trace is not None and trace.stat().st_size > 0:
                break
            time.sleep(0.5)
        if trace is None:
            print("FAIL: no trace log appeared (yate did not start?)")
            kill_marker_processes()
            return 2
        print(f"harness: trace {trace.name}")
        time.sleep(3.0)  # let the TUI settle

        hwnd = 0
        for _ in range(20):
            hwnd = find_new_window(snapshot, "yate-kbtest")
            if hwnd:
                break
            time.sleep(0.5)
        if not hwnd:
            print("FAIL: new yate window not found after launch")
            kill_marker_processes()
            return 2
        if not focus_window(hwnd):
            print("FAIL: could not focus the yate window; aborting WITHOUT "
                  "sending keys (they would hit whatever is focused)")
            kill_marker_processes()
            return 2
        print("harness: window focused, injecting keys")
        if not ensure_english_layout(hwnd):
            print("harness: WARN could not switch to US layout; an active "
                  "IME may eat plain keys (expect hanzi evidence)")
        time.sleep(1.0)

        # -- key sequence (arrival-focused; see module docstring)
        sequence: list[tuple[str, object]] = [
            ("x", lambda: tap(VK_KEY_X)),
            ("down", lambda: tap(VK_DOWN)),
            ("ctrl+p", lambda: chord([VK_CONTROL], VK_KEY_P)),
            ("escape", lambda: tap(VK_ESCAPE)),
            ("ctrl+shift+e", lambda: chord([VK_CONTROL, VK_SHIFT], VK_KEY_E)),
            ("ctrl+1", lambda: chord([VK_CONTROL], VK_KEY_1)),
            ("ctrl+space (informational)", lambda: chord([VK_CONTROL], VK_SPACE)),
            ("escape", lambda: tap(VK_ESCAPE)),
            ("ctrl+`", lambda: chord([VK_CONTROL], VK_OEM_3)),
            ("ctrl+`", lambda: chord([VK_CONTROL], VK_OEM_3)),
            ("ctrl+q (quit)", lambda: chord([VK_CONTROL], VK_KEY_Q)),
        ]
        for label, action in sequence:
            action()
            time.sleep(0.45)
            print(f"harness: sent {label}")

        # -- wait for yate to exit (trace stops growing)
        deadline = time.time() + 25
        last_size = -1
        stable = 0
        while time.time() < deadline and stable < 4:
            size = trace.stat().st_size
            stable = stable + 1 if size == last_size else 0
            last_size = size
            time.sleep(0.5)
        # ctrl+q quits through Textual BINDINGS (never passes
        # Editor.handle_key), so the app process vanishing is the real proof.
        app_exited = marker_process_count() == 0
        kill_marker_processes()  # graceful ctrl+q should have exited already
        time.sleep(1.0)

        content = trace.read_text(encoding="utf-8", errors="replace")
        checks: list[tuple[str, str, bool]] = []
        for needle, label in [
            ("key event: key=x", "plain 'x' typed"),
            ("key event: key=down", "down arrow"),
            ("key event: key=ctrl+p", "ctrl+p (palette)"),
            ("chord: vk=0x45", "ctrl+shift+e chord at driver level"),
            ("-> ctrl+shift+e", "ctrl+shift+e named"),
            ("key event: key=ctrl+shift+e", "ctrl+shift+e reached app"),
            ("chord: vk=0x31", "ctrl+1 chord at driver level"),
            ("key event: key=ctrl+1", "ctrl+1 reached app"),
            ("key event: key=ctrl+space", "ctrl+space reached app (IME may block)"),
            ("terminal on_key: key=ctrl+`", "terminal consumption log (ctrl+` toggle)"),
            ("-> ctrl+q", "ctrl+q delivered at driver level"),
        ]:
            checks.append((label, needle, needle in content))
        checks.append(("app exited on ctrl+q", "", app_exited))

        print("\n=== PB6 real-input harness results ===")
        failures = 0
        for label, needle, ok in checks:
            mark = "PASS" if ok else "FAIL"
            informational = "informational" in label or "IME" in label
            if not ok and informational:
                mark = "WARN"
            else:
                failures += 0 if ok else 1
            print(f"[{mark}] {label}")
        print("\n-- chord/frame evidence lines --")
        for line in content.splitlines():
            if "chord:" in line or "unmapped" in line or "terminal on_key" in line:
                print(f"  {line.strip()}")
        return 0 if failures == 0 else 1
    finally:
        kill_marker_processes()


if __name__ == "__main__":
    sys.exit(main())
