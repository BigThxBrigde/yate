"""Low-level key-chord model and codecs for the windows input channel.

yate has two key layers: terminals deliver raw bytes (or Textual key names
decoded from them), and the keymap tables dispatch on those bytes.  On
Windows the console driver can do better than bytes -- input records carry
the virtual-key code and the full modifier state -- but that information is
lost before the keymap layer unless someone models it.  This package is that
model, plus the byte-level codecs the rest of yate already speaks:

- :mod:`yate.keyproto.chords` -- the :class:`KeyChord` record and VK codes;
- :mod:`yate.keyproto.aliases` -- chord -> canonical Textual key name and
  chord -> legacy C0 byte;
- :mod:`yate.keyproto.legacy` -- Textual key name -> raw byte (the codec
  formerly living in ``yate.editor_view.keys``).

L0 leaf package: apart from the Windows driver, the package modules depend
on the standard library only.  ``driver_windows.py`` carries two documented
exemptions: :mod:`yate.logs` (R12 -- every runtime log goes through
tracing; the logger itself is side-effect free) and
:mod:`yate.keyproto.textual_internals` (the sole gateway to Textual's
private internal APIs, with the minimum-version commitment).  The package
does not import :mod:`yate.keymaps.base` -- the earlier ``SPECIAL_KEYS``
mention was historical.
"""

from __future__ import annotations
