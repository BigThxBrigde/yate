"""System clipboard service: a degrade-safe wrapper around pyperclip.

yate syncs its registers with the system clipboard via pyperclip
(Gitee issue IKJHBO).  The system clipboard may be unavailable on any
platform -- no backend tool on Linux (xclip/xsel/wl-clipboard), a busy
Windows clipboard -- in which case pyperclip raises
:class:`pyperclip.PyperclipException`.  Key paths must never see that
exception, so :func:`copy_text` / :func:`paste_text` catch it, log at
debug level and return failure values instead; callers fall back to the
internal-register-only behaviour.

This is the **only** module in yate that imports pyperclip.
"""

from __future__ import annotations

import pyperclip

from yate.logs import tracing

#: Trace logger ("yate.services.clipboard"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)


def copy_text(text: str) -> bool:
    """Write *text* to the system clipboard; False when unavailable.

    Returns True on success.  When the pyperclip backend raises
    :class:`pyperclip.PyperclipException` (no backend tool, clipboard
    busy, ...), logs at debug level and returns False so key paths can
    fall back to internal registers without an exception.
    """
    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException as exc:
        log.debug("clipboard copy unavailable: %s", exc)
        return False
    return True


def paste_text() -> str | None:
    """Read the system clipboard; None when unavailable, "" when empty.

    Returns the clipboard text on success.  When the pyperclip backend
    raises :class:`pyperclip.PyperclipException`, logs at debug level
    and returns None.  An empty clipboard yields ``""`` -- kept distinct
    from None; both are treated as fallback by callers.
    """
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException as exc:
        log.debug("clipboard paste unavailable: %s", exc)
        return None
