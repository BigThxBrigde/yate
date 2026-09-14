"""yate - yet another terminal editor.

A Textual based terminal text editor with:

* :mod:`yate.editor_core` -- UI independent editing core (buffer, document, search)
* :mod:`yate.keymaps`     -- pluggable key maps (VS Code style *vsc* and *vim*)
* :mod:`yate.editor_view` -- Textual widgets (editor view, explorer, modals)
* :mod:`yate.services`    -- workspace, shell execution, extensions and fonts
"""

__version__ = "0.2.3"
__description__ = "yet another terminal editor (Textual based)"
__all__ = ["__version__", "__description__"]
