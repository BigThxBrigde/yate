"""Workspace trust store gating project-level extension auto-loading.

Opening a repository must never execute the repository's own code: a
malicious ``extensions/`` directory checked into a project would
otherwise run arbitrary Python at every yate start inside that
directory.  This module records the workspaces a user has explicitly
trusted via the ``:trust`` command in ``~/.yate/trusted_workspaces``
(one resolved absolute path per line, ``#`` comments allowed) and
answers whether a working directory may have its ``./extensions``
auto-loaded at startup.

rc-declared paths, ``--ext`` / ``--ext-dir`` and the user-level
``~/.yate/extensions`` stay unconditional: those are deliberate user
actions, while the project directory belongs to whatever repository the
user happens to open.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

#: Path of the per-user trust store, next to the yaterc file.  Read at
#: call time, so tests can point it at a temporary file.
TRUST_FILE = Path.home() / ".yate" / "trusted_workspaces"


def load_trusted_workspaces(path: Path | None = None) -> set[Path]:
    """Read the trusted workspace roots from *path* (``None`` = the store).

    A missing store yields an empty set; blank lines and ``#`` comments
    are skipped.  Every entry is resolved so short paths, case variants
    or ``..`` spellings of the same directory collapse into one root.
    """
    store = TRUST_FILE if path is None else path
    try:
        # A hand-edited or corrupted store must never break startup: invalid
        # bytes decode to U+FFFD instead of raising UnicodeDecodeError, and
        # the surrounding entries still load.
        raw = store.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    trusted: set[Path] = set()
    for line in raw.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            trusted.add(Path(entry).resolve())
    return trusted


def trust_workspace(root: Path, path: Path | None = None) -> None:
    """Record *root* as trusted, creating the store when absent.

    Appending keeps the file human-editable; when *root* is already
    listed nothing is written, so repeated ``:trust`` calls never grow
    the file.
    """
    store = TRUST_FILE if path is None else path
    resolved = root.resolve()
    if resolved in load_trusted_workspaces(store):
        return
    # Owner-only, both for a freshly created directory and for one that
    # predates this code (``mode`` only applies on creation, and a loose umask
    # would leave it group/world readable): the store lists the workspaces
    # whose code may run automatically, so nobody else must be able to read or
    # inject entries.  ``os.chmod`` is a no-op on Windows, where the mode bits
    # carry no such meaning.
    store.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if os.name == "posix":
        with contextlib.suppress(OSError):
            os.chmod(store.parent, 0o700)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(f"{resolved}\n")
    if os.name == "posix":
        with contextlib.suppress(OSError):
            os.chmod(store, 0o600)


def is_trusted(root: Path, path: Path | None = None) -> bool:
    """Return whether *root* appears in the trust store."""
    store = TRUST_FILE if path is None else path
    return root.resolve() in load_trusted_workspaces(store)
