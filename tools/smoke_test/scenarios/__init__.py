"""Smoke scenarios, grouped by the functional area they cover.

Every submodule exposes ``SCENARIOS: list[Scenario]``; this package
concatenates them in a stable order (core first, then the feature groups,
then the regression and stress groups) and re-exports the helpers scenario
authors need.
"""

from __future__ import annotations

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import goto, run_command, type_text, wait_until
from .aliases import SCENARIOS as _ALIASES
from .core import SCENARIOS as _CORE
from .diffview import SCENARIOS as _DIFFVIEW
from .edit import SCENARIOS as _EDIT
from .explorer import SCENARIOS as _EXPLORER
from .files import SCENARIOS as _FILES
from .guards import SCENARIOS as _GUARDS
from .integration import SCENARIOS as _INTEGRATION
from .panes import SCENARIOS as _PANES
from .regression import SCENARIOS as _REGRESSION
from .screensaver import SCENARIOS as _SCREENSAVER
from .search import SCENARIOS as _SEARCH
from .stress import SCENARIOS as _STRESS
from .view import SCENARIOS as _VIEW

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

SCENARIOS: list[Scenario] = [
    *_CORE,
    *_EDIT,
    *_SEARCH,
    *_FILES,
    *_GUARDS,
    *_PANES,
    *_EXPLORER,
    *_VIEW,
    *_DIFFVIEW,
    *_INTEGRATION,
    *_REGRESSION,
    *_SCREENSAVER,
    *_STRESS,
    *_ALIASES,
]
