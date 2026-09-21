"""editor_view -- the Textual / Rich based UI core of yate.

Widgets
-------
* :class:`~yate.editor_view.editor.EditorView`  -- the main text editing
  surface (gutter, selection, search highlights, cursor, scrolling)
* :class:`~yate.editor_view.explorer.ExplorerTree` -- the file tree /
  resource explorer
* :class:`~yate.editor_view.statusbar.StatusBar`   -- mode, file name,
  cursor position, diagnostics
* :class:`~yate.editor_view.commandline.PromptBar` -- the ``:`` / ``/`` /
  ``!`` prompt and message area
* :class:`~yate.editor_view.modals.HelpScreen`  -- keymap help overlay
  (modal screen)
* :class:`~yate.editor_view.modals.OutputScreen` -- shell command output
  overlay (modal screen)
* :class:`~yate.editor_view.terminal.TerminalPanel` -- integrated PTY
  terminal docked at the bottom

All glyphs live in :mod:`yate.editor_view.icons` (Nerd Fonts) and colors
in :mod:`yate.editor_view.theme`.

Widgets are deliberately **not** re-exported here: importing this package
(or a leaf module such as :mod:`~yate.editor_view.theme`) must not eagerly
build the whole widget stack. Import widgets from their own modules
(``from yate.editor_view.editor import EditorView``).
"""
