"""Subprocess-backed report screenshots re-rendered through Rich.

Report-style screenshots must show *real* command output (the overview
forbids fabricating them): each command runs in a subprocess at the repo
root with ANSI forced on, the captured text is parsed back into a Rich
``Text`` and printed on a recording console, and the console is exported as
a standalone SVG.  The pytest frame was dropped at the user's request
(2026-11-03); its two-panel builder was removed with it.

Reusing the smoke suite's ``Reporter`` was evaluated and rejected (overview
research item 6): its record mode is bound to an HTML path and needs a
``ScenarioResult`` data pipeline, which couples more than it saves.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys

from rich.console import Console
from rich.text import Text

from tools.screenshots.driver import repo_root, scrub_text

__all__ = ["diag_report_svg", "smoke_report_svg"]

#: Wall clock budgets for the remaining report subprocesses.
_SMOKE_TIMEOUT_S: float = 300.0
_DIAG_TIMEOUT_S: float = 120.0

#: Report width shared by every rendered frame (matches the SVG width used
#: by the pilot scenarios' 100-column app size).
_WIDTH: int = 100


def _capture(cmd: list[str], *, timeout: float) -> str:
    """Run *cmd* at the repo root and return its combined output.

    ``FORCE_COLOR=1`` makes Rich-based tools (smoke report, ``--diag``) emit
    ANSI even without a TTY; pytest is forced separately via ``--color=yes``
    by the caller.  ``PYTHONIOENCODING=utf-8`` pins the child's pipe encoding
    to match our UTF-8 decode: without it the child falls back to the locale
    codec (GBK on Chinese Windows) and every byte outside UTF-8 would decay
    into replacement characters.  Decoding is UTF-8 with replacement so a
    stray invalid byte cannot crash the capture.
    """
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root(),
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        tail = exc.stdout or ""
        if isinstance(tail, bytes):
            tail = tail.decode("utf-8", errors="replace")
        lines = [line for line in tail.splitlines() if line.strip()]
        last = lines[-1] if lines else "<no output captured>"
        raise RuntimeError(
            f"subprocess timed out after {timeout:.0f}s; last line: {last}"
        ) from exc
    output = proc.stdout.rstrip()
    if proc.stderr:
        output = f"{output}\n{proc.stderr.rstrip()}"
    return scrub_text(output)


def _recording_console() -> Console:
    """A recording console that never writes to the real stdout.

    The captured report belongs in the SVG only: printing it to the terminal
    is noise, and on a non-UTF-8 console (GBK) it can even crash with an
    encode error.  A ``StringIO`` file keeps ``record=True`` segments intact
    for :meth:`Console.export_svg`.
    """
    return Console(width=_WIDTH, record=True, file=io.StringIO())


def _ansi_svg(text: str, title: str) -> str:
    """Re-render ANSI-colored *text* on a recording console and export SVG."""
    console = _recording_console()
    console.print(Text.from_ansi(text))
    return console.export_svg(title=title)


def smoke_report_svg() -> str:
    """Run the view-tag smoke suite for real and render its colored report."""
    output = _capture(
        [sys.executable, "-m", "tools.smoke_test", "run", "--tag", "view"],
        timeout=_SMOKE_TIMEOUT_S,
    )
    return _ansi_svg(output, "yate smoke test report (run --tag view)")


def diag_report_svg() -> str:
    """Run ``yate --diag`` for real and render its environment report."""
    output = _capture([sys.executable, "-m", "yate", "--diag"],
                      timeout=_DIAG_TIMEOUT_S)
    return _ansi_svg(output, "yate --diag report")
