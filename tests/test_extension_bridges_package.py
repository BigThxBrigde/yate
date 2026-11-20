"""Compatibility guards for the bridges module-to-package split.

The extension facade freezes its public import paths; this test pins that
every name formerly reachable from ``yate.services.extensions.bridges``
still resolves to the same object after the single module became a package.
"""

from __future__ import annotations

from yate.services import extensions
from yate.services.extensions import api, bridges

#: Names ``api.py`` imported from the old single-module ``bridges``.
LEGACY_NAMES: tuple[str, ...] = (
    "ActionExtensionBridge",
    "CanvasControls",
    "CanvasOpener",
    "ClipboardExtensionBridge",
    "DataExtensionBridge",
    "DocsExtensionBridge",
    "EventExtensionBridge",
    "HighlightExtensionBridge",
    "LspExtensionBridge",
    "SpriteExtensionBridge",
    "SyntaxExtensionBridge",
    "ThemeExtensionBridge",
    "UiExtensionBridge",
)

#: Additional module-level names that were public before the split.
LEGACY_TYPES: tuple[str, ...] = ("CanvasHandle", "SegmentAlign", "StatusSegment")


def test_bridges_package_reexports_every_legacy_name() -> None:
    """The package namespace keeps every old name, with identical objects."""
    for name in (*LEGACY_NAMES, *LEGACY_TYPES):
        assert name in bridges.__all__, name
        assert getattr(bridges, name) is not None, name
    for name in LEGACY_NAMES:
        assert getattr(bridges, name) is getattr(api, name), name


def test_facade_exports_still_resolve_through_the_package() -> None:
    """The frozen facade names that come from bridges are unchanged."""
    assert extensions.HighlightExtensionBridge is bridges.HighlightExtensionBridge
    assert extensions.LspExtensionBridge is bridges.LspExtensionBridge
    assert extensions.SpriteExtensionBridge is bridges.SpriteExtensionBridge
    assert extensions.StatusSegment is bridges.StatusSegment
    assert extensions.SyntaxExtensionBridge is bridges.SyntaxExtensionBridge
