"""File tree / resource explorer (Textual Tree widget).

The tree owns the whole explorer experience: navigation, the vim-style file
operations (``a``/``A``/``r``/``d``) and the prompt flows behind them.  It is
constructed with concrete collaborators only -- the document session, the
workspace and the prompt bar -- plus the few editor callbacks it triggers
(opening a file, focusing the editor, the vim ``ctrl+w`` chord).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from rich.text import Text
from textual.events import Key
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from yate.services.workspace import IGNORED_NAMES, Workspace
from yate.session import EditorSession

from . import theme
from .commandline import PromptBar
from .icons import icon_for_path

#: data attached to a tree node: the path it represents (None = placeholder)
NodeData = Path | None


class ExplorerTree(Tree[NodeData]):
    """Directory tree with Nerd Font glyphs, lazy-loaded on expand."""

    DEFAULT_CSS = """
    ExplorerTree {
        background: $surface;
        border-right: tall $primary 20%;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        session: EditorSession,
        workspace: Workspace,
        prompt: PromptBar,
        *,
        open_path: Callable[[Path], None],
        focus_editor: Callable[[], None],
        window_prefix: Callable[[Key], bool],
        **kwargs: Any,
    ) -> None:
        # The root node shows the open folder name; refresh_tree() fills it in.
        super().__init__(Text(""), **kwargs)
        self.session = session
        self.workspace = workspace
        self.prompt = prompt
        self.open_path = open_path
        self.focus_editor = focus_editor
        self.window_prefix = window_prefix
        self.show_root = True
        self.guide_depth = 2
        #: last node the user selected (opened); survives refresh_tree even
        #: when the tree lost focus (Textual resets cursor_line to -1 then)
        self._last_selected: Path | None = None
        #: pending prompt target of the create / rename / delete flow
        self._target: Optional[Path] = None
        self._is_dir = False
        # Tree's auto_expand toggles on every select, which would cancel the
        # explicit toggle in on_tree_node_selected (l/enter would do nothing)
        self.auto_expand = False

    # --------------------------------------------------------------- data

    def _expanded_paths(self) -> set[Path]:
        """Collect the paths of all currently expanded directory nodes."""
        out: set[Path] = set()

        def walk(node: TreeNode[NodeData]) -> None:
            if node.is_expanded and isinstance(node.data, Path):
                out.add(node.data)
            for child in node.children:
                walk(child)

        walk(self.root)
        return out

    def refresh_tree(self) -> None:
        """(Re)build the tree from the workspace root (theme aware).

        The expansion state of all directories survives the rebuild, and
        the cursor stays on the same path (clamped by Textual if the node
        vanished, which would otherwise jump it to the last visible row).
        """
        t = theme.active()
        self.styles.background = t.panel
        root_path = self.workspace.root
        if root_path is None:
            self.clear()
            self.root.label = Text(" no folder open", style=t.fg_dim)
            self.root.data = None
            self.refresh()
            return
        expanded = self._expanded_paths()
        # prefer the last opened file (mouse clicks do not move the tree
        # cursor, and the cursor is even reset when the tree loses focus)
        cursor_path = self._last_selected or self._cursor_path()
        self.clear()
        self.root.label = self._label(root_path, True, True)
        self.root.data = root_path
        self._load_children(self.root, root_path, expanded)
        self.root.expand()
        if cursor_path is not None:
            # node._line is stale until Textual recomputes the tree lines,
            # so restore the cursor after the next layout pass
            self.call_after_refresh(self._restore_cursor, cursor_path)
        self.refresh()

    def _restore_cursor(self, path: Path) -> None:
        line = self._line_of(path)
        if line is not None:
            self.cursor_line = line

    def _line_of(self, path: Path) -> int | None:
        """Visible row index of the node representing *path*.

        Matches Textual's rendering order: depth-first over expanded nodes.
        Computed from the model so it is valid before the next layout pass.
        """
        found: list[int] = []
        counter = -1

        def walk(node: TreeNode[NodeData]) -> None:
            nonlocal counter
            counter += 1
            if isinstance(node.data, Path) and node.data == path:
                found.append(counter)
                return
            if node.is_expanded:
                for child in node.children:
                    walk(child)

        walk(self.root)
        return found[0] if found else None

    def _find_node(
        self, node: TreeNode[NodeData], path: Path
    ) -> TreeNode[NodeData] | None:
        """Depth-first search for the node representing *path*."""
        for child in node.children:
            if isinstance(child.data, Path) and child.data == path:
                return child
            if child.is_expanded:
                found = self._find_node(child, path)
                if found is not None:
                    return found
        return None

    def _load_children(
        self,
        node: TreeNode[NodeData],
        directory: Path,
        expanded: set[Path] | None = None,
    ) -> None:
        placeholder = Text("", style=theme.active().fg_dim)
        for entry in self.workspace.list_dir(directory):
            if entry.name in IGNORED_NAMES:
                continue
            label = self._label(entry.path, entry.is_dir, False)
            child = node.add(label, data=entry.path, allow_expand=entry.is_dir)
            if entry.is_dir:
                # placeholder so the node shows as expandable before load
                child.add(placeholder, data=None)
                if expanded is not None and entry.path in expanded:
                    # load synchronously and recurse so directories at ANY
                    # depth keep their expansion (the async lazy-load path
                    # below has no `expanded` set and would collapse them)
                    child.remove_children()
                    self._load_children(child, entry.path, expanded)
                    child.expand()

    @staticmethod
    def _label(path: Path, is_dir: bool, expanded: bool) -> Text:
        t = theme.active()
        name = path.name or str(path)
        icon = icon_for_path(name, is_dir, expanded)
        text = Text()
        text.append(icon + " ", style=t.accent if is_dir else t.fg_bright)
        text.append(name, style=t.accent if is_dir else t.fg)
        return text

    # ------------------------------------------------------------- events

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[NodeData]) -> None:
        """Lazily load a directory's children the first time it expands."""
        node = event.node
        path = node.data
        if not isinstance(path, Path) or not path.is_dir():
            return
        # Lazy load: replace the empty placeholder with real children.
        if len(node.children) == 1 and node.children[0].data is None:
            node.remove_children()
            self._load_children(node, path)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[NodeData]) -> None:
        """Keep the lazy-load placeholder trick consistent after collapsing."""
        node = event.node
        path = node.data
        if isinstance(path, Path) and path.is_dir() and not node.children:
            node.add(Text("", style=theme.active().fg_dim), data=None)

    def on_tree_node_selected(self, event: Tree.NodeSelected[NodeData]) -> None:
        """Enter: toggle directories, open files in the editor."""
        path = event.node.data
        if not isinstance(path, Path):
            return
        self._last_selected = path
        if path.is_dir():
            event.node.toggle()
            return
        self.open_path(path)
        self.focus_editor()

    # ------------------------------------------------------- vim-style keys

    @staticmethod
    def _is_plain_typing(event: Key) -> bool:
        """True for printable single characters (consume, do not forward)."""
        key = event.key
        if "+" in key:
            return False
        if len(key) == 1 and key.isprintable():
            return True
        char = event.character
        return bool(char and len(char) == 1 and char.isprintable())

    def on_key(self, event: Key) -> None:
        """Vim-style navigation plus file operations (a/A/r/d)."""
        # the vim ctrl+w window chord runs before everything else (same as
        # the editor view): the pending hjkl would otherwise be eaten by
        # the navigation handlers below
        if self.window_prefix(event):
            event.stop()
            event.prevent_default()
            return
        key = event.key

        def consume() -> None:
            event.stop()
            event.prevent_default()

        if key == "j":
            consume()
            self.action_cursor_down()
        elif key == "k":
            consume()
            self.action_cursor_up()
        elif key == "l":
            consume()
            self.action_select_cursor()
        elif key == "h":
            consume()
            node = self.cursor_node
            if node is not None and node.is_expanded:
                node.collapse()
            else:
                self.action_cursor_parent()
        elif key == "a":
            consume()
            self.prompt_new_file(self._cursor_path())
        elif key == "A":
            consume()
            self.prompt_new_dir(self._cursor_path())
        elif key == "H":
            consume()
            self.workspace.show_hidden = not self.workspace.show_hidden
            self.refresh_tree()
            self.prompt.write(
                f"hidden files {'shown' if self.workspace.show_hidden else 'hidden'}"
            )
        elif key == "r":
            consume()
            self.prompt_rename(self._cursor_path())
        elif key in ("d", "delete"):
            consume()
            self.prompt_delete(self._cursor_path())
        elif key == "escape":
            consume()
            self.focus_editor()
        elif self._is_plain_typing(event):
            # consume plain typing so it does not leak into the editor
            consume()

    def _cursor_path(self) -> Path | None:
        """Path of the node under the cursor (``None`` for placeholders)."""
        node = self.cursor_node
        data = node.data if node is not None else None
        return data if isinstance(data, Path) else None

    # ----------------------------------------------------- prompt flows

    def prompt_new_file(self, directory: Optional[Path]) -> None:
        """``a``: prompt for a new file next to / inside *directory*."""
        self._prompt_new(directory, is_dir=False)

    def prompt_new_dir(self, directory: Optional[Path]) -> None:
        """``A``: prompt for a new folder next to / inside *directory*."""
        self._prompt_new(directory, is_dir=True)

    def _prompt_new(self, directory: Optional[Path], *, is_dir: bool) -> None:
        if directory is None:
            self.prompt.write("select a file or folder first", kind="warn")
            return
        # on a file entry the sibling directory is the creation target
        if not directory.is_dir():
            directory = directory.parent
        mode = "new_dir" if is_dir else "new_file"
        # A created file opens for editing -> focus the editor; a folder
        # keeps the explorer focused.
        refocus = self._refocus_explorer if is_dir else self.focus_editor
        if not self.prompt.activate(
            mode,
            placeholder=f"created inside {directory.name}/",
            on_submit=self.submit_create,
            refocus=refocus,
        ):
            return
        self._target = directory
        self._is_dir = is_dir

    def prompt_rename(self, path: Optional[Path]) -> None:
        """``r``: prompt for a new name for *path*."""
        if path is None:
            self.prompt.write("select a file or folder first", kind="warn")
            return
        if not self.prompt.activate(
            "rename",
            initial=path.name,
            placeholder=f"renaming {path.name}",
            on_submit=self.submit_rename,
            refocus=self._refocus_explorer,
        ):
            return
        self._target = path

    def prompt_delete(self, path: Optional[Path]) -> None:
        """``d``: prompt for the confirmation that deletes *path*."""
        if path is None:
            self.prompt.write("select a file or folder first", kind="warn")
            return
        kind = "folder" if path.is_dir() else "file"
        if not self.prompt.activate(
            "delete",
            placeholder=f"{kind} {path.name} — type y to confirm",
            on_submit=self.submit_delete,
            refocus=self._refocus_explorer,
        ):
            return
        self._target = path

    def _refocus_explorer(self) -> None:
        if self.workspace.root is not None:
            self.focus()

    # ----------------------------------------------------------- submission

    def submit_create(self, name: str) -> None:
        """Prompt submitted: create the pending entry."""
        directory = self._target
        if directory is None:
            return
        try:
            target = self.workspace.create_entry(directory, name, is_dir=self._is_dir)
        except ValueError as exc:
            self.prompt.write(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self.prompt.write(str(exc), kind="error")
            return
        except OSError as exc:
            self.prompt.write(f"create failed: {exc}", kind="error")
            return
        self.refresh_tree()
        self.prompt.write(f"created {target.name}", kind="ok")
        if not self._is_dir:
            # VS Code behavior: a new file opens right away
            self.open_path(target)

    def submit_rename(self, name: str) -> None:
        """Prompt submitted: rename the pending path."""
        path = self._target
        if path is None:
            return
        try:
            new_path = self.workspace.rename_entry(path, name)
        except ValueError as exc:
            self.prompt.write(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self.prompt.write(str(exc), kind="error")
            return
        except OSError as exc:
            self.prompt.write(f"rename failed: {exc}", kind="error")
            return
        # keep tabs pointing at the moved document
        self.session.retarget(path, new_path)
        self.refresh_tree()
        self.prompt.write(f"renamed to {new_path.name}", kind="ok")

    def submit_delete(self, confirm: str) -> None:
        """Prompt submitted: delete the pending path when confirmed."""
        path = self._target
        if path is None:
            return
        if confirm.strip().lower() not in ("y", "yes"):
            self.prompt.write("delete cancelled")
            return
        try:
            self.workspace.remove_entry(path)
        except OSError as exc:
            self.prompt.write(f"delete failed: {exc}", kind="error")
            return
        closed = self.session.close_under(path)
        self.refresh_tree()
        if closed:
            self.prompt.write(
                f"deleted {path.name} (closed {len(closed)} open tab(s))", kind="ok"
            )
        else:
            self.prompt.write(f"deleted {path.name}", kind="ok")
