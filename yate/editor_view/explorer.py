"""File tree / resource explorer (Textual Tree widget)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.events import Key
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from . import theme
from .icons import icon_for_path
from ..services.workspace import IGNORED_NAMES

if TYPE_CHECKING:
    from yate.app import YateApp

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

    def __init__(self, yate: YateApp, **kwargs: Any) -> None:
        # The root node shows the open folder name; refresh_tree() fills it in.
        super().__init__(Text(""), **kwargs)
        self.yate = yate
        self.show_root = True
        self.guide_depth = 2
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

        The expansion state of all directories survives the rebuild.
        """
        t = theme.active()
        self.styles.background = t.panel
        root_path = self.yate.workspace.root
        if root_path is None:
            self.clear()
            self.root.label = Text(" no folder open", style=t.fg_dim)
            self.root.data = None
            self.refresh()
            return
        expanded = self._expanded_paths()
        self.clear()
        self.root.label = self._label(root_path, True, True)
        self.root.data = root_path
        self._load_children(self.root, root_path, expanded)
        self.root.expand()
        self.refresh()

    def _load_children(
        self,
        node: TreeNode[NodeData],
        directory: Path,
        expanded: set[Path] | None = None,
    ) -> None:
        placeholder = Text("", style=theme.active().fg_dim)
        for entry in self.yate.workspace.list_dir(directory):
            if entry.name in IGNORED_NAMES:
                continue
            label = self._label(entry.path, entry.is_dir, False)
            child = node.add(label, data=entry.path, allow_expand=entry.is_dir)
            if entry.is_dir:
                # placeholder so the node shows as expandable before load
                child.add(placeholder, data=None)
                if expanded is not None and entry.path in expanded:
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
        if path.is_dir():
            event.node.toggle()
            return
        self.yate.open_path(path)
        self.yate.focus_editor()

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
        if self.yate.try_window_prefix(event):
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
            self.yate.explorer_new_file_prompt(self._cursor_path())
        elif key == "A":
            consume()
            self.yate.explorer_new_dir_prompt(self._cursor_path())
        elif key == "r":
            consume()
            self.yate.explorer_rename_prompt(self._cursor_path())
        elif key in ("d", "delete"):
            consume()
            self.yate.explorer_delete_prompt(self._cursor_path())
        elif key == "escape":
            consume()
            self.yate.focus_editor()
        elif self._is_plain_typing(event):
            # consume plain typing so it does not leak into the editor
            consume()

    def _cursor_path(self) -> Path | None:
        """Path of the node under the cursor (``None`` for placeholders)."""
        node = self.cursor_node
        data = node.data if node is not None else None
        return data if isinstance(data, Path) else None
