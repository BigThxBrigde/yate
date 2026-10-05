"""Stable error codes and terminal error rendering for ``tools.pack``.

Every user-visible failure of the packaging helpers is reported as a short
machine-readable code plus a readable message::

    error[WIKI-0102]: Chinese source vanished: alpha-plan.md
    hint: re-run after the source tree is complete

Two rules make this the only channel an error takes:

* library code raises :class:`PackError` (never ``sys.exit``), so the CLI
  boundary stays the single place that decides exit codes;
* the traceback never reaches the terminal by default -- it is always
  handed to :mod:`logging` (see :data:`log`) and only printed when the user
  asks for it with ``--debug``.

The :mod:`tools.translate` sibling keeps its own message style; this module
deliberately scopes the code table to ``tools.pack``.
"""

from __future__ import annotations

import logging
import sys
import traceback
from enum import StrEnum

__all__ = ["Code", "PackError", "log", "report"]

#: Diagnostics channel.  No handler is installed, so DEBUG records -- where
#: the traceback goes -- are dropped instead of leaking onto the terminal.
log: logging.Logger = logging.getLogger("yate.pack")


class Code(StrEnum):
    """Stable error codes; the value is exactly what the terminal shows.

    Codes are grouped by subcommand (``PKG`` cross-cutting, ``WIKI``,
    ``ICON``, ``ROSTERS``) and never renumbered -- they end up in bug
    reports, so the string is the contract, not the enum member.
    """

    UNEXPECTED = "PKG-0001"
    GIT_MISSING = "PKG-0002"
    WIKI_TARGET_COLLISION = "WIKI-0101"
    WIKI_ZH_SOURCE_MISSING = "WIKI-0102"
    WIKI_SOURCE_UNREADABLE = "WIKI-0103"
    WIKI_MANIFEST_READ = "WIKI-0104"
    WIKI_MANIFEST_WRITE = "WIKI-0105"
    WIKI_PAGE_WRITE = "WIKI-0106"
    WIKI_PRUNE_FAILED = "WIKI-0107"
    WIKI_TRANSLATE_FAILED = "WIKI-0201"
    WIKI_TRANSLATE_TIMEOUT = "WIKI-0202"
    ICON_BUILD = "ICON-0301"
    ROSTERS_RENDER = "ROSTERS-0302"


class PackError(RuntimeError):
    """A packaging tool operation failed and the run must abort.

    *code* selects the stable :class:`Code` shown to the user and *message*
    is the readable text; *hint* is an optional second line with the action
    that usually fixes it (printed as ``hint: ...``).

    Subclasses (e.g. :class:`tools.pack.wiki.WikiError`) only specialise the
    default code, so ``except PackError`` catches the whole family.
    """

    def __init__(self, code: Code, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.code: Code = code
        self.hint: str | None = hint

    def render(self) -> str:
        """Return the two-or-one line terminal form of this error."""
        head = f"error[{self.code}]: {self}"
        if self.hint is None:
            return head
        return f"{head}\nhint: {self.hint}"


def report(exc: BaseException, *, debug: bool = False) -> None:
    """Print *exc* as ``error[<code>]: <message>`` on stderr.

    An unexpected exception type is rendered with :data:`Code.UNEXPECTED` so
    the terminal contract holds for everything, not just :class:`PackError`.
    The traceback always goes to :data:`log` at DEBUG level; it is echoed to
    stderr only when *debug* is set (``--debug``).

    Returns None -- the caller maps the failure to an exit code.
    """
    if isinstance(exc, PackError):
        log.debug("pack tool failure: %s", exc, exc_info=exc)
        print(exc.render(), file=sys.stderr)
    else:
        log.debug("unhandled pack tool failure", exc_info=exc)
        print(f"error[{Code.UNEXPECTED}]: {exc}", file=sys.stderr)
    if debug:
        traceback.print_exception(exc, file=sys.stderr)