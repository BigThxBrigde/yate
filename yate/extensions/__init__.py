"""Bundled yate extensions.

The scripts in this directory ship inside the yate package and are loaded
automatically at startup (see :func:`yate.paths.bundled_extensions_dir`):

* ``python_lsp.py``      -- Python language-server registration
* ``example_ext.py.example`` -- copy-to-use extension template (not loaded,
  the ``.example`` suffix keeps it out of the auto-load ``*.py`` scan)
* further ``*.py.example`` syntax templates (batch, ini, fsharp, git, diff)
  demonstrate both highlight APIs; copy one without the suffix to use it

Individual bundled extensions can be turned off with the yaterc
``disabled_extensions`` option. User/project extensions still live in
``~/.yate/extensions/`` and ``./extensions/``.
"""

from __future__ import annotations
