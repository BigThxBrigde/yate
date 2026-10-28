"""Custom, extensible Python script support.

An extension is any ``.py`` file exposing a ``setup(api)`` function (and an
optional ``teardown(api)``).  ``setup`` receives an :class:`ExtensionAPI`
through which it can register actions, key bindings, ``:`` commands, run
shell commands and manipulate the active document.  If ``setup`` raises
partway through, every registration made through the API is rolled back
automatically -- previous values restored -- so callers no longer need to
front-load validation (audit A13; the loader drives the scope, see
:meth:`ExtensionAPI.start_scope`).

Example bundled extension ``yate/extensions/uppercase.py``::

    def setup(api):
        @api.command("upper", "Uppercase the selection (or whole line)")
        def upper(args):
            buf = api.buffer
            text = buf.selected_text()
            if text is None:
                row = buf.row
                text = buf.lines[row]
                buf.lines[row] = text.upper()
                buf.mark_content_changed()  # direct line edit: refresh caches
            else:
                api.buffer.insert_text(text.upper())
            api.message("uppercased!")

        api.bind_key("<alt-u>", lambda ctx: upper(""), keymap="vsc")

Lua extensions (``*.lua``) share this pipeline: a global ``setup(api)`` is
called once the chunk's top level has run (chunks without one keep the
legacy "top-level code *is* the setup" behavior), an optional global
``teardown(api)`` mirrors the hook, and the API library ships as
``require("yate")`` (``yate/extensions/_yate.lua``;
bridge: :mod:`yate.services.extensions.lua.runtime`, needs
``pip install yate[lua]``).

Layout map (2026-10-11 split into sibling modules, 2026-10-13 collapsed
into this subpackage): :mod:`yate.services.extensions.bridges` owns the
``api.*`` bridges (events / ui / lsp / highlight / syntax / sprites /
theme / clipboard / docs / actions),
:mod:`yate.services.extensions.api` owns ``ExtensionContext`` and the
``ExtensionAPI`` surface plus the A13 rollback-scope aliases, and
:mod:`yate.services.extensions.loader` owns discovery, loading, rollback
driving, teardown and the startup load order.  This module is a pure
re-export facade; the plugin-facing import path is frozen and the
submodules are internal, non-public API (R14): yate code and plugins
import only from here.

Package-root re-export exception note (architecture rules section 3.5): UI and
service packages normally must not re-export; this facade is the single
registered exception for service packages -- the plugin import path is
frozen by R14 and guarded by
``test_extension_facade_exports_the_frozen_plugin_names``.
"""

from __future__ import annotations

# Plugin import path frozen: the manual and every ``*.py.example`` import from here.
from yate.services.extensions.api import (
    AnyCallback,
    CommandDecorator,
    ExtensionAPI,
    ExtensionContext,
    RollbackHook,
)
from yate.services.extensions.bridges import (
    HighlightExtensionBridge,
    LspExtensionBridge,
    SpriteExtensionBridge,
    StatusSegment,
    SyntaxExtensionBridge,
)
from yate.services.extensions.loader import (
    ExtensionLoader,
    LoadedExtension,
    TeardownHook,
    load_startup_extensions,
)

__all__ = [
    "AnyCallback",
    "CommandDecorator",
    "ExtensionAPI",
    "ExtensionContext",
    "ExtensionLoader",
    "HighlightExtensionBridge",
    "LoadedExtension",
    "LspExtensionBridge",
    "RollbackHook",
    "SpriteExtensionBridge",
    "StatusSegment",
    "SyntaxExtensionBridge",
    "TeardownHook",
    "load_startup_extensions",
]
