"""Workspace navigation scenarios: explorer keys, ``:e <dir>``, pane chords.

Three adjacent behaviours that the ``explorer`` / ``panes`` modules only touch
in passing get their own end-to-end walk here:

* ``explorer_navigate_and_esc`` -- the vim tree keys (``j`` / ``k`` / ``l`` /
  ``h`` / ``esc``) plus the invariant that plain typing is *swallowed* by the
  tree instead of leaking into the buffer behind it;
* ``open_directory_switches_workspace`` -- ``:e <dir>`` re-roots the workspace,
  reveals the sidebar and focuses the tree.  A relative argument resolves
  against the *workspace root*
  (:meth:`yate.document_flows.DocumentFlows.resolve_input_path`), not the
  process cwd, which is what the scenario pins down;
* ``pane_resize_chords`` -- the vim ``ctrl+w`` chord with ``+`` / ``-`` / ``=``
  and the "pane at its minimum size" / "only one pane open" warnings.

Pane geometry *is* observable: :class:`yate.session.Split` keeps the fractional
sizes of every split, and :attr:`yate.editor_view.panes.PaneManager.root` is
the public tree root, so the resize assertions read real numbers instead of
guessing from the rendering.  Only :meth:`WindowFlows._window_pending` is
private, and the public :attr:`WindowFlows.window_pending` property covers it.
"""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import cursor_path, message_text, run_command, type_text, wait_until
from yate.app import YateApp
from yate.session import MIN_FRACTION, Split

__all__ = ["SCENARIOS"]


# --------------------------------------------------------------- read helpers


def _cursor_name(app: YateApp) -> str | None:
    """File name of the explorer node under the cursor (``None`` if unset)."""
    data = cursor_path(app)
    return data.name if isinstance(data, Path) else None


def _cursor_expanded(app: YateApp) -> bool:
    """Whether the explorer's cursor node is an expanded directory."""
    node = app.editor.explorer_tree.cursor_node
    return node.is_expanded if node is not None else False


def _child_names(app: YateApp) -> list[str]:
    """Names of the cursor node's children (placeholders report as ``""``)."""
    node = app.editor.explorer_tree.cursor_node
    if node is None:
        return []
    return [child.data.name if isinstance(child.data, Path) else "" for child in node.children]


def _pane_sizes(app: YateApp) -> list[float]:
    """Fractional sizes of the root split, rounded to kill float noise.

    ``[]`` when the pane tree has a single leaf (no split to measure).
    """
    root = app.editor.panes.root
    if not isinstance(root, Split):
        return []
    return [round(size, 3) for size in root.sizes]


# ----------------------------------------------------------------- scenarios


async def _explorer_navigate_and_esc(tmp: Path) -> ScenarioResult:
    """``j`` / ``k`` / ``l`` / ``h`` / ``esc`` drive the tree; typing never leaks.

    The tree is walked down into ``root/sub``, the file is opened with ``l``
    (which hands focus back to the editor), and the cursor climbs back out with
    ``h``.  Plain characters typed while the tree holds the focus must be
    consumed by ``ExplorerTree._is_plain_typing`` -- if that guard ever
    regresses, they land in the open buffer and the text assertions fail.
    """
    root = tmp / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    inner = sub / "inner.txt"
    inner_text = "inner line\n"
    inner.write_text(inner_text, encoding="utf-8")
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        checks.append(Check("root_is_tmp", tmp.resolve().name,
                            app.editor.workspace.root.name
                            if app.editor.workspace.root else None))
        await pilot.press("ctrl+e")
        await pilot.pause()
        checks.append(Check("tree_focused", True,
                            app.focused is app.editor.explorer_tree))
        # root node -> first child (directories sort first)
        checks.append(Check("cursor_on_root", tmp.resolve().name, _cursor_name(app)))
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("j_to_root_dir", "root", _cursor_name(app)))
        # l on a directory expands it and lazily loads its children
        await pilot.press("l")
        await pilot.pause()
        checks.append(Check("l_expanded", True, _cursor_expanded(app)))
        checks.append(Check("loaded_sub", ["sub"], _child_names(app)))
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("j_to_sub", "sub", _cursor_name(app)))
        await pilot.press("l")
        await pilot.pause()
        checks.append(Check("sub_expanded", True, _cursor_expanded(app)))
        checks.append(Check("loaded_inner", ["inner.txt"], _child_names(app)))
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check("j_to_file", "inner.txt", _cursor_name(app)))
        # l on a file opens it in a worker and focuses the editor
        await pilot.press("l")
        await wait_until(pilot, lambda: app.editor.session.doc.name == "inner.txt")
        checks.append(Check("opened_file", "inner.txt", app.editor.session.doc.name))
        checks.append(Check("one_pane", 1, app.editor.panes.leaf_count))
        # back to the tree: plain typing must not reach the buffer
        await pilot.press("ctrl+e")
        await pilot.pause()
        checks.append(Check("tree_refocused", True, await wait_until(
            pilot, lambda: _cursor_name(app) == "inner.txt")))
        await type_text(pilot, "xyz")
        checks.append(Check("typing_swallowed", inner_text,
                            app.editor.session.buffer.get_text()))
        checks.append(Check("doc_clean", False, app.editor.session.doc.modified))
        # h: file -> parent, an expanded node collapses, a collapsed one moves
        # up (sub -> the root *directory* -> the tree root node)
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("h_to_parent", "sub", _cursor_name(app)))
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("h_collapsed_sub", False, _cursor_expanded(app)))
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("h_to_root_dir", "root", _cursor_name(app)))
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("h_collapsed_root_dir", False, _cursor_expanded(app)))
        await pilot.press("h")
        await pilot.pause()
        checks.append(Check("h_to_root_node", tmp.resolve().name, _cursor_name(app)))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("esc_focuses_editor", True,
                            app.focused is app.editor.panes.active_view))
        checks.append(Check("buffer_intact", inner_text,
                            app.editor.session.buffer.get_text()))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("explorer_navigate_and_esc", checks, rows)


async def _open_directory_switches_workspace(tmp: Path) -> ScenarioResult:
    """:e <dir> re-roots the workspace, reveals the sidebar and focuses the tree.

    The argument is *relative*, so it only resolves if the base is the
    workspace root (``tmp``) rather than the process cwd: there is no
    ``proj`` directory in the repository root.  Opening a folder leaves the
    active document alone -- only the tree and the workspace move.
    """
    proj = tmp / "proj"
    proj.mkdir()
    (proj / "keep.txt").write_text("keep\n", encoding="utf-8")
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        checks.append(Check("started_on_file", "a.txt", app.editor.session.doc.name))
        checks.append(Check("explorer_hidden", False, app.editor.explorer_visible))
        checks.append(Check("tree_hidden", False, app.editor.explorer_tree.display))
        checks.append(Check("root_before", tmp.resolve().name,
                            app.editor.workspace.root.name
                            if app.editor.workspace.root else None))
        await run_command(pilot, "e proj")
        checks.append(Check("rerooted", True, await wait_until(
            pilot, lambda: app.editor.workspace.root == proj.resolve())))
        checks.append(Check("root_after", "proj",
                            app.editor.workspace.root.name
                            if app.editor.workspace.root else None))
        checks.append(Check("explorer_shown", True, app.editor.explorer_visible))
        checks.append(Check("tree_shown", True, app.editor.explorer_tree.display))
        checks.append(Check("tree_focused", True, app.focused is app.editor.explorer_tree))
        checks.append(Check("folder_message", True,
                            "opened folder" in message_text(app)))
        # a folder open is not a document open
        checks.append(Check("doc_untouched", "a.txt", app.editor.session.doc.name))
        checks.append(Check("still_one_pane", 1, app.editor.panes.leaf_count))
        # The workspace root stays on proj for the rest of this app's life;
        # the runner builds a fresh app per scenario, so nothing leaks.
        checks.append(Check("terminal_root", "proj",
                            app.editor.workspace.root.name
                            if app.editor.workspace.root else None))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("open_directory_switches_workspace", checks, rows)


async def _pane_resize_chords(tmp: Path) -> ScenarioResult:
    """``ctrl+w`` + ``+`` / ``-`` / ``=`` resize, and the minimum-size warning.

    ``+`` and ``-`` drive ``WindowFlows.resize_pane``'s *horizontal* axis, i.e.
    a top/bottom ``:sp`` tree -- on a side-by-side ``:vs`` tree they find no
    matching split and take the "already at its minimum size" branch, which the
    scenario pins down explicitly at the end.
    """
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.editor.panes
        checks.append(Check("one_pane", 1, panes.leaf_count))
        await run_command(pilot, "vim")
        checks.append(Check("in_vim", "vim", app.editor.keymaps.name))
        await run_command(pilot, "sp")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        checks.append(Check("sp_splits", 2, panes.leaf_count))
        checks.append(Check("equal_at_first", [0.5, 0.5], _pane_sizes(app)))
        # ctrl+w + grows the active pane
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("chord_armed", True, app.editor.window_flows.window_pending))
        await pilot.press("+")
        await pilot.pause()
        checks.append(Check("chord_consumed", False,
                            app.editor.window_flows.window_pending))
        sizes = _pane_sizes(app)
        checks.append(Check("plus_grew_active", True, sizes[1] > sizes[0]))
        checks.append(Check("fractions_sum_to_one", 1.0, round(sum(sizes), 3)))
        # ctrl+w = puts every split back to an even share
        await pilot.press("ctrl+w")
        await pilot.press("=")
        await pilot.pause()
        checks.append(Check("equalized", [0.5, 0.5], _pane_sizes(app)))
        # shrink the active pane until the minimum-share guard fires
        warned = False
        for _ in range(12):
            await pilot.press("ctrl+w")
            await pilot.press("-")
            await pilot.pause()
            if "already at its minimum size" in message_text(app):
                warned = True
                break
        checks.append(Check("minimum_warned", True, warned))
        checks.append(Check("stopped_at_minimum",
                            [round(1 - MIN_FRACTION, 3), round(MIN_FRACTION, 3)],
                            _pane_sizes(app)))
        # ctrl+w q closes the pane, then warns when only one is left
        await pilot.press("ctrl+w")
        await pilot.press("q")
        await wait_until(pilot, lambda: panes.leaf_count == 1)
        checks.append(Check("closed", 1, panes.leaf_count))
        await pilot.press("ctrl+w")
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("last_pane_kept", 1, panes.leaf_count))
        checks.append(Check("last_pane_warned", True,
                            "only one pane open" in message_text(app)))
        # a side-by-side tree has no horizontal split: + cannot resize it
        await run_command(pilot, "vs")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        await pilot.press("ctrl+w")
        await pilot.press("+")
        await pilot.pause()
        checks.append(Check("vertical_tree_unchanged", [0.5, 0.5], _pane_sizes(app)))
        checks.append(Check("vertical_tree_warned", True,
                            "already at its minimum size" in message_text(app)))
        await run_command(pilot, "only")
        await wait_until(pilot, lambda: panes.leaf_count == 1)
        checks.append(Check("one_pane_again", 1, panes.leaf_count))
        await run_command(pilot, "vsc")
        checks.append(Check("keymap_restored", "vsc", app.editor.keymaps.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("pane_resize_chords", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("explorer_navigate_and_esc", _explorer_navigate_and_esc, ("explorer",)),
    Scenario("open_directory_switches_workspace", _open_directory_switches_workspace,
             ("files", "explorer")),
    Scenario("pane_resize_chords", _pane_resize_chords, ("panes",)),
]
