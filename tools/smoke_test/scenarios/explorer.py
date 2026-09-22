"""File explorer scenarios (tag: ``explorer``).

The explorer is opened by starting yate on a *directory*: that sets the
workspace root and shows the sidebar.  Tree navigation uses the same
``j`` / ``a`` / ``r`` / ``d`` keys a user would press; the helper
``_walk_to`` just presses ``j`` until the wanted entry is under the cursor
so the scenario does not depend on the tree's exact row order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import run_command, type_text, wait_until

__all__ = ["SCENARIOS"]


async def _walk_to(pilot: Any, app: Any, name: str, limit: int = 12) -> bool:
    """Move the tree cursor down until the node named *name* is selected."""
    tree = app.editor.explorer_tree
    if tree is None:
        return False
    for _ in range(limit):
        node = tree.cursor_node
        data = node.data if node is not None else None
        if isinstance(data, Path) and data.name == name:
            return True
        await pilot.press("j")
        await pilot.pause()
    return False


async def _explorer_visibility_focus(tmp: Path) -> ScenarioResult:
    """ctrl+b toggles the sidebar, ctrl+e / ctrl+1 move the focus."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        tree = app.editor.explorer_tree
        sidebar = app.editor.sidebar
        assert tree is not None and sidebar is not None
        checks.append(Check("visible_on_dir_open", True, app.editor.explorer_visible))
        checks.append(Check("sidebar_shown", True, tree.display))
        # Compare the folder name, not its absolute path (temp dirs differ).
        checks.append(Check("root", tmp.resolve().name,
                            app.editor.workspace.root.name
                            if app.editor.workspace.root else None))
        await pilot.press("ctrl+b")
        await pilot.pause()
        checks.append(Check("hidden", False, app.editor.explorer_visible))
        checks.append(Check("sidebar_hidden", False, sidebar.display))
        await pilot.press("ctrl+b")
        await pilot.pause()
        checks.append(Check("shown_again", True, app.editor.explorer_visible))
        await pilot.press("ctrl+e")
        await pilot.pause()
        checks.append(Check("explorer_focused", True,
                            app.focused is app.editor.explorer_tree))
        await pilot.press("ctrl+1")
        await pilot.pause()
        checks.append(Check("editor_focused", True,
                            app.focused is app.editor.panes.active_view))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("explorer_visibility_focus", checks, rows)


async def _explorer_crud(tmp: Path) -> ScenarioResult:
    """a (new file), r (rename), d (delete) round-trip through the prompt."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+e")
        await pilot.pause()
        checks.append(Check("on_root", True,
                            await _walk_to(pilot, app, tmp.name)))
        # --- new file
        await pilot.press("a")
        await pilot.pause()
        checks.append(Check("new_file_mode", "new_file",
                            app.editor.prompt_bar.active_mode
                            if app.editor.prompt_bar else None))
        await type_text(pilot, "b.txt")
        await pilot.press("enter")
        await wait_until(pilot, lambda: (tmp / "b.txt").exists())
        checks.append(Check("created", True, (tmp / "b.txt").exists()))
        checks.append(Check("opened_new_file", "b.txt",
                            app.editor.session.doc.name))
        # --- rename (the prompt is pre-filled with the old name)
        await pilot.press("ctrl+e")
        await pilot.pause()
        await _walk_to(pilot, app, "b.txt")
        await pilot.press("r")
        await pilot.pause()
        checks.append(Check("rename_mode", "rename",
                            app.editor.prompt_bar.active_mode
                            if app.editor.prompt_bar else None))
        for _ in range(len("b.txt")):
            await pilot.press("backspace")
        await pilot.pause()
        await type_text(pilot, "c.txt")
        await pilot.press("enter")
        await wait_until(pilot, lambda: (tmp / "c.txt").exists())
        checks.append(Check("renamed", True, (tmp / "c.txt").exists()))
        checks.append(Check("old_gone", False, (tmp / "b.txt").exists()))
        # --- delete (asks for confirmation)
        await pilot.press("ctrl+e")
        await pilot.pause()
        await _walk_to(pilot, app, "c.txt")
        await pilot.press("d")
        await pilot.pause()
        checks.append(Check("delete_mode", "delete",
                            app.editor.prompt_bar.active_mode
                            if app.editor.prompt_bar else None))
        await type_text(pilot, "y")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("deleted", False, (tmp / "c.txt").exists()))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("explorer_crud", checks, rows)


async def _explorer_delete_open_folder(tmp: Path) -> ScenarioResult:
    """Deleting a folder closes the tabs that live under it."""
    sub = tmp / "sub"
    sub.mkdir()
    (sub / "x.txt").write_text("x\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        # setup: open the file that is about to lose its folder
        app.editor.open_path(sub / "x.txt")
        await wait_until(pilot, lambda: app.editor.session.doc.name == "x.txt")
        checks.append(Check("opened", "x.txt", app.editor.session.doc.name))
        checks.append(Check("two_docs", 2, len(app.editor.session.docs)))
        await pilot.press("ctrl+e")
        await pilot.pause()
        checks.append(Check("on_folder", True, await _walk_to(pilot, app, "sub")))
        await pilot.press("d")
        await pilot.pause()
        await type_text(pilot, "y")
        await pilot.press("enter")
        await wait_until(pilot, lambda: not sub.exists())
        checks.append(Check("folder_gone", False, sub.exists()))
        checks.append(Check("tab_closed", 1, len(app.editor.session.docs)))
        checks.append(Check("fallback_unnamed", None, app.editor.session.doc.path))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("explorer_delete_open_folder", checks, rows)


async def _explorer_hidden_toggle(tmp: Path) -> ScenarioResult:
    """:set show_hidden=on and the ``H`` key reveal dotfiles."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp / ".secret.txt").write_text("s\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        tree = app.editor.explorer_tree
        assert tree is not None
        checks.append(Check("hidden_by_default", False,
                            app.editor.workspace.show_hidden))
        checks.append(Check("visible_children", 1, len(list(tree.root.children))))
        await run_command(pilot, "set show_hidden=on")
        checks.append(Check("shown_via_set", True, app.editor.workspace.show_hidden))
        checks.append(Check("children_with_hidden", 2,
                            len(list(tree.root.children))))
        await pilot.press("ctrl+e")
        await pilot.pause()
        await pilot.press("H")
        await pilot.pause()
        checks.append(Check("hidden_via_key", False,
                            app.editor.workspace.show_hidden))
        checks.append(Check("children_again", 1, len(list(tree.root.children))))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("explorer_hidden_toggle", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("explorer_visibility_focus", _explorer_visibility_focus, ("explorer",)),
    Scenario("explorer_crud", _explorer_crud, ("explorer",)),
    Scenario("explorer_delete_open_folder", _explorer_delete_open_folder,
             ("explorer",)),
    Scenario("explorer_hidden_toggle", _explorer_hidden_toggle, ("explorer",)),
]
