"""Bundled yate extensions.

The scripts in this directory ship inside the yate package and are loaded
automatically at startup (see :func:`yate.paths.bundled_extensions_dir`):

* ``python_lsp.py``      -- Python language-server registration
* ``example_ext.py.example`` -- copy-to-use extension template (not loaded,
  the ``.example`` suffix keeps it out of the auto-load ``*.py`` scan)
* further ``*.py.example`` syntax templates (batch, ini, fsharp, git, diff)
  demonstrate both highlight APIs; copy one without the suffix to use it
* ``_yate.lua``          -- bundled Lua API library for ``*.lua`` extensions
  (importable as ``require("yate")``; never auto-loaded thanks to the
  underscore prefix); loading ``.lua`` scripts needs the optional
  ``lupa`` package (``pip install yate[lua]``)
* ``lua.example``        -- commented Lua extension template; copy it
  without the ``.example`` suffix to activate

Individual bundled extensions can be turned off with the yaterc
``disabled_extensions`` option. User/project extensions still live in
``~/.yate/extensions/`` and ``./extensions/``.
"""

from __future__ import annotations
