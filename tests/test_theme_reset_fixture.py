"""Pin the conftest autouse theme-state reset (worker-parallel isolation).

``yate.editor_components.theme`` keeps the active theme in module globals, so
a test that switches themes would otherwise leak into every later test of the
same xdist worker whenever the autouse ``reset_theme_state`` fixture in
``conftest.py`` stops restoring the default after every test.  This single
test drives the switch itself and then invokes the fixture's teardown helper
(:func:`conftest._theme_state_teardown`) directly -- pytest 9 forbids calling
fixtures directly (m24) -- so it passes or fails identically on any worker
and on any worker assignment (the previous two-test pairing depended on
definition-order execution on one xdist worker, which ``--dist load`` does
not guarantee).
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from conftest import _theme_state_teardown
from yate.editor_components import theme


def test_theme_state_is_reset_after_each_test() -> None:
    """Switch themes, then verify the fixture teardown undid it."""
    theme.set_theme("latte")
    assert theme.active().name == "latte"
    # Drive the teardown exactly as the fixture does after this test body:
    # listeners cleared first, then the default restored (unbroadcast).
    _theme_state_teardown()
    assert theme.active().name == theme.DEFAULT_THEME
    assert not theme._listeners
