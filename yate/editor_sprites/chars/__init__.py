"""Bitmap data modules, one per screensaver character (plus templates).

Imported by :mod:`yate.editor_sprites.characters` only; each module
exposes ``FRAMES`` and a palette (``PALETTE`` or a ``palette()``
recolorer for multi-color templates).  Pure data -- no logic, no I/O.
"""

from __future__ import annotations
