"""Explorer file operations behind the prompt bar (create/rename/delete).

Extracted from :class:`yate.app.YateApp`: the prompt flows and the actual
workspace mutations.  Pending-target state (``_explorer_target`` /
``_explorer_is_dir``) stays on the app because the prompt submit handler
dispatches on it.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Optional

from yate.editor_core import SearchEngine
from yate.interfaces import AppProtocol

# Extracted YateApp collaborator: touching the app's private state (the
# pending explorer prompt target) is this module's contract (Python has no
# friend classes).
# pyright: reportPrivateUsage=false


def prompt_new_file(app: AppProtocol, directory: Optional[Path]) -> None:
    prompt_new(app, directory, is_dir=False)


def prompt_new_dir(app: AppProtocol, directory: Optional[Path]) -> None:
    prompt_new(app, directory, is_dir=True)


def prompt_new(
    app: AppProtocol, directory: Optional[Path], *, is_dir: bool
) -> None:
    if directory is None:
        app.message("select a file or folder first", kind="warn")
        return
    if app.prompt_bar is None:
        return
    # on a file entry the sibling directory is the creation target
    if not directory.is_dir():
        directory = directory.parent
    app._explorer_target = directory
    app._explorer_is_dir = is_dir
    app.prompt_bar.activate(
        "new_dir" if is_dir else "new_file",
        placeholder=f"created inside {directory.name}/",
    )


def prompt_rename(app: AppProtocol, path: Optional[Path]) -> None:
    if path is None:
        app.message("select a file or folder first", kind="warn")
        return
    if app.prompt_bar is None:
        return
    app._explorer_target = path
    app.prompt_bar.activate("rename", initial=path.name,
                            placeholder=f"renaming {path.name}")


def prompt_delete(app: AppProtocol, path: Optional[Path]) -> None:
    if path is None:
        app.message("select a file or folder first", kind="warn")
        return
    if app.prompt_bar is None:
        return
    app._explorer_target = path
    kind = "folder" if path.is_dir() else "file"
    app.prompt_bar.activate(
        "delete",
        placeholder=f"{kind} {path.name} — type y to confirm",
    )


def create(app: AppProtocol, directory: Optional[Path], name: str) -> None:
    if directory is None:
        return
    try:
        target = app.workspace.create_entry(
            directory, name, is_dir=app._explorer_is_dir)
    except ValueError as exc:
        app.message(f"invalid name: {exc}", kind="error")
        return
    except FileExistsError as exc:
        app.message(str(exc), kind="error")
        return
    except OSError as exc:
        app.message(f"create failed: {exc}", kind="error")
        return
    if app.explorer_tree is not None:
        app.explorer_tree.refresh_tree()
    app.message(f"created {target.name}", kind="ok")
    if not app._explorer_is_dir:
        # VS Code behavior: a new file opens right away
        app._open_document_path(target)


def apply_rename(app: AppProtocol, path: Optional[Path], name: str) -> None:
    if path is None:
        return
    try:
        new_path = app.workspace.rename_entry(path, name)
    except ValueError as exc:
        app.message(f"invalid name: {exc}", kind="error")
        return
    except FileExistsError as exc:
        app.message(str(exc), kind="error")
        return
    except OSError as exc:
        app.message(f"rename failed: {exc}", kind="error")
        return
    # keep tabs pointing at the moved document
    for doc in app.docs:
        if doc.path is not None and doc.path.resolve() == path.resolve():
            doc.path = new_path
    if app.explorer_tree is not None:
        app.explorer_tree.refresh_tree()
    app.message(f"renamed to {new_path.name}", kind="ok")


def apply_delete(app: AppProtocol, path: Optional[Path], confirm: str) -> None:
    if path is None:
        return
    if confirm.strip().lower() not in ("y", "yes"):
        app.message("delete cancelled")
        return
    try:
        app.workspace.remove_entry(path)
    except OSError as exc:
        app.message(f"delete failed: {exc}", kind="error")
        return
    # close tabs whose file lived under the deleted path
    target = path.resolve()
    closed_docs = [d for d in app.docs
                   if d.path is not None and d.path.resolve().is_relative_to(target)]
    kept = [d for d in app.docs if d not in closed_docs]
    if closed_docs:
        # Notify LSP for each closed document BEFORE removing from app.docs.
        # Hand the worker the *bound coroutine function*, never the coroutine:
        # an eagerly built coroutine lives outside the worker's lifecycle, so a
        # worker that never starts (quit cancels the "lsp-sync" group) drops the
        # didClose and leaks "coroutine was never awaited".  partial() is bound
        # per doc, so the loop cannot late-bind like a plain lambda would.
        for doc in closed_docs:
            app.run_worker(
                partial(app.lsp.on_document_closed, doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )
        app.docs = kept
        if not app.docs:
            app.new_buffer(show=False)
        app.doc_index = max(0, min(app.doc_index, len(app.docs) - 1))
        app.search = SearchEngine()
        app.message(f"closed {len(closed_docs)} open tab(s)", kind="warn")
    if app.explorer_tree is not None:
        app.explorer_tree.refresh_tree()
    app.message(f"deleted {path.name}", kind="ok")
