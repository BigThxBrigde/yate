"""Local minimal type stub for the untyped ``pyperclip`` package.

pyperclip ships no ``py.typed`` marker and no annotations, so pyright strict
would report ``import-untyped`` on every import.  This stub covers exactly
the API surface yate uses (:func:`copy`, :func:`paste`,
:class:`PyperclipException`); it is type-checking only and never packaged.
"""

from __future__ import annotations

def copy(text: str) -> None: ...

def paste() -> str: ...

class PyperclipException(RuntimeError): ...
