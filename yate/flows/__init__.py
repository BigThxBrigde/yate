"""L3 flow modules: single-purpose orchestration split out of the editor.

Each module here is constructed by :class:`yate.editor.Editor` with explicit
collaborators and callbacks; none of them imports upward (no ``yate.editor``
/ ``yate.app``) and none holds the App handle (architecture-boundaries
section 1 L3, R11).  The package ``__init__`` stays lazy (architecture-boundaries
rule 3.5): no re-exports, import every module by its full path, e.g.
``from yate.flows.completion_flows import CompletionFlows``.

The one thing this module *does* declare is the shared vocabulary of the
capabilities the editor injects into the flows -- it builds those callables
once and hands the same ones to every flow (issue IKJUWP).  No submodule is
imported here, so the laziness promise above still holds; the two Textual
module imports it does make are cheap and every flow submodule needs them
anyway.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textual.screen import Screen
from textual.worker import Worker

#: ``message(text, kind)`` -- write one line on the message line (*kind* is a
#: :data:`yate.editor_view.commandline.MESSAGE_COLORS` key: ``"info"`` /
#: ``"error"`` / ``"warn"`` / ``"ok"``); the editor owns the callable.
type MessageFn = Callable[[str, str], None]

#: Bound ``App.run_worker``: the background-work verb injected by the editor.
#: Flows never hold the App handle themselves (R11 / capability injection).
type SpawnFn = Callable[..., Worker[object]]

#: ``push_overlay(screen)`` -- mount a modal overlay on the screen stack.
type OverlayPusher = Callable[[Screen[Any]], None]  # noqa: Any - any Textual Screen

#: Query a state flag a flow must respect before acting -- ``mounted``,
#: ``has_modal_screen``, ``explorer_focused``.  Evaluated at call time, so the
#: answer follows the shell instead of the construction moment.
type StateQuery = Callable[[], bool]
