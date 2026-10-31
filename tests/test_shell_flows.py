# pyright: reportPrivateUsage=false
"""Headless tests for the shell/font flow module (ShellFlows).

Drives :class:`yate.flows.shell_flows.ShellFlows` with recording stand-ins
for the injected collaborators (the spawn verb, the prompt bar, the overlay
pusher) and a real :class:`EditorSession` / :class:`Workspace` pair.  The
real ``run_shell`` / ``fonts.ensure_font`` are stubbed so the tests stay
fast and platform-independent.  Covered: the empty-command guards of
``run`` / ``run_later`` / ``run_async``, the ``show_output`` gating of the
synchronous runner, and the font installer's success and failure reporting.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest

from yate.config import YateConfig
from yate.editor_view.commandline import PromptBar
from yate.flows import OverlayPusher, SpawnFn
from yate.flows import shell_flows
from yate.flows.shell_flows import ShellFlows
from yate.services.fonts import FontStatus
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace
from yate.session import EditorSession


class _SpawnRecorder:
    """Records every run_worker-style spawn call (verb injection stand-in)."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, dict(kwargs)))
        return None


class _PromptStub:
    """Prompt-bar stand-in: exposes ``active_mode``, records idle/activate."""

    def __init__(self) -> None:
        self.active_mode: str = ""
        self.idled = 0
        self.activations: list[tuple[object, ...]] = []

    def idle(self) -> None:
        self.idled += 1

    def activate(self, *args: object, **kwargs: object) -> None:
        self.activations.append((args, dict(kwargs)))


class _OverlayRecorder:
    """Records every ``push_overlay`` call."""

    def __init__(self) -> None:
        self.screens: list[object] = []

    def __call__(self, screen: object) -> None:
        self.screens.append(screen)


def _make_flows() -> tuple[
    ShellFlows,
    _SpawnRecorder,
    _PromptStub,
    _OverlayRecorder,
    list[tuple[str, str]],
    dict[str, bool],
]:
    """Build the flow over recording stand-ins (mounted defaults to True)."""
    spawn = _SpawnRecorder()
    prompt = _PromptStub()
    overlay = _OverlayRecorder()
    messages: list[tuple[str, str]] = []
    mounted_state: dict[str, bool] = {"value": True}
    session = EditorSession(YateConfig())
    session.new_buffer()
    flows = ShellFlows(
        spawn=cast(SpawnFn, spawn),
        session=session,
        workspace=Workspace(),
        prompt=cast(PromptBar, prompt),
        message=lambda text, kind: messages.append((text, kind)),
        mounted=lambda: mounted_state["value"],
        focus_editor=lambda: None,
        refresh=lambda: None,
        push_overlay=cast(OverlayPusher, overlay),
    )
    return flows, spawn, prompt, overlay, messages, mounted_state


def _fake_run_shell(command: str, cwd: Path | None = None) -> ShellResult:
    """Deterministic run_shell stand-in (no subprocess is spawned)."""
    return ShellResult(command, 0, "hello", cwd or Path.cwd())


def test_run_gates_output_overlay_on_show_output_and_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The overlay is pushed only when show_output and mounted both hold.

    ``show_output=False`` (the extension-API path) must return the result
    without any UI feedback, and an unmounted shell must not push either.
    """
    monkeypatch.setattr(shell_flows, "run_shell", _fake_run_shell)
    flows, _spawn, _prompt, overlay, _messages, mounted_state = _make_flows()

    shown = flows.run("echo hi")
    assert shown is not None
    assert shown.returncode == 0
    assert shown.output == "hello"
    assert len(overlay.screens) == 1

    mounted_state["value"] = False
    flows.run("echo hi")
    assert len(overlay.screens) == 1

    flows.run("echo hi", show_output=False)
    assert len(overlay.screens) == 1


def test_run_later_rejects_empty_command() -> None:
    """run_later of a blank command returns before prompting or spawning."""
    flows, spawn, prompt, _overlay, _messages, _mounted = _make_flows()
    prompt.active_mode = "shell"

    flows.run_later("   ")

    assert spawn.calls == []
    assert prompt.idled == 0
    assert prompt.activations == []


def test_run_async_rejects_empty_command() -> None:
    """run_async of a blank command resolves to None with no messages."""
    flows, spawn, _prompt, _overlay, messages, _mounted = _make_flows()

    result = asyncio.run(flows.run_async("  "))

    assert result is None
    assert spawn.calls == []
    assert messages == []


def test_install_font_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """install_font spawns _font_async; a good install reports readiness."""
    monkeypatch.setattr(
        "yate.services.fonts.ensure_font",
        lambda: FontStatus(has_nerd_font=True),
    )
    flows, spawn, _prompt, _overlay, messages, _mounted = _make_flows()

    flows.install_font()

    assert messages[0][0].startswith("checking Nerd Font")
    assert messages[0][1] == "info"
    assert len(spawn.calls) == 1
    fn = spawn.calls[0][0][0]
    assert fn == flows._font_async
    assert spawn.calls[0][1] == {
        "group": "font",
        "exclusive": True,
        "exit_on_error": False,
    }

    asyncio.run(flows._font_async())
    assert messages[-1] == ("Nerd Font ready", "ok")


def test_install_font_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raising ensure_font is reported instead of killing the worker."""
    monkeypatch.setattr(
        "yate.services.fonts.ensure_font",
        _broken_ensure_font,
    )
    flows, _spawn, _prompt, _overlay, messages, _mounted = _make_flows()

    flows.install_font()
    asyncio.run(flows._font_async())

    assert messages[-1] == ("font setup failed: registry exploded", "error")


def _broken_ensure_font() -> FontStatus:
    """ensure_font stand-in that always fails."""
    raise RuntimeError("registry exploded")
