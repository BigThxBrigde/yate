"""Smoke scenarios, grouped by the functional area they cover.

Every submodule exposes ``SCENARIOS: list[Scenario]``; this package
concatenates them in a stable order (core first, then the feature groups,
then the regression and stress groups) and re-exports the helpers scenario
authors need.
"""

from __future__ import annotations

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import goto, run_command, type_text, wait_until
from tools.smoke_test.scenarios.aliases import SCENARIOS as _ALIASES
from tools.smoke_test.scenarios.core import SCENARIOS as _CORE
from tools.smoke_test.scenarios.diffview import SCENARIOS as _DIFFVIEW
from tools.smoke_test.scenarios.edit import SCENARIOS as _EDIT
from tools.smoke_test.scenarios.explorer import SCENARIOS as _EXPLORER
from tools.smoke_test.scenarios.files import SCENARIOS as _FILES
from tools.smoke_test.scenarios.guards import SCENARIOS as _GUARDS
from tools.smoke_test.scenarios.integration import SCENARIOS as _INTEGRATION
from tools.smoke_test.scenarios.multi_cursor import SCENARIOS as _MULTI_CURSOR
from tools.smoke_test.scenarios.palette_preview import SCENARIOS as _PALETTE_PREVIEW
from tools.smoke_test.scenarios.panes import SCENARIOS as _PANES
from tools.smoke_test.scenarios.regression import SCENARIOS as _REGRESSION
from tools.smoke_test.scenarios.screensaver import SCENARIOS as _SCREENSAVER
from tools.smoke_test.scenarios.search import SCENARIOS as _SEARCH
from tools.smoke_test.scenarios.stress import SCENARIOS as _STRESS
from tools.smoke_test.scenarios.view import SCENARIOS as _VIEW
from tools.smoke_test.scenarios.vim_advanced import SCENARIOS as _VIM_ADVANCED
from tools.smoke_test.scenarios.workspace_nav import SCENARIOS as _WORKSPACE_NAV

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
    *_VIM_ADVANCED,
    *_MULTI_CURSOR,
    *_SEARCH,
    *_FILES,
    *_PALETTE_PREVIEW,
    *_GUARDS,
    *_PANES,
    *_EXPLORER,
    *_WORKSPACE_NAV,
    *_VIEW,
    *_DIFFVIEW,
    *_INTEGRATION,
    *_REGRESSION,
    *_SCREENSAVER,
    *_STRESS,
    *_ALIASES,
]
