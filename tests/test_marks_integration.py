"""goto_line pushes the pre-jump cursor onto the session jump list.

Integration seam for plan-d (issue IKUOCI): every line-jump entry point --
``:42``, ctrl-g and the ``+N``/``-N`` offset form -- funnels into
``PromptFlows.goto_line``, which must call ``session.push_jump()`` *before*
moving the cursor so alt-left can return to where the jump started (AC3).
Real ``EditorSession`` / ``Document``; panes, prompt, message and refresh
are recording stubs (no UI, no Textual).
"""

from __future__ import annotations

from typing import cast

from yate.config import YateConfig
from yate.editor_components.commandline import PromptBar
from yate.editor_components.panes import PaneManager
from yate.editor_components.view import EditorView
from yate.editor_core import Document
from yate.editor_core.buffer import TextBuffer
from yate.flows.prompt_flows import PromptFlows
from yate.session import EditorSession, JumpEntry

#: A 20-line document: "line 1" .. "line 20" (1-based line N is row N-1).
_DOC_TEXT = "\n".join(f"line {n}" for n in range(1, 21))


class _StubPanes:
    """``PaneManager`` stand-in: no mounted views, nothing to reveal."""

    def __init__(self) -> None:
        self.active_view: EditorView | None = None

    def views_for(self, doc: Document) -> list[EditorView]:
        return []


class _StubPrompt:
    """``PromptBar`` stand-in; ``goto_line`` itself never touches it."""


class _Harness:
    """A real session plus a stubbed ``PromptFlows`` and its recorders."""

    def __init__(self) -> None:
        self.session = EditorSession(YateConfig())
        self.session.docs.append(Document(None, TextBuffer(_DOC_TEXT)))
        self.session.index = 0
        self.messages: list[tuple[str, str]] = []
        self.refreshed: list[bool] = []
        self.flows = PromptFlows(
            session=self.session,
            panes=cast(PaneManager, _StubPanes()),
            prompt=cast(PromptBar, _StubPrompt()),
            message=self._message,
            readonly_notice=lambda: None,
            refresh=self._refresh,
        )

    def _message(self, text: str, kind: str) -> None:
        self.messages.append((text, kind))

    def _refresh(self) -> None:
        self.refreshed.append(True)


def test_goto_line_pushes_jump_before_moving() -> None:
    """goto_line(15) records the pre-jump cursor (0, 0), then lands row 14."""
    harness = _Harness()
    doc = harness.session.doc

    harness.flows.goto_line(15)

    back, _forward = harness.session.jumps.stacks()
    assert back[-1] == JumpEntry(doc.uid, doc.display_path, 0, 0)
    assert harness.session.buffer.row == 14


def test_goto_line_same_position_dedups() -> None:
    """Re-jumping to the line the cursor already sits on keeps one entry.

    The dedup needs the origin to repeat, so the cursor starts on line 15
    (row 14) and both pushes capture the same position; ``JumpList.push``
    drops the second one (plan-a semantics).
    """
    harness = _Harness()
    harness.session.buffer.set_cursor((14, 0))

    harness.flows.goto_line(15)
    harness.flows.goto_line(15)

    back, _forward = harness.session.jumps.stacks()
    assert len(back) == 1


def test_goto_line_two_targets_two_entries() -> None:
    """Two distinct targets record two origins; one back step returns row 4."""
    harness = _Harness()

    harness.flows.goto_line(5)
    harness.flows.goto_line(10)

    back, _forward = harness.session.jumps.stacks()
    assert len(back) == 2
    back_target = harness.session.jump_back()
    assert back_target is not None
    assert back_target.row == 4


def test_relative_goto_pushes_history() -> None:
    """A "+5" offset jumps five rows down and records one history entry."""
    harness = _Harness()

    harness.flows.goto_line_command("+5")

    back, _forward = harness.session.jumps.stacks()
    assert len(back) == 1
    assert harness.session.buffer.row == 5


def test_goto_line_out_of_range_still_clamps_and_records() -> None:
    """An out-of-range target clamps to the last row and still records.

    The recorded entry is the *pre-jump* position (row 0), independent of
    where the clamp lands.
    """
    harness = _Harness()
    doc = harness.session.doc

    harness.flows.goto_line(999)

    back, _forward = harness.session.jumps.stacks()
    assert back == [JumpEntry(doc.uid, doc.display_path, 0, 0)]
    assert harness.session.buffer.row == 19


def test_jump_back_after_goto_returns_to_previous_line() -> None:
    """alt-left simulation: two gotos, one back step lands on the prior row."""
    harness = _Harness()

    harness.flows.goto_line(5)
    harness.flows.goto_line(10)
    assert harness.session.buffer.row == 9

    back_target = harness.session.jump_back()
    assert back_target is not None
    # The L3 wiring repositions the cursor from the returned entry; the
    # model itself only hands the entry back (session tests fix that).
    harness.session.buffer.set_cursor((back_target.row, back_target.col))
    assert harness.session.buffer.row == 4
