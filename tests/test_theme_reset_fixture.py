"""Pin the conftest autouse theme-state reset (worker-parallel isolation).

``yate.editor_view.theme`` keeps the active theme in module globals, so a
test that switches themes would otherwise leak into every later test of the
same xdist worker whenever its manual restore line is skipped.  The autouse
``reset_theme_state`` fixture in ``conftest.py`` restores the default after
every test; these two tests fail in definition order once that teardown
stops running -- the second one only passes if the first one's switch was
undone (on the same worker; on separate workers both pass trivially).
"""

from __future__ import annotations

from yate.editor_view import theme


def test_theme_switch_takes_effect_within_a_test() -> None:
    """Sanity anchor: the switch below really changes the global state."""
    theme.set_theme("latte")
    assert theme.active().name == "latte"


def test_theme_state_is_reset_after_each_test() -> None:
    """The previous test switched to latte; the autouse fixture undid it."""
    assert theme.active().name == theme.DEFAULT_THEME
