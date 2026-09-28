"""Screensaver sprite pack: pixel frames, palettes, half-block rendering.

Pure L0 leaf: ASCII-art sprite data plus pure rendering functions -- no
Textual / rich / UI imports, no I/O, no state.  The screensaver screen
(:mod:`yate.editor_view.screensaver`) drives this pack: it picks a frame
per animation tick, walks it across the terminal via :func:`render.walk_x`
and turns the ``(glyph, style)`` cells from :func:`render.render_rows`
into text segments itself.

Import submodules directly (``render`` for the rendering helpers,
``characters`` for the registry); this ``__init__`` deliberately
re-exports nothing so importing the package stays lazy.
"""

from __future__ import annotations
