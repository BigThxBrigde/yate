"""The ``api.*`` sub-namespace bridges (events / lsp / highlight / syntax /
sprites / ui / theme / clipboard / docs / actions / data).

Split out of the former single ``bridges.py`` module (2026-11-20): each
bridge wraps one capability domain for extension scripts; the
:class:`ExtensionAPI <yate.services.extensions.api.ExtensionAPI>` facade
instantiates them in its ``__init__`` and hands them out through the
matching properties.  The import paths of every consumer stay frozen:
this ``__init__`` re-exports every old module-level public name (the 11
bridge classes plus :class:`CanvasHandle`, :class:`StatusSegment` and the
``SegmentAlign`` / ``CanvasControls`` / ``CanvasOpener`` aliases), so
``from yate.services.extensions.bridges import X`` keeps working for
``api.py``, the facade and the test suite unchanged.

Two wiring notes frozen by the unchanged test suite:

* the names the tests patch on this package namespace
  (``load_language_from_grammar`` / ``drop_ts_language``, string targets
  in ``tests/test_extension_bridges.py`` and ``patch.object`` targets in
  ``tests/test_ts_backend.py``) are re-exported here from
  :mod:`yate.editor_syntax.ts_backend`, while their in-package caller
  (:class:`~yate.services.extensions.bridges.syntax_lsp.SyntaxExtensionBridge`)
  resolves them through a late-bound ``from
  yate.services.extensions.bridges import ...`` lookup at call time -- the
  same registered seam the ``yate/services/yxp/`` facade uses;
* each submodule keeps the R12 default ``log =
  tracing.get_logger(__name__)`` (child logger names
  ``yate.services.extensions.bridges.<module>``): no test depends on the
  old single-module logger name -- the only caplog window targeting the
  bridges domain (``tests/test_extension_bridges.py``) filters on the
  ``"yate"`` root logger with ``propagate`` re-enabled, so child records
  arrive regardless of their exact logger name.
"""

from __future__ import annotations

from yate.editor_syntax.ts_backend import (
    drop_language as drop_ts_language,
    load_language_from_grammar,
)
from yate.services.extensions.bridges.data_event import (
    ActionExtensionBridge,
    ClipboardExtensionBridge,
    DataExtensionBridge,
    DocsExtensionBridge,
    EventExtensionBridge,
)
from yate.services.extensions.bridges.syntax_lsp import (
    HighlightExtensionBridge,
    LspExtensionBridge,
    SpriteExtensionBridge,
    SyntaxExtensionBridge,
    ThemeExtensionBridge,
)
from yate.services.extensions.bridges.ui import (
    CanvasControls,
    CanvasHandle,
    CanvasOpener,
    SegmentAlign,
    StatusSegment,
    UiExtensionBridge,
)

__all__ = [
    "ActionExtensionBridge",
    "CanvasControls",
    "CanvasHandle",
    "CanvasOpener",
    "ClipboardExtensionBridge",
    "DataExtensionBridge",
    "DocsExtensionBridge",
    "EventExtensionBridge",
    "HighlightExtensionBridge",
    "LspExtensionBridge",
    "SegmentAlign",
    "SpriteExtensionBridge",
    "StatusSegment",
    "SyntaxExtensionBridge",
    "ThemeExtensionBridge",
    "UiExtensionBridge",
    "drop_ts_language",
    "load_language_from_grammar",
]
