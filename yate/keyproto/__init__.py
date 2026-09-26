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

L0 leaf package: it must not import any other yate module except
:mod:`yate.keymaps.base` (also an L0 leaf, for the ``SPECIAL_KEYS`` table).
"""
