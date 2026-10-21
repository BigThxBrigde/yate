"""YM004: forbid trailing CJK punctuation on ATX headings."""

from __future__ import annotations

import re
from typing import override

from pymarkdown.plugin_manager.plugin_details import PluginDetails
from pymarkdown.plugin_manager.plugin_scan_context import PluginScanContext
from pymarkdown.plugin_manager.rule_plugin import RulePlugin

from tools.mdlint.fences import FenceTracker

# ATX heading (up to three spaces of indent is still a heading) whose last
# non-space character is Chinese punctuation.
_HEADING_TRAILING_PUNCT = re.compile(r"^ {0,3}#{1,6}\s+.*[。，；：！？、]\s*$")


class YmHeadingTrailingPunct(RulePlugin):
    """Detect Chinese punctuation at the end of an ATX heading."""

    def __init__(self) -> None:
        """Track fenced-code state across lines."""
        super().__init__()
        self._fence = FenceTracker()

    @override
    def get_details(self) -> PluginDetails:
        """Get the details for the plugin."""
        return PluginDetails(
            plugin_id="YM004",
            plugin_name="heading-trailing-punct",
            plugin_description="ATX headings must not end with Chinese punctuation",
            plugin_enabled_by_default=True,
            plugin_version="0.1.0",
        )

    @override
    def starting_new_file(self) -> None:
        """Reset the fenced-code state for a new document."""
        self._fence.reset()

    @override
    def next_line(self, context: PluginScanContext, line: str) -> None:
        """Scan one heading line for trailing Chinese punctuation."""
        masked = self._fence.mask(line)
        if masked is None:
            return
        if _HEADING_TRAILING_PUNCT.match(masked):
            # Column of the last non-space character (the punctuation mark).
            self.report_next_line_error(context, len(masked.rstrip()))
