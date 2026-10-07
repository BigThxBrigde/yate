"""Small markdown fixture the manual/doc UI tests load instead of the bundled manual.

Patching ``yate.editor_view.manual.load_doc_markdown`` with
:data:`MANUAL_DOC_FIXTURE` keeps every search/layout assertion of
``test_app_manual.py`` / ``test_app_render.py`` meaningful while skipping
the expensive parse/render of the real manual.  Data dependencies:
several ``yate`` blocks for the ``1/``/``2/`` hit counters; a table cell
``item`` for ``MarkdownTableCellContents``; a dozen ``ctrl`` fence lines
for the same-widget row-diff and ``moved > 0``; the words ``theme`` and
``key`` for the doc-search queries; no ``zqzqwx`` anywhere.
"""

from __future__ import annotations

#: Injected document; the fence sits near the top and trailing filler
#: paragraphs keep the rendered height above the pilot viewport.
MANUAL_DOC_FIXTURE: str = (
    "# yate\n"
    "\n"
    "The yate editor opens this small fixture document instead of the bundled manual.\n"
    "\n"
    "```text\n"
    "ctrl-a appends one fixture line to the buffer\n"
    "ctrl-b moves the fixture cursor back one character\n"
    "ctrl-c cancels the running fixture operation\n"
    "ctrl-d deletes the character under the fixture cursor\n"
    "ctrl-e jumps to the end of the fixture line\n"
    "ctrl-f moves the fixture cursor forward one character\n"
    "ctrl-g quits the fixture prompt without saving it\n"
    "ctrl-h deletes the character before the fixture cursor\n"
    "ctrl-i indents the selected fixture region by one step\n"
    "ctrl-j joins the two fixture lines around the cursor\n"
    "ctrl-k cuts the fixture text up to the end of the line\n"
    "ctrl-l redraws the whole fixture screen from scratch\n"
    "ctrl-m marks the current fixture position for later\n"
    "ctrl-n moves the fixture cursor to the next line\n"
    "```\n"
    "\n"
    "| key | value |\n"
    "| --- | ----- |\n"
    "| item | first fixture table entry |\n"
    "| item | second fixture table entry |\n"
    "\n"
    "Another yate paragraph keeps the search hit list multi-block.\n"
    "\n"
    "The theme bridge follows the active yate palette while the keymap\n"
    "word gives the doc-search tests determinate matches.\n"
    "\n"
    "A final yate block closes the searchable part of the fixture.\n"
    "\n"
    "Trailing filler keeps the rendered document taller than the pilot\n"
    "viewport, so the search scroll targets are not clamped to the top\n"
    "of a fully visible page during the layout assertions.  Nothing in\n"
    "these filler lines is matched by any guarded search query.\n"
    "\n"
    "Filler the second, still unmatched by every guarded search query,\n"
    "purely to grow the scrollable content below the early code fence.\n"
)
