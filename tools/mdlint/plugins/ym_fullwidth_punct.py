"""YM002: require full-width punctuation in Chinese context."""

from __future__ import annotations

import re
from typing import override

from pymarkdown.plugin_manager.plugin_details import PluginDetails
from pymarkdown.plugin_manager.plugin_scan_context import PluginScanContext
from pymarkdown.plugin_manager.rule_plugin import RulePlugin

from tools.mdlint.fences import FenceTracker

_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# Half-width punctuation that should be full-width next to CJK characters.
_HALF_WIDTH_PUNCT = ",.;:?!()"
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S*")


def _mask_urls(line: str) -> str:
    """Blank bare URLs, preserving column numbers."""
    return _URL.sub(lambda match: " " * len(match.group()), line)


class YmFullwidthPunct(RulePlugin):
    """Detect half-width punctuation adjacent to CJK characters."""

    def __init__(self) -> None:
        """Track fenced-code state across lines."""
        super().__init__()
        self._fence = FenceTracker()

    @override
    def get_details(self) -> PluginDetails:
        """Get the details for the plugin."""
        return PluginDetails(
            plugin_id="YM002",
            plugin_name="fullwidth-punct",
            plugin_description=(
                "Half-width punctuation must be full-width in Chinese context"
            ),
            plugin_enabled_by_default=True,
            plugin_version="0.1.0",
        )

    @override
    def starting_new_file(self) -> None:
        """Reset the fenced-code state for a new document."""
        self._fence.reset()

    @override
    def next_line(self, context: PluginScanContext, line: str) -> None:
        """Scan one line for half-width punctuation near CJK text."""
        masked = self._fence.mask(line)
        if masked is None:
            return
        masked = _mask_urls(masked)
        if not _CJK.search(masked):
            return
        chars = list(masked)
        for idx, char in enumerate(chars):
            if char not in _HALF_WIDTH_PUNCT:
                continue
            if idx > 0 and _CJK.match(chars[idx - 1]):
                self.report_next_line_error(context, idx + 1)
            elif idx + 1 < len(chars) and _CJK.match(chars[idx + 1]):
                self.report_next_line_error(context, idx + 1)
