"""Bundled markdown doc viewer lifecycle: manual + changelog.

Extracted from :class:`yate.app.YateApp` (same collaborator shape as
``app_features.terminal``).  The viewer's design tokens already match the
running yate theme through the Textual theme bridge registered at startup,
so :func:`show_doc` only has to push the overlay screen -- no theme
switch / restore is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yate.editor_view.manual import MarkdownDocScreen

if TYPE_CHECKING:
    from yate.app import YateApp

# Extracted YateApp collaborator: this module only reads app.mounted and
# app.screen, and pushes an overlay through app._push_overlay -- no private
# theme state to touch anymore.
# pyright: reportPrivateUsage=false


def show_doc(app: "YateApp", *, kind: str, lang: str, title: str) -> None:
    """Push the MarkdownDocScreen for *kind* / *lang* / *title*.

    The viewer's frame chrome (borders, markdown headings, search-hit tints)
    already follows the active yate theme through the Textual theme bridge,
    so there is no theme switch before the push and no restore on close.
    """
    if not app.mounted or isinstance(app.screen, MarkdownDocScreen):
        return
    app._push_overlay(MarkdownDocScreen(app, kind=kind, lang=lang, title=title))


def show_manual(app: "YateApp", lang: str = "en") -> None:
    """Open the bundled user manual."""
    show_doc(app, kind="manual", lang=lang, title="user manual")


def show_changelog(app: "YateApp", lang: str = "en") -> None:
    """Open the bundled bilingual changelog."""
    show_doc(app, kind="changelog", lang=lang, title="changelog")
