"""Smoke scenarios, grouped by the functional area they cover.

Every submodule exposes ``SCENARIOS: list[Scenario]``; this package
concatenates them in a stable order (core first, then the feature groups,
then the regression and stress groups) and re-exports the helpers scenario
authors need.
"""

from __future__ import annotations

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import goto, run_command, type_text, wait_until
from .core import SCENARIOS as _CORE

__all__ = [
    "SCENARIOS",
    "Check",
    "Scenario",
    "ScenarioResult",
    "goto",
    "new_app",
    "run_command",
    "snapshot_svg",
    "type_text",
    "wait_until",
]

SCENARIOS: list[Scenario] = list(_CORE)
