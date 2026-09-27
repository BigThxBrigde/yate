"""Tests for theme change subscription (widgets own their theme painting)."""

from __future__ import annotations

from collections.abc import Callable

from yate.editor_view import theme


def test_subscribe_listener_notified_on_set_theme() -> None:
    """A subscribed listener runs after every successful set_theme."""
    calls: list[str] = []
    unsubscribe: Callable[[], None] = theme.subscribe(lambda: calls.append("hit"))
    try:
        theme.set_theme("latte")
        theme.set_theme("mocha")
        assert calls == ["hit", "hit"]
    finally:
        unsubscribe()
        theme.set_theme("mocha")


def test_unsubscribe_stops_notifications_and_is_idempotent() -> None:
    """After unsubscribing (twice) the listener is never called again."""
    calls: list[str] = []
    hit = lambda: calls.append("hit")  # noqa: E731 - trivial test double
    unsubscribe = theme.subscribe(hit)
    unsubscribe()
    unsubscribe()  # second removal must be a no-op, not ValueError
    try:
        theme.set_theme("latte")
        assert calls == []
    finally:
        theme.set_theme("mocha")


def test_failing_listener_does_not_block_broadcast() -> None:
    """A raising subscriber is isolated; later subscribers still run."""
    calls: list[str] = []

    def bad() -> None:
        raise RuntimeError("boom")

    unsubscribe_bad = theme.subscribe(bad)
    unsubscribe_good = theme.subscribe(lambda: calls.append("after"))
    try:
        theme.set_theme("latte")
        assert calls == ["after"]
    finally:
        unsubscribe_bad()
        unsubscribe_good()
        theme.set_theme("mocha")


def test_failed_set_theme_does_not_notify() -> None:
    """An unknown theme raises KeyError without touching subscribers."""
    calls: list[str] = []
    unsubscribe = theme.subscribe(lambda: calls.append("hit"))
    try:
        try:
            theme.set_theme("no-such-theme")
        except KeyError:
            pass
        else:
            raise AssertionError("set_theme must raise KeyError for unknown names")
        assert calls == []
    finally:
        unsubscribe()
