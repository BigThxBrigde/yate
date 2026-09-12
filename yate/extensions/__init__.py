"""Bundled yate extensions.

The scripts in this directory ship inside the yate package and are loaded
automatically at startup (see :func:`yate.paths.bundled_extensions_dir`):

* ``python_lsp.py``      -- Python language-server registration
* ``csharp_highlight.py`` -- C# syntax highlighting bundle
* ``example_ext.py.example`` -- copy-to-use extension template (not loaded,
  the ``.example`` suffix keeps it out of the auto-load ``*.py`` scan)

Individual bundled extensions can be turned off with the yaterc
``disabled_extensions`` option. User/project extensions still live in
``~/.yate/extensions/`` and ``./extensions/``.
"""
