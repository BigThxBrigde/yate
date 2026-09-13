"""Bundled markdown doc viewer lifecycle: manual + changelog.

Extracted from :class:`yate.app.YateApp` (same collaborator shape as
``app_features.terminal``): the theme-restoration flag stays on the app
because commands, keymaps and tests read it directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yate.editor_view.manual import MarkdownDocScreen

if TYPE_CHECKING:
    from yate.app import YateApp

# Extracted YateApp collaborator: touching the app's private doc-viewer
# state (_prev_doc_theme) is this module's contract.
# pyright: reportPrivateUsage=false


def show_doc(app: "YateApp", *, kind: str, lang: str, title: str) -> None:
    """Push the MarkdownDocScreen, switching theme for the duration."""
    if not app.mounted or isinstance(app.screen, MarkdownDocScreen):
        return
    # switch the textual design tokens before pushing so the first frame
    # of the markdown viewer is already themed (switching on screen resume
    # leaves an unthemed flash while markdown mounts)
    app._prev_doc_theme = app.theme
    app.theme = "catppuccin-mocha"
    app._push_overlay(
        MarkdownDocScreen(app, kind=kind, lang=lang, title=title),
        callback=lambda _result: _restore_theme(app),
    )


def show_manual(app: "YateApp", lang: str = "en") -> None:
    """Open the bundled user manual."""
    show_doc(app, kind="manual", lang=lang, title="user manual")


def show_changelog(app: "YateApp", lang: str = "en") -> None:
    """Open the bundled bilingual changelog."""
    show_doc(app, kind="changelog", lang=lang, title="changelog")


def _restore_theme(app: "YateApp") -> None:
    if app._prev_doc_theme is not None:
        app.theme = app._prev_doc_theme
        app._prev_doc_theme = None
