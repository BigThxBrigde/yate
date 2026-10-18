"""Service layer: the UI-free services the editor and the shell share.

Members (each imported from its own submodule):

* :mod:`yate.services.workspace` -- workspace tree / file system browsing;
* :mod:`yate.services.shell` -- shell command execution;
* :mod:`yate.services.clipboard` -- system clipboard (degrade-safe wrapper);
* :mod:`yate.services.fonts` -- bundled Nerd Font detection and user install;
* :mod:`yate.services.trust` -- workspace trust store for extension auto-loading;
* :mod:`yate.services.user_setup` -- one-time ``~/.yate/`` setup and cleanup;
* :mod:`yate.services.events` -- editor event hub for extension scripts;
* :mod:`yate.services.idle_tracker` -- idle-input tracking for the screensaver;
* :mod:`yate.services.yxp` -- ``.yxp`` package read / verify / install (no
  extension runtime coupling, so it stays out of ``services/extensions/``);
* :mod:`yate.services.extensions` -- the L3 extension machinery subpackage.

Submodules are deliberately **not** re-exported: importing this package
(e.g. ``from yate.services import fonts``) must not eagerly load the
extension loader and the rest of the service stack. Import from the
submodule that defines the symbol
(``from yate.services.workspace import Workspace``).
"""

from __future__ import annotations
