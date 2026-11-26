"""Regression tests for the PB6 probe's process-count query (m19).

Pins review finding m19 only: a failed PowerShell / CIM lookup (non-zero
exit, empty or unparsable output) returns ``-1`` instead of ``0``, so "the
query broke" can never be reported as "the app exited" -- that was a fake
PASS on the ctrl+q quit assertion.
"""

# marker_process_count is under test directly; the module's Win32 glue
# (ctypes.windll) is import-only on Windows, which is where the probe runs.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import subprocess

import pytest

from tools.probes import pb6_real_input_harness


@pytest.fixture
def canned_result(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.CompletedProcess[str]]:
    """Stub ``subprocess.run``; ``canned_result[0]`` is the reply to mutate."""
    box: list[subprocess.CompletedProcess[str]] = [
        subprocess.CompletedProcess([], 0, "", "")
    ]

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return box[0]

    monkeypatch.setattr(pb6_real_input_harness.subprocess, "run", fake_run)
    return box


def test_marker_process_count_counts_live_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parsable count is returned as an int."""
    def fake_run(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "2\n", "")

    monkeypatch.setattr(pb6_real_input_harness.subprocess, "run", fake_run)
    assert pb6_real_input_harness.marker_process_count() == 2


def test_marker_process_count_zero_means_the_app_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit ``0`` on a healthy query still means "app exited"."""
    def fake_run(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "0\n", "")

    monkeypatch.setattr(pb6_real_input_harness.subprocess, "run", fake_run)
    assert pb6_real_input_harness.marker_process_count() == 0


def test_marker_process_count_nonzero_returncode_is_a_failure(
    canned_result: list[subprocess.CompletedProcess[str]],
) -> None:
    """A failed query returns -1, never 0 (m19: no fake PASS)."""
    canned_result[0].returncode = 1

    assert pb6_real_input_harness.marker_process_count() == -1


def test_marker_process_count_empty_stdout_is_a_failure(
    canned_result: list[subprocess.CompletedProcess[str]],
) -> None:
    """Empty output on a zero exit (CIM hiccup) returns -1, not 0."""
    canned_result[0].stdout = ""

    assert pb6_real_input_harness.marker_process_count() == -1


def test_marker_process_count_unparsable_stdout_is_a_failure(
    canned_result: list[subprocess.CompletedProcess[str]],
) -> None:
    """Unparsable output returns -1 instead of raising or guessing."""
    canned_result[0].stdout = "not a number\n"

    assert pb6_real_input_harness.marker_process_count() == -1
