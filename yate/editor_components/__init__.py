"""editor_components -- the Textual / Rich based UI core of yate.

Widgets
-------
* :class:`~yate.editor_components.editor.EditorView`  -- the main text editing
  surface (gutter, selection, search highlights, cursor, scrolling)
* :class:`~yate.editor_components.explorer.ExplorerTree` -- the file tree /
  resource explorer
* :class:`~yate.editor_components.statusbar.StatusBar`   -- mode, file name,
  cursor position, diagnostics
* :class:`~yate.editor_components.commandline.PromptBar` -- the ``:`` / ``/`` /
  ``!`` prompt and message area
* :class:`~yate.editor_components.modals.HelpScreen`  -- keymap help overlay
  (modal screen)
* :class:`~yate.editor_components.modals.OutputScreen` -- shell command output
  overlay (modal screen)
* :class:`~yate.editor_components.terminal.TerminalPanel` -- integrated PTY
  terminal docked at the bottom

All glyphs live in :mod:`yate.editor_components.icons` (Nerd Fonts) and colors
in :mod:`yate.editor_components.theme`.

Widgets are deliberately **not** re-exported here: importing this package
(or a leaf module such as :mod:`~yate.editor_components.theme`) must not eagerly
build the whole widget stack. Import widgets from their own modules
(``from yate.editor_components.editor import EditorView``).
"""

from __future__ import annotations
