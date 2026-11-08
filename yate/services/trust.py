"""Workspace trust store gating project-level extension auto-loading.

Trust granted via ``:trust`` is a *permanent* authorization of the
resolved absolute path: it is not bound to the directory's contents, so
replacing the code inside a trusted directory keeps auto-executing it.
Revocation is manual -- the entry's line must be removed from the store
by hand (or the store file deleted).

POSIX permission hardening is best-effort: the store directory and the
store file are ``chmod``ed owner-only, and a ``chmod`` failure logs a
warning instead of passing silently.  Windows ACLs are out of scope
(tracked separately); ``chmod`` is skipped there entirely.

The read side refuses a trust store that is itself a symbolic link:
:func:`load_trusted_workspaces` returns an empty set and logs a warning
in that case.  A symlinked *parent* directory is unaffected -- that is a
common home-directory layout.

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

The write side refuses symlinked roots (see :func:`trust_workspace`), so
whatever yate records is a link-free resolved directory: redirecting a
symbolic link can never extend an existing trust entry to a new target.
"""

from __future__ import annotations

import os
from pathlib import Path

from yate.logs import tracing
from yate.paths import yate_home

#: Whether POSIX permission bits are meaningful here; tests override this
#: seam so the warning path is exercised on Windows too.
_POSIX: bool = os.name == "posix"

#: Trace logger ("yate.services.trust"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Path of the per-user trust store, next to the yaterc file.  Read at
#: call time, so tests can point it at a temporary file.
TRUST_FILE: Path = yate_home() / "trusted_workspaces"


def _chmod_quietly(target: Path, mode: int) -> None:
    """Best-effort owner-only permissions; a failure must be visible."""
    try:
        os.chmod(target, mode)
    except OSError as exc:
        log.warning(
            "could not set owner-only permissions on %s: %s", target, exc
        )


def _has_symlink_component(path: Path) -> bool:
    """Whether *path* itself or any ancestor below the file-system root is
    a symbolic link."""
    probe = path.absolute()
    return probe.is_symlink() or any(parent.is_symlink() for parent in probe.parents)


def load_trusted_workspaces(path: Path | None = None) -> set[Path]:
    """Read the trusted workspace roots from *path* (``None`` = the store).

    A missing store yields an empty set; blank lines and ``#`` comments
    are skipped.  Every entry is resolved so short paths, case variants
    or ``..`` spellings of the same directory collapse into one root.
    """
    store = TRUST_FILE if path is None else path
    if store.is_symlink():
        log.warning("refusing to read symlinked trust store %s", store)
        return set()
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


def trust_workspace(root: Path, path: Path | None = None) -> bool:
    """Record *root* as trusted, creating the store when absent.

    Returns ``True`` when *root* is (or just became) trusted and ``False``
    when the request was refused, so the ``:trust`` command can give
    accurate feedback instead of claiming success for a rejected root.

    Appending keeps the file human-editable; when *root* is already
    listed nothing is written, so repeated ``:trust`` calls never grow
    the file.

    A root containing a symlink component is refused (S39): store entries
    are matched by their resolved value, so a persisted link could be
    redirected to hand its trust to a different target without a fresh
    ``:trust``.  The store therefore only ever receives link-free roots
    written by yate itself; the read side still normalizes literal link
    entries that were written by hand.
    """
    store = TRUST_FILE if path is None else path
    if _has_symlink_component(root):
        log.warning(
            "refusing to trust %s: it contains a symlink component; "
            "trust the resolved directory instead",
            root,
        )
        return False
    resolved = root.resolve()
    if resolved in load_trusted_workspaces(store):
        return True
    # Owner-only, both for a freshly created directory and for one that
    # predates this code (``mode`` only applies on creation, and a loose umask
    # would leave it group/world readable): the store lists the workspaces
    # whose code may run automatically, so nobody else must be able to read or
    # inject entries.  ``os.chmod`` is a no-op on Windows, where the mode bits
    # carry no such meaning; a chmod failure logs a warning instead of
    # passing silently.
    store.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if _POSIX:
        _chmod_quietly(store.parent, 0o700)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(f"{resolved}\n")
    if _POSIX:
        _chmod_quietly(store, 0o600)
    return True


def is_trusted(root: Path, path: Path | None = None) -> bool:
    """Return whether *root* appears in the trust store."""
    store = TRUST_FILE if path is None else path
    return root.resolve() in load_trusted_workspaces(store)
