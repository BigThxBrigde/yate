"""Sole gateway to Textual's private internal APIs.

yate's Windows key-chord driver reuses two Textual internals that carry no
stability promise (underscore modules): the xterm parser and the driver
writer thread.  This module is the *only* place that imports them, so a
Textual upgrade that breaks a private API surfaces here first -- check this
file before anything else when bumping Textual.

One more Textual-surface mirror lives outside this file: the
``HighlightMixin`` declaration stubs in
``yate/editor_view/highlighting.py`` hand-mirror five public widget
signatures -- re-check that file on upgrades too.

Version commitments: the dependency floor is ``textual>=8.0``
(``pyproject.toml``); the private APIs below are verified against the 8.2.8
release (the devtools-bridge notes in ``architecture-boundaries.md`` R12
carry the same-era evidence).
"""

from __future__ import annotations

from textual._xterm_parser import XTermParser
from textual.drivers._writer_thread import WriterThread

__all__ = ["WriterThread", "XTermParser"]
