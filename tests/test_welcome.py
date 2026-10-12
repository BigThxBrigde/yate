"""Unit tests for ``yate.editor_view.welcome`` (welcome-page rows).

Covers the caller-owned (theme, vim_keys) cache contract, the vim-only
ex-command hint, the banner centering flags / padding and the Strip padding
of the row renderer.  The active theme is read only -- nothing here mutates
the process-global theme state.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from yate.editor_view import theme
from yate.editor_view.welcome import (
    _WELCOME_BANNER,
    _WelcomeRow,
    render_welcome_row,
    welcome_rows,
)


def _cache() -> dict[tuple[str, bool], list[_WelcomeRow]]:
    """A fresh caller-owned cache, as the host widget keeps per instance."""
    return {}


# --- welcome_rows cache -------------------------------------------------------


def test_welcome_rows_cache_hits_same_object_for_same_key() -> None:
    t = theme.active()
    cache = _cache()
    first = welcome_rows(t, False, cache)
    assert welcome_rows(t, False, cache) is first
    assert len(cache) == 1


def test_welcome_rows_rebuilds_when_cache_key_changes() -> None:
    t = theme.active()
    cache = _cache()
    vsc_rows = welcome_rows(t, False, cache)
    vim_rows = welcome_rows(t, True, cache)
    assert (t.name, False) in cache
    assert (t.name, True) in cache
    assert vsc_rows is not vim_rows


def test_welcome_rows_vim_hint_present_only_in_vim_mode() -> None:
    t = theme.active()
    cache = _cache()
    hint_text = "  " + ":".ljust(15)
    vim_rows = welcome_rows(t, True, cache)
    assert any(
        any(text == hint_text for text, *_rest in row) for row in vim_rows
    )
    vsc_rows = welcome_rows(t, False, cache)
    # ":" is an ordinary typed character in vsc mode: no hint kbd names it
    assert not any(
        text.strip() == ":" for row in vsc_rows for text, *_rest in row
    )


# --- banner rows ---------------------------------------------------------------


def test_welcome_rows_banner_rows_are_centered_flags_true() -> None:
    t = theme.active()
    cache = _cache()
    rows = welcome_rows(t, False, cache)
    banner_w = max(len(art) for art in _WELCOME_BANNER)
    banner = rows[1:7]
    assert len(banner) == 6
    for row in banner:
        assert len(row) == 1
        text, _color, bold, centered = row[0]
        assert centered is True
        assert bold is False
        # every banner line is ljust-padded to the same width so the
        # per-line centering keeps the figlet block aligned
        assert len(text) == banner_w


# --- render_welcome_row --------------------------------------------------------


def test_render_welcome_row_strip_width_equals_view_width() -> None:
    t = theme.active()
    cache = _cache()
    strip = render_welcome_row(0, 80, 4, t, False, cache)
    assert strip.cell_length == 80


def test_render_welcome_row_pads_gutter_prefix() -> None:
    t = theme.active()
    cache = _cache()
    strip = render_welcome_row(0, 80, 4, t, False, cache)
    first_segment = next(iter(strip))
    assert first_segment.text == " " * 4
