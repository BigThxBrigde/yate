"""Bundled markdown doc viewer lifecycle: manual + changelog.

The viewer's design tokens already match the running yate theme through the
Textual theme bridge registered at startup, so :meth:`DocsFeature.show_doc`
only has to push the overlay screen -- no theme switch / restore is needed.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol

from textual.screen import Screen

from yate.editor_view.manual import MarkdownDocScreen


class DocsHost(Protocol):
    """What :class:`DocsFeature` needs from the application."""

    @property
    def mounted(self) -> bool: ...

    @property
    def screen(self) -> Screen[object]: ...

    def push_overlay(
        self,
        screen: Screen[Any],
        callback: Optional[Callable[[Any], None]] = None,
    ) -> None: ...


class DocsFeature:
    """Push the bundled manual / changelog overlay screens."""

    def __init__(self, host: DocsHost) -> None:
        self._host = host

    def show_doc(self, *, kind: str, lang: str, title: str) -> None:
        """Push the MarkdownDocScreen for *kind* / *lang* / *title*.

        The viewer's frame chrome (borders, markdown headings, search-hit
        tints) already follows the active yate theme through the Textual
        theme bridge, so there is no theme switch before the push and no
        restore on close.
        """
        if (not self._host.mounted
                or isinstance(self._host.screen, MarkdownDocScreen)):
            return
        self._host.push_overlay(
            MarkdownDocScreen(kind=kind, lang=lang, title=title))

    def show_manual(self, lang: str = "en") -> None:
        """Open the bundled user manual."""
        self.show_doc(kind="manual", lang=lang, title="user manual")

    def show_changelog(self, lang: str = "en") -> None:
        """Open the bundled bilingual changelog."""
        self.show_doc(kind="changelog", lang=lang, title="changelog")
