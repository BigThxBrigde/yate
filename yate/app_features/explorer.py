"""Explorer file operations behind the prompt bar (create/rename/delete).

Extracted from :class:`yate.app.YateApp` as a self-contained feature: the
prompt flows, the pending-target state and the actual workspace mutations
all live here.  The application supplies the host capabilities (opening
documents, closing affected tabs, refreshing the tree, activating prompts)
through :class:`ExplorerHost`; the explorer widget drives the feature
through :class:`ExplorerOps`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from textual.events import Key

from yate.editor_core import Document
from yate.editor_lsp import LspManager
from yate.services.workspace import Workspace


class ExplorerOps(Protocol):
    """The explorer facade :class:`~yate.editor_view.explorer.ExplorerTree`
    drives (implemented by :class:`ExplorerFeature`)."""

    @property
    def workspace(self) -> Workspace: ...

    def message(self, text: str, kind: str = "info") -> None: ...

    def open_path_later(self, path: Path) -> None: ...

    def focus_editor(self) -> None: ...

    def try_window_prefix(self, event: Key) -> bool: ...

    def prompt_new_file(self, directory: Optional[Path]) -> None: ...

    def prompt_new_dir(self, directory: Optional[Path]) -> None: ...

    def prompt_rename(self, path: Optional[Path]) -> None: ...

    def prompt_delete(self, path: Optional[Path]) -> None: ...


class ExplorerHost(Protocol):
    """What :class:`ExplorerFeature` needs from the application."""

    lsp: LspManager

    def message(self, text: str, kind: str = "info") -> None: ...

    def open_path_later(self, path: Path) -> None: ...

    def focus_editor(self) -> None: ...

    def try_window_prefix(self, event: Key) -> bool: ...

    def open_document(self, path: Path) -> Optional[Document]: ...

    def refresh_explorer(self) -> None: ...

    def activate_prompt(self, mode: str, *, placeholder: str = "",
                        initial: str = "") -> bool: ...

    def close_documents_under(self, path: Path) -> None: ...

    def retarget_document(self, old: Path, new: Path) -> None: ...


class ExplorerFeature:
    """Create / rename / delete flows behind the explorer prompt bar."""

    def __init__(self, host: ExplorerHost, workspace: Workspace) -> None:
        self._host = host
        self._workspace = workspace
        #: Pending prompt target; the submit handler dispatches on it.
        self._target: Optional[Path] = None
        self._is_dir = False

    # ---------------------------------------------------------- ExplorerOps

    @property
    def workspace(self) -> Workspace:
        """The workspace the tree renders and mutates."""
        return self._workspace

    def message(self, text: str, kind: str = "info") -> None:
        self._host.message(text, kind)

    def open_path_later(self, path: Path) -> None:
        self._host.open_path_later(path)

    def focus_editor(self) -> None:
        self._host.focus_editor()

    def try_window_prefix(self, event: Key) -> bool:
        return self._host.try_window_prefix(event)

    @property
    def target_is_dir(self) -> bool:
        """Whether the pending prompt target is a directory (submit refocus)."""
        return self._is_dir

    # -------------------------------------------------------------- prompts

    def prompt_new_file(self, directory: Optional[Path]) -> None:
        self._prompt_new(directory, is_dir=False)

    def prompt_new_dir(self, directory: Optional[Path]) -> None:
        self._prompt_new(directory, is_dir=True)

    def _prompt_new(self, directory: Optional[Path], *, is_dir: bool) -> None:
        if directory is None:
            self._host.message("select a file or folder first", kind="warn")
            return
        # on a file entry the sibling directory is the creation target
        if not directory.is_dir():
            directory = directory.parent
        mode = "new_dir" if is_dir else "new_file"
        if not self._host.activate_prompt(
            mode, placeholder=f"created inside {directory.name}/"
        ):
            return
        self._target = directory
        self._is_dir = is_dir

    def prompt_rename(self, path: Optional[Path]) -> None:
        if path is None:
            self._host.message("select a file or folder first", kind="warn")
            return
        if not self._host.activate_prompt(
            "rename", initial=path.name, placeholder=f"renaming {path.name}"
        ):
            return
        self._target = path

    def prompt_delete(self, path: Optional[Path]) -> None:
        if path is None:
            self._host.message("select a file or folder first", kind="warn")
            return
        kind = "folder" if path.is_dir() else "file"
        if not self._host.activate_prompt(
            "delete", placeholder=f"{kind} {path.name} — type y to confirm"
        ):
            return
        self._target = path

    # ----------------------------------------------------------- submission

    def submit_create(self, name: str) -> None:
        """Prompt submitted: create the pending entry."""
        directory = self._target
        if directory is None:
            return
        try:
            target = self._workspace.create_entry(
                directory, name, is_dir=self._is_dir)
        except ValueError as exc:
            self._host.message(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self._host.message(str(exc), kind="error")
            return
        except OSError as exc:
            self._host.message(f"create failed: {exc}", kind="error")
            return
        self._host.refresh_explorer()
        self._host.message(f"created {target.name}", kind="ok")
        if not self._is_dir:
            # VS Code behavior: a new file opens right away
            self._host.open_document(target)

    def submit_rename(self, name: str) -> None:
        """Prompt submitted: rename the pending path."""
        path = self._target
        if path is None:
            return
        try:
            new_path = self._workspace.rename_entry(path, name)
        except ValueError as exc:
            self._host.message(f"invalid name: {exc}", kind="error")
            return
        except FileExistsError as exc:
            self._host.message(str(exc), kind="error")
            return
        except OSError as exc:
            self._host.message(f"rename failed: {exc}", kind="error")
            return
        # keep tabs pointing at the moved document
        self._host.retarget_document(path, new_path)
        self._host.refresh_explorer()
        self._host.message(f"renamed to {new_path.name}", kind="ok")

    def submit_delete(self, confirm: str) -> None:
        """Prompt submitted: delete the pending path when confirmed."""
        path = self._target
        if path is None:
            return
        if confirm.strip().lower() not in ("y", "yes"):
            self._host.message("delete cancelled")
            return
        try:
            self._workspace.remove_entry(path)
        except OSError as exc:
            self._host.message(f"delete failed: {exc}", kind="error")
            return
        self._host.close_documents_under(path)
        self._host.refresh_explorer()
        self._host.message(f"deleted {path.name}", kind="ok")
