"""YM003: require Chinese quotation marks in Chinese context."""

from __future__ import annotations

import re
from typing import override

from pymarkdown.plugin_manager.plugin_details import PluginDetails
from pymarkdown.plugin_manager.plugin_scan_context import PluginScanContext
from pymarkdown.plugin_manager.rule_plugin import RulePlugin

from tools.mdlint.fences import FenceTracker

_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_ASCII_QUOTES = "\"'"


class YmChineseQuotes(RulePlugin):
    """Detect ASCII quotes used around Chinese text."""

    def __init__(self) -> None:
        """Track fenced-code state across lines."""
        super().__init__()
        self._fence = FenceTracker()

    @override
    def get_details(self) -> PluginDetails:
        """Get the details for the plugin."""
        return PluginDetails(
            plugin_id="YM003",
            plugin_name="chinese-quotes",
            plugin_description=(
                "ASCII quotes must be Chinese quotes in Chinese context"
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
        """Scan one line for ASCII quotes adjacent to CJK text."""
        masked = self._fence.mask(line)
        if masked is None:
            return
        if not _CJK.search(masked):
            return
        chars = list(masked)
        for idx, char in enumerate(chars):
            if char not in _ASCII_QUOTES:
                continue
            if idx > 0 and _CJK.match(chars[idx - 1]):
                self.report_next_line_error(context, idx + 1)
            elif idx + 1 < len(chars) and _CJK.match(chars[idx + 1]):
                self.report_next_line_error(context, idx + 1)
