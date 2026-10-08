"""Two/three-way diff view scenarios (tags: ``files``, ``command``).

Covers the ``:diff`` command end to end: a two-way compare with hunk
navigation, block copying and the two-step close guard; a three-way merge
with hunk navigation, pane focus cycling and a local->remote copy; and the
four refusal branches, each of which must leave the bottom message as the
only trace (no screen is ever pushed for them).

``DiffScreen`` exposes no public accessors for its mode, labels, selected
hunk, region list or close-guard latch, so the read helpers below go
through ``getattr`` + ``cast`` with the field names taken from
``yate/editor_view/diffview.py`` (``DiffScreen.__init__``).  Direct
attribute access would trip pyright's ``reportPrivateUsage``, which this
repo's zero-diagnostic gate treats as an error.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from textual.widgets import Static

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, plain_text, run_command
from yate.editor_core.diff import DiffHunk, MergeRegion
from yate.editor_view.diff_pane import DiffPane
from yate.editor_view.diffview import DiffScreen

__all__ = ["SCENARIOS"]

#: Real hint text of ``DiffScreen.action_dismiss_guarded`` when at least one
#: side was modified (the em dash is U+2014, exactly as in the source).
_UNSAVED_HINT: str = "unsaved changes \u2014 press esc again to close"

#: Real hint text of the same action with no modified side.
_CLEAN_HINT: str = "press esc again to close"


# --------------------------------------------------------------- read helpers
# Field names below are the ones ``DiffScreen.__init__`` really assigns
# (``_mode`` / ``_labels`` / ``_current`` / ``_regions`` / ``_all_regions`` /
# ``_confirm_close``); ``getattr`` + ``cast`` keeps pyright strict quiet
# about the documented-private access while still failing loudly at runtime
# if a field is ever renamed.


def _mode(screen: DiffScreen) -> str:
    """``"2way"`` or ``"3way"`` (``DiffScreen._mode``)."""
    return cast(str, getattr(screen, "_mode", ""))


def _labels(screen: DiffScreen) -> list[str]:
    """Per-side header labels (``DiffScreen._labels``)."""
    return cast("list[str]", getattr(screen, "_labels", []))


def _current(screen: DiffScreen) -> int:
    """Selected hunk / merge region index; ``-1`` means none (``_current``)."""
    return cast(int, getattr(screen, "_current", -1))


def _hunks(screen: DiffScreen) -> list[DiffHunk]:
    """Two-way non-same regions (``DiffScreen._regions``)."""
    return cast("list[DiffHunk]", getattr(screen, "_regions", []))


def _merge_regions(screen: DiffScreen) -> list[MergeRegion]:
    """Three-way non-same regions (``DiffScreen._regions``)."""
    return cast("list[MergeRegion]", getattr(screen, "_regions", []))


def _all_merge_regions(screen: DiffScreen) -> list[MergeRegion]:
    """Every three-way region, ``same`` spans included (``_all_regions``)."""
    return cast("list[MergeRegion]", getattr(screen, "_all_regions", []))


def _confirm_close(screen: DiffScreen) -> bool:
    """Close-guard latch state (``DiffScreen._confirm_close``)."""
    return cast(bool, getattr(screen, "_confirm_close", False))


def _panes(screen: DiffScreen) -> list[DiffPane]:
    """The mounted per-side panes, in side order (public ``query``)."""
    return list(screen.query(DiffPane))


def _hint(screen: DiffScreen) -> str:
    """Bottom hint line, read from the public ``#diff-hint`` widget."""
    return plain_text(screen.query_one("#diff-hint", Static).content)


def _diff_screen(app: object) -> DiffScreen | None:
    """The top screen when it is a :class:`DiffScreen`, else ``None``."""
    screen = getattr(app, "screen", None)
    return screen if isinstance(screen, DiffScreen) else None


def _doc_names(screen: DiffScreen) -> list[str]:
    """File name of each side, in side order."""
    return [pane.doc.name for pane in _panes(screen)]


def _line_counts(screen: DiffScreen) -> list[int]:
    """Line count of each side's buffer, in side order."""
    return [pane.buffer.line_count for pane in _panes(screen)]


def _side_lines(screen: DiffScreen, side: int) -> list[str]:
    """A copy of one side's buffer lines (``side`` is 0-based)."""
    return list(_panes(screen)[side].buffer.lines)


def _side_modified(screen: DiffScreen, side: int) -> bool:
    """Whether one side's document counts as modified."""
    return _panes(screen)[side].doc.modified


# ------------------------------------------------------------------ scenarios


async def _diff_two_way_navigate(tmp: Path) -> ScenarioResult:
    """``:diff a.txt b.txt`` opens, navigates, copies and closes with esc esc.

    Two replace hunks are seeded (line 2 and line 4).  ``alt+down`` selects
    the first one, ``alt+right`` copies the left block onto the right side,
    and the close guard then needs two escapes because the right side is now
    modified.
    """
    (tmp / "a.txt").write_text(
        "alpha\nbravo\ncharlie\ndelta\n", encoding="utf-8"
    )
    (tmp / "b.txt").write_text(
        "alpha\nBRAVO\ncharlie\nDELTA\n", encoding="utf-8"
    )
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await run_command(pilot, "diff a.txt b.txt")
        screen = _diff_screen(app)
        checks.append(Check("screen_pushed", 2, len(app.screen_stack)))
        checks.append(Check("is_diff_screen", True, screen is not None))
        assert screen is not None
        checks.append(Check("mode", "2way", _mode(screen)))
        checks.append(Check("labels", ["left", "right"], _labels(screen)))
        checks.append(Check("doc_names", ["a.txt", "b.txt"], _doc_names(screen)))
        checks.append(Check("line_counts", [5, 5], _line_counts(screen)))
        checks.append(Check("pane_count", 2, len(_panes(screen))))
        checks.append(
            Check("hunk_count", 2, len(_hunks(screen)))
        )
        checks.append(Check("hunk_kinds", ["replace", "replace"],
                            [h.kind for h in _hunks(screen)]))
        checks.append(Check("nothing_selected_initially", -1, _current(screen)))
        checks.append(Check("guard_clear_initially", False,
                            _confirm_close(screen)))

        await pilot.press("alt+down")
        await pilot.pause()
        checks.append(Check("first_change_selected", 0, _current(screen)))
        checks.append(Check("still_open_after_nav", 2, len(app.screen_stack)))

        right_before = _side_lines(screen, 1)
        checks.append(Check("right_before", "BRAVO", right_before[1]))
        await pilot.press("alt+right")
        await pilot.pause()
        right_after = _side_lines(screen, 1)
        checks.append(Check("right_line_copied", "bravo", right_after[1]))
        checks.append(Check("right_buffer_changed", True,
                            right_after != right_before))
        checks.append(Check("right_side_modified", True,
                            _side_modified(screen, 1)))
        checks.append(Check("left_side_untouched", False,
                            _side_modified(screen, 0)))
        checks.append(Check("hunk_count_after_copy", 1, len(_hunks(screen))))

        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("first_esc_keeps_screen", 2, len(app.screen_stack)))
        checks.append(Check("first_esc_arms_guard", True,
                            _confirm_close(screen)))
        checks.append(Check("first_esc_hint", _UNSAVED_HINT, _hint(screen)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("second_esc_closes", 1, len(app.screen_stack)))
        checks.append(Check("back_to_editor", True, _diff_screen(app) is None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("diff_two_way_navigate", checks, rows)


async def _diff_three_way_merge(tmp: Path) -> ScenarioResult:
    """``:diff --3way base local remote`` renders three panes and merges.

    ``local`` and ``remote`` each change the same base line differently, so
    the only non-``same`` region is a ``conflict``.  ``tab`` / ``ctrl+3``
    move the pane focus and ``alt+right`` copies local onto remote.
    """
    (tmp / "base.txt").write_text("a\nb\nc\n", encoding="utf-8")
    (tmp / "local.txt").write_text("a\nLOCAL\nc\n", encoding="utf-8")
    (tmp / "remote.txt").write_text("a\nREMOTE\nc\n", encoding="utf-8")
    app = new_app(target=tmp / "base.txt")
    checks: list[Check] = []
    async with app.run_test(size=(120, 34)) as pilot:
        await pilot.pause()
        await run_command(pilot, "diff --3way base.txt local.txt remote.txt")
        screen = _diff_screen(app)
        checks.append(Check("screen_pushed", 2, len(app.screen_stack)))
        checks.append(Check("is_diff_screen", True, screen is not None))
        assert screen is not None
        checks.append(Check("mode", "3way", _mode(screen)))
        checks.append(Check("labels", ["base", "local", "remote"],
                            _labels(screen)))
        checks.append(Check("pane_count", 3, len(_panes(screen))))
        checks.append(
            Check("doc_names", ["base.txt", "local.txt", "remote.txt"],
                  _doc_names(screen))
        )
        checks.append(Check("line_counts", [4, 4, 4], _line_counts(screen)))
        checks.append(
            Check("all_region_kinds", ["same", "conflict", "same"],
                  [r.kind for r in _all_merge_regions(screen)])
        )
        checks.append(Check("merge_region_count", 1, len(_merge_regions(screen))))
        checks.append(Check("merge_region_kind", "conflict",
                            _merge_regions(screen)[0].kind))
        checks.append(Check("nothing_selected_initially", -1, _current(screen)))

        await pilot.press("alt+down")
        await pilot.pause()
        checks.append(Check("region_selected", 0, _current(screen)))

        await pilot.press("tab")
        await pilot.pause()
        checks.append(Check("tab_focuses_pane_2", _panes(screen)[1], app.focused))
        await pilot.press("ctrl+3")
        await pilot.pause()
        checks.append(Check("ctrl3_focuses_pane_3", _panes(screen)[2], app.focused))

        remote_before = _side_lines(screen, 2)
        checks.append(Check("remote_before", "REMOTE", remote_before[1]))
        await pilot.press("alt+right")
        await pilot.pause()
        checks.append(Check("remote_line_copied", "LOCAL",
                            _side_lines(screen, 2)[1]))
        checks.append(Check("remote_side_modified", True,
                            _side_modified(screen, 2)))
        checks.append(Check("base_never_a_target", False,
                            _side_modified(screen, 0)))
        checks.append(
            Check("conflict_resolved_to_both", "both",
                  _merge_regions(screen)[0].kind)
        )

        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("first_esc_keeps_screen", 2, len(app.screen_stack)))
        checks.append(Check("first_esc_hint", _UNSAVED_HINT, _hint(screen)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("second_esc_closes", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("diff_three_way_merge", checks, rows)


async def _diff_failure_paths(tmp: Path) -> ScenarioResult:
    """Every refused ``:diff`` leaves the stack at 1 and reports on the bar.

    The four branches are the real ones in ``yate/commands.py::_diff`` and
    ``yate/overlays.py::open_diff``: wrong arity, a missing file, a file
    ``Workspace.is_text_file`` rejects (suffix ``.bin`` is not in
    ``TEXT_SUFFIXES``, so the verdict is suffix-based and identical on every
    platform), and ``--3way`` with only two names.
    """
    (tmp / "a.txt").write_text("alpha\nbravo\n", encoding="utf-8")
    (tmp / "b.txt").write_text("alpha\nBRAVO\n", encoding="utf-8")
    # Real bytes, so the fixture matches what the branch is meant to reject.
    (tmp / "blob.bin").write_bytes(b"\x00\x01\x02\x03binary\xff")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()

        await run_command(pilot, "diff")
        checks.append(Check("usage_no_screen", 1, len(app.screen_stack)))
        usage = message_text(app)
        checks.append(Check("usage_message", True, "usage: :diff" in usage))
        checks.append(Check("usage_message_full", True,
                            "usage: :diff [--3way] FILE1 FILE2 [FILE3] "
                            "(quote paths with spaces)" in usage))

        await run_command(pilot, "diff missing.txt b.txt")
        checks.append(Check("missing_no_screen", 1, len(app.screen_stack)))
        missing = message_text(app)
        checks.append(Check("missing_message", True, "no such file" in missing))
        checks.append(Check("missing_message_names_file", True,
                            "missing.txt" in missing))

        await run_command(pilot, "diff blob.bin b.txt")
        checks.append(Check("binary_no_screen", 1, len(app.screen_stack)))
        checks.append(Check("binary_message", True,
                            "not a text file: blob.bin" in message_text(app)))

        await run_command(pilot, "diff --3way a.txt b.txt")
        checks.append(Check("threeway_arity_no_screen", 1, len(app.screen_stack)))
        checks.append(Check("threeway_arity_message", True,
                            "--3way needs three files" in message_text(app)))

        checks.append(Check("no_diff_screen_left", True, _diff_screen(app) is None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("diff_failure_paths", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("diff_two_way_navigate", _diff_two_way_navigate, ("files", "command")),
    Scenario("diff_three_way_merge", _diff_three_way_merge, ("files", "command")),
    Scenario("diff_failure_paths", _diff_failure_paths, ("files", "command")),
]
