"""Explorer / workspace tree headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from pathlib import Path
from textual.widgets.tree import TreeNode
from yate.app import YateApp

def test_explorer_open_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "a.txt").write_text("alpha\n", encoding="utf-8")
        (root / "b.py").write_text("print('beta')\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert explorer.display
            # ctrl+e focuses the explorer; j moves down; l opens
            await pilot.press("ctrl+e")
            assert app.focused is app.editor.explorer_tree
            await pilot.press("j", "l")
            await pilot.pause()
            opened = {d.name for d in app.editor.session.docs if d.path is not None}
            assert opened & {"a.txt", "b.py"}
            # esc returns focus to the editor
            await pilot.press("escape")
            assert app.focused is app.editor.panes.active_view

    asyncio.run(scenario())


# -------------------------------------------------------- workspace file walking


def test_collects_nested_files_and_prunes_noise(tmp_path: Path) -> None:
    from yate.services.workspace import Workspace

    root = tmp_path
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (root / "src" / "util.py").write_text("y = 2\n", encoding="utf-8")
    (root / "readme.md").write_text("# hi\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "junk.pyc").write_text("x", encoding="utf-8")

    ws = Workspace(root)
    names = {p.name for p in ws.walk_files()}
    assert names == {"main.py", "util.py", "readme.md"}


def test_no_root_returns_empty() -> None:
    from yate.services.workspace import Workspace

    assert Workspace(None).walk_files() == []


def test_limit(tmp_path: Path) -> None:
    from yate.services.workspace import Workspace

    root = tmp_path
    for i in range(10):
        (root / f"f{i}.txt").write_text("x\n", encoding="utf-8")
    assert len(Workspace(root).walk_files(limit=3)) == 3


# ----------------------------------------------------------------- fuzzy match


def test_empty_query_matches() -> None:
    from yate.editor_view.palette import fuzzy_match

    assert fuzzy_match("", "anything") is not None


def test_subsequence_order() -> None:
    from yate.editor_view.palette import fuzzy_match

    assert fuzzy_match("wt", "write") is not None
    assert fuzzy_match("tw", "write") is None
    assert fuzzy_match("bp", "bprev") is not None
    assert fuzzy_match("xyz", "bprev") is None


def test_consecutive_ranks_better_than_gap() -> None:
    from yate.editor_view.palette import fuzzy_match

    tight = fuzzy_match("set", "set")
    gappy = fuzzy_match("set", "reset")  # r-e-**s**-**e**-**t**: gap match
    assert tight is not None and gappy is not None
    assert tight[0] < gappy[0]


def test_returns_matched_indices() -> None:
    from yate.editor_view.palette import fuzzy_match

    match = fuzzy_match("bprev", "bprev")
    assert match is not None
    assert match[1] == [0, 1, 2, 3, 4]


# ----------------------------------------------------------- explorer operations


def test_file_target_starts_with_explorer_hidden(tmp_path: Path) -> None:
    """A file argument focuses on editing: the explorer starts hidden
    (Ctrl+B / :explorer reveals it); a directory starts with it shown,
    and a not-yet-created file path behaves like a file argument."""

    async def scenario() -> None:
        root = tmp_path
        alpha = root / "alpha.txt"
        alpha.write_text("alpha\n", encoding="utf-8")

        app = YateApp(target=alpha)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert not explorer.display
            # the workspace root is still the file's parent, so showing
            # the explorer later works without reopening anything
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert explorer.display

        app_dir = YateApp(target=root)
        async with app_dir.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer_dir = app_dir.editor.explorer_tree
            assert explorer_dir is not None
            assert explorer_dir.display

        app_new = YateApp(target=root / "brand_new.txt")
        async with app_new.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer_new = app_new.editor.explorer_tree
            assert explorer_new is not None
            assert not explorer_new.display

    asyncio.run(scenario())


def test_ctrl_b_toggles_explorer(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert explorer.display
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert not explorer.display
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert explorer.display

    asyncio.run(scenario())


def test_new_file_and_folder_from_explorer(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "seed.txt").write_text("seed\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # cursor sits on the root: "a" creates a file at the top level
            await pilot.press("ctrl+e")
            await pilot.press("a")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "new_file"
            await pilot.press(*"made.txt")
            await pilot.press("enter")
            await pilot.pause()
            assert (root / "made.txt").exists()
            # new files open right away (VS Code behavior)
            opened = {d.name for d in app.editor.session.docs if d.path is not None}
            assert "made.txt" in opened
            # "A" creates a folder; creation target is the selected dir
            await pilot.press("ctrl+e")
            await pilot.press("A")
            await pilot.pause()
            assert prompt_bar.active_mode == "new_dir"
            await pilot.press(*"subdir")
            await pilot.press("enter")
            await pilot.pause()
            assert (root / "subdir").is_dir()

    asyncio.run(scenario())


def test_open_nested_file_keeps_expansion_and_cursor(tmp_path: Path) -> None:
    """Regression: refresh_tree collapsed second-level directories and
    the cursor jumped to the last row after opening a nested file."""

    async def scenario() -> None:
        root = tmp_path
        sub = root / "sub"
        deep = sub / "deep"
        deep.mkdir(parents=True)
        (root / "top.txt").write_text("t\n", encoding="utf-8")
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        (deep / "leaf.txt").write_text("l\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None

            def find(
                node: TreeNode[Path | None], name: str
            ) -> TreeNode[Path | None] | None:
                for c in node.children:
                    if c.data is not None and Path(c.data).name == name:
                        return c
                    if c.is_expanded:
                        r = find(c, name)
                        if r is not None:
                            return r
                return None

            # expand sub, then deep (two levels), then open leaf.txt
            sub_node = find(tree.root, "sub")
            assert sub_node is not None
            tree.select_node(sub_node)
            await pilot.pause()
            await pilot.pause()
            deep_node = find(tree.root, "deep")
            assert deep_node is not None
            tree.select_node(deep_node)
            await pilot.pause()
            await pilot.pause()
            leaf = find(tree.root, "leaf.txt")
            assert leaf is not None
            tree.select_node(leaf)
            for _ in range(12):
                await pilot.pause()

            # sub AND deep must still be expanded after the refresh
            # triggered by opening the file
            assert sub_node.is_expanded, "first-level dir collapsed"
            assert deep_node.is_expanded, "nested dir collapsed"
            # cursor/highlight must sit on the opened file, not the
            # last row of the tree
            await pilot.press("ctrl+e")
            await pilot.pause()
            cur = tree.cursor_node
            assert cur is not None and cur.data is not None
            assert Path(cur.data).name == "leaf.txt"
            assert app.editor.session.doc.path is not None
            assert app.editor.session.doc.path.name == "leaf.txt"

    asyncio.run(scenario())


def test_rename_updates_open_document_path(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / "old.txt").write_text("data\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+e", "j", "l")  # focus, move, open old.txt
            await pilot.pause()
            doc = app.editor.session.doc
            assert doc.path is not None
            await pilot.press("ctrl+e")
            await pilot.press("j")  # cursor onto old.txt
            await pilot.press("r")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "rename"
            assert prompt_bar.input.value == "old.txt"
            await pilot.press(*"new.txt")
            await pilot.press("enter")
            await pilot.pause()
            assert not (root / "old.txt").exists()
            assert (root / "new.txt").exists()
            assert app.editor.session.doc.path == (root / "new.txt").resolve()

    asyncio.run(scenario())


def test_delete_requires_confirmation(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        victim = root / "gone.txt"
        victim.write_text("bye\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+e", "j")
            await pilot.press("d")
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            assert prompt_bar.active_mode == "delete"
            assert victim.exists()
            # anything but y cancels
            await pilot.press("n")
            await pilot.press("enter")
            await pilot.pause()
            assert victim.exists()
            # d again, confirm with y
            await pilot.press("ctrl+e", "j", "d")
            await pilot.press(*"y")
            await pilot.press("enter")
            await pilot.pause()
            assert not victim.exists()

    asyncio.run(scenario())


def test_refresh_tree_keeps_expanded_dirs(tmp_path: Path) -> None:
    from yate.editor_view.explorer import ExplorerTree

    async def scenario() -> None:
        # workspace stores the resolved root; on Windows TEMP may be an
        # 8.3 short name (e.g. RUNNER~1), so canonicalize before comparing
        root = tmp_path.resolve()
        sub = root / "sub"
        sub.mkdir()
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            explorer = app.editor.explorer_tree
            assert explorer is not None
            # expand "sub" via the tree: focus root, j to sub, l to expand
            await pilot.press("ctrl+e", "j", "l")
            await pilot.pause()
            sub_node = next(n for n in explorer.root.children
                            if isinstance(n.data, Path) and n.data == sub)
            assert sub_node.is_expanded
            # any refresh (e.g. opening a file elsewhere) must not collapse
            explorer.refresh_tree()
            sub_node2 = next(n for n in explorer.root.children
                             if isinstance(n.data, Path) and n.data == sub)
            assert sub_node2.is_expanded
            assert ExplorerTree in type(explorer).__mro__

    asyncio.run(scenario())


def test_slim_scrollbar_size(tmp_path: Path) -> None:
    """Issue IKINF3: the app CSS overrides the Widget default (2 cells) with
    a 1-cell vertical scrollbar on every scrollable widget."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            view = app.editor.panes.active_view
            assert view is not None
            assert view.styles.scrollbar_size_vertical == 1
            explorer = app.editor.explorer_tree
            assert explorer is not None
            assert explorer.styles.scrollbar_size_vertical == 1

    asyncio.run(scenario())


# ------------------------------------------------------ explorer filter smoke


def test_h_toggles_hidden_files_in_tree(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / ".hidden.txt").write_text("h\n", encoding="utf-8")
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None

            def shown() -> list[str]:
                return [
                    Path(c.data).name
                    for c in tree.root.children
                    if c.data is not None
                ]

            assert ".hidden.txt" not in shown()
            # hide the by-default-shown tree, then re-show it (focused)
            app.editor.run_command("explorer")
            for _ in range(4):
                await pilot.pause()
            app.editor.run_command("explorer")
            for _ in range(6):
                await pilot.pause()
            assert app.focused is tree
            await pilot.press("H")
            for _ in range(4):
                await pilot.pause()
            assert app.editor.workspace.show_hidden
            assert ".hidden.txt" in shown()
            await pilot.press("H")
            for _ in range(4):
                await pilot.pause()
            assert not app.editor.workspace.show_hidden
            assert ".hidden.txt" not in shown()

    asyncio.run(scenario())


def test_set_show_hidden_option_roundtrip(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path
        (root / ".dot").write_text("d\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("set show_hidden=on")
            await pilot.pause()
            assert app.editor.workspace.show_hidden
            tree = app.editor.explorer_tree
            assert tree is not None
            names = [
                Path(c.data).name
                for c in tree.root.children
                if c.data is not None
            ]
            assert ".dot" in names
            app.editor.run_command("set show_hidden=off")
            await pilot.pause()
            assert not app.editor.workspace.show_hidden

    asyncio.run(scenario())


def test_explorer_toggle_focuses_tree(tmp_path: Path) -> None:
    """Regression: re-opening the explorer must hand focus to the tree so
    keyboard navigation works without a mouse click (the tree is shown
    by default at startup, so toggle once to hide, once to re-show)."""

    async def scenario() -> None:
        root = tmp_path
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        (root / "b.txt").write_text("b\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None
            app.editor.run_command("explorer")  # hide (shown by default)
            for _ in range(4):
                await pilot.pause()
            assert not tree.display
            app.editor.run_command("explorer")  # re-show
            for _ in range(6):
                await pilot.pause()
            assert tree.display
            assert app.focused is tree
            # keyboard navigation actually works (j moves the cursor)
            line = tree.cursor_line
            await pilot.press("j")
            await pilot.pause()
            assert tree.cursor_line == line + 1

    asyncio.run(scenario())


def test_palette_entries_exclude_palette_command() -> None:
    """Regression: the palette must not list the palette command itself
    (opening it from inside would be a no-op recursion)."""
    from yate.config import FilePreviewConfig
    from yate.editor_view.palette import PaletteScreen

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            screen = PaletteScreen(
                "commands",
                workspace=app.editor.workspace,
                commands=app.editor.commands,
                actions=app.editor.actions,
                open_path=app.editor.document_flows.open_path_later,
                focus_editor=app.editor.focus_editor,
                execute_action=app.editor.execute_action,
                run_command=app.editor.run_command,
                refresh=app.editor.refresh_ui,
                preview=FilePreviewConfig(),
            )
            screen._build_command_entries()
            kinds = {name for name, _d, (_k, _n) in screen._entries}
            assert "quit" in kinds  # sanity: commands are listed
            assert "palette" not in kinds

    asyncio.run(scenario())


def test_tree_helper_line_of_and_find_node(tmp_path: Path) -> None:
    # Workspace resolves its root, which on Windows also expands 8.3
    # short names (GitHub runners expose TEMP as C:\Users\RUNNER~1).
    # Resolve here too or every node-path comparison below fails.
    async def scenario() -> None:
        root = tmp_path.resolve()
        sub = root / "sub"
        sub.mkdir()
        (sub / "inner.txt").write_text("i\n", encoding="utf-8")
        (root / "top.txt").write_text("t\n", encoding="utf-8")
        app = YateApp(target=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tree = app.editor.explorer_tree
            assert tree is not None
            top = sub.parent / "top.txt"
            # collapsed: sub's children are not visible
            assert tree._line_of(sub / "inner.txt") is None
            node = tree._find_node(tree.root, sub / "inner.txt")
            assert node is None
            # expand sub via select (toggle) and re-check
            snode = tree._find_node(tree.root, sub)
            assert snode is not None
            tree.select_node(snode)
            for _ in range(4):
                await pilot.pause()
            assert tree._find_node(tree.root, sub / "inner.txt") is not None
            # rows: 0=root, 1=sub, 2=inner.txt, 3=top.txt
            assert tree._line_of(sub / "inner.txt") == 2
            assert tree._line_of(top) == 3
            assert tree._line_of(root / "missing.txt") is None

    asyncio.run(scenario())
