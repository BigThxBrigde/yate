"""Unit checks for the conftest pilot-wait diagnostics helpers.

The wrapper installed on ``Pilot._wait_for_screen`` only acts on the
timeout path; these tests drive the probe formatting and the message
enrichment directly (stub pilots and fake pumps, no real Textual app).
"""

# the tests legitimately poke at conftest internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from textual.pilot import WaitForScreenTimeout

import conftest


class _FakeTask:
    """Stand-in for ``asyncio.Task`` with a canned ``done`` verdict."""

    def __init__(self, done: bool) -> None:
        self._done = done

    def done(self) -> bool:
        return self._done


class _FakeQueue:
    """Stand-in for ``asyncio.Queue`` exposing the internal deque."""

    def __init__(self, messages: list[Any]) -> None:  # noqa: Any - queued reprs
        self._queue: list[Any] = list(messages)

    def qsize(self) -> int:
        return len(self._queue)


class _FakePump:
    """Stand-in for a message pump (``_describe_pump`` reads via getattr)."""

    def __init__(
        self,
        pump_id: str | None = None,
        *,
        task: _FakeTask | None = None,
        closing: bool = False,
        closed: bool = False,
        attached: bool = True,
        queue: _FakeQueue | None = None,
    ) -> None:
        self.id = pump_id
        self._task = task
        self._closing = closing
        self._closed = closed
        self.is_attached = attached
        self._message_queue = queue


class _NoScreenPilot:
    """Pilot stand-in whose ``app`` cannot produce a screen."""

    @property
    def app(self) -> Any:  # noqa: Any - raises before any screen exists
        raise RuntimeError("no app")


def test_describe_pump_renders_state_fields() -> None:
    """The snapshot line carries id, task state, flags, depth and queue peek."""
    pump = _FakePump(
        "file-manager-list",
        task=_FakeTask(done=False),
        closing=False,
        closed=False,
        attached=True,
        queue=_FakeQueue(["<Callback #1>", "<Callback #2>"]),
    )
    line = conftest._describe_pump(pump)
    assert "_FakePump#file-manager-list" in line
    assert "task=pending" in line
    assert "closing=False" in line
    assert "closed=False" in line
    assert "attached=True" in line
    assert "qsize=2" in line
    assert "'<Callback #1>'" in line
    assert "'<Callback #2>'" in line


def test_describe_pump_degrades_on_missing_internals() -> None:
    """A pump without the private attributes degrades instead of raising."""
    line = conftest._describe_pump(object())
    assert "task=none" in line
    assert "closing=None" in line
    assert "closed=None" in line
    assert "attached=None" in line
    assert "qsize=-1" in line
    assert "queue=" not in line


def test_format_pump_summary_reports_transient_stall() -> None:
    """An empty unresponsive set means every pump caught up after the timeout."""
    summary = conftest._format_pump_summary([], watched=7)
    assert "all 7 watched pumps answered" in summary
    assert "transient stall" in summary


def test_format_pump_summary_counts_unresponsive_pumps() -> None:
    """The header reports the unresponsive share and one line per pump."""
    dead = _FakePump("dead-one", task=_FakeTask(done=True), closed=True)
    slow = _FakePump("slow-two", task=_FakeTask(done=False), queue=_FakeQueue(["m"]))
    summary = conftest._format_pump_summary([dead, slow], watched=5)
    assert "(probe: 2/5 pumps did not answer)" in summary
    assert "_FakePump#dead-one" in summary
    assert "task=done" in summary
    assert "_FakePump#slow-two" in summary
    assert "task=pending" in summary


def test_format_pump_summary_truncates_long_queue_entries() -> None:
    """A single queued message cannot flood the failure output."""
    pump = _FakePump(
        "flooded",
        task=_FakeTask(done=False),
        queue=_FakeQueue(["x" * 500]),
    )
    summary = conftest._format_pump_summary([pump], watched=1)
    assert "x" * 500 not in summary
    assert "x" * 50 in summary
    assert "x" * 130 not in summary


def test_probe_degrades_when_no_screen_is_readable() -> None:
    """A pilot without a readable app/screen yields the degradation note."""
    probe = conftest._probe_unresponsive_pumps(_NoScreenPilot())
    assert asyncio.run(probe) == "(probe: no current screen - pump states unavailable)"


def test_wrapper_appends_probe_summary_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The re-raised timeout carries the original text plus the probe note."""

    async def raising_original(self: Any, timeout: float = 30.0) -> bool:  # noqa: Any - stub
        raise WaitForScreenTimeout("Timed out while waiting.")

    monkeypatch.setattr(conftest, "_original_wait_for_screen", raising_original)
    with pytest.raises(WaitForScreenTimeout) as excinfo:
        asyncio.run(conftest._probed_wait_for_screen(_NoScreenPilot()))
    assert "Timed out while waiting." in str(excinfo.value)
    assert "(probe: no current screen" in str(excinfo.value)


def test_wrapper_passthrough_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A green original verdict comes back untouched (no probe, no change)."""

    async def green_original(self: Any, timeout: float = 30.0) -> bool:  # noqa: Any - stub
        return True

    monkeypatch.setattr(conftest, "_original_wait_for_screen", green_original)
    assert asyncio.run(conftest._probed_wait_for_screen(_NoScreenPilot())) is True


def test_wrapper_reraises_unrelated_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errors other than the timeout propagate without a probe attempt."""

    async def broken_original(self: Any, timeout: float = 30.0) -> bool:  # noqa: Any - stub
        raise ValueError("boom")

    monkeypatch.setattr(conftest, "_original_wait_for_screen", broken_original)
    with pytest.raises(ValueError, match="boom"):
        asyncio.run(conftest._probed_wait_for_screen(_NoScreenPilot()))
