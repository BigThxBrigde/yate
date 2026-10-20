"""YM001: require a space between CJK characters and Latin letters/digits."""

from __future__ import annotations

import re
from typing import override

from pymarkdown.plugin_manager.plugin_details import PluginDetails
from pymarkdown.plugin_manager.plugin_scan_context import PluginScanContext
from pymarkdown.plugin_manager.rule_plugin import RulePlugin

from tools.mdlint.fences import FenceTracker

_CJK_ASCII_ADJACENCY = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf][A-Za-z0-9]|[A-Za-z0-9][\u4e00-\u9fff\u3400-\u4dbf]"
)


class YmCjkSpacing(RulePlugin):
    """Detect missing spaces between CJK text and Latin letters or digits."""

    def __init__(self) -> None:
        """Track fenced-code state across lines."""
        super().__init__()
        self._fence = FenceTracker()

    @override
    def get_details(self) -> PluginDetails:
        """Get the details for the plugin."""
        return PluginDetails(
            plugin_id="YM001",
            plugin_name="cjk-spacing",
            plugin_description="CJK and Latin characters must be separated by a space",
            plugin_enabled_by_default=True,
            plugin_version="0.1.0",
        )

    @override
    def starting_new_file(self) -> None:
        """Reset the fenced-code state for a new document."""
        self._fence.reset()

    @override
    def next_line(self, context: PluginScanContext, line: str) -> None:
        """Scan one line for CJK/Latin adjacency outside code."""
        masked = self._fence.mask(line)
        if masked is None:
            return
        for match in _CJK_ASCII_ADJACENCY.finditer(masked):
            self.report_next_line_error(context, match.start() + 1)
