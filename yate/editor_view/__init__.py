"""editor_view -- the Textual / Rich based UI core of yate.

Widgets
-------
* :class:`EditorView`  -- the main text editing surface (gutter, selection,
  search highlights, cursor, scrolling)
* :class:`ExplorerTree` -- the file tree / resource explorer
* :class:`StatusBar`   -- mode, file name, cursor position, diagnostics
* :class:`PromptBar`   -- the ``:`` / ``/`` / ``!`` prompt and message area
* :class:`HelpScreen`  -- keymap help overlay (modal screen)
* :class:`OutputScreen` -- shell command output overlay (modal screen)

All glyphs live in :mod:`yate.editor_view.icons` (Nerd Fonts) and colors in
:mod:`yate.editor_view.theme`.
"""

from yate.editor_view.commandline import PromptBar
from yate.editor_view.editor import EditorView
from yate.editor_view.explorer import ExplorerTree
from yate.editor_view.modals import HelpScreen, OutputScreen
from yate.editor_view.statusbar import StatusBar

__all__ = [
    "EditorView",
    "ExplorerTree",
    "StatusBar",
    "PromptBar",
    "HelpScreen",
    "OutputScreen",
]
