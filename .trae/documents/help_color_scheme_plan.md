# Help Overlay Color Scheme Fix — Implementation Plan

## Goal

The F1 / `:help` overlay should render with the **same color scheme as the F8
user manual**: mauve (`$primary`) border, Catppuccin Mocha surface, muted hint
and matching scrollbar — instead of today's blue frame from Textual's default
`textual-dark` theme. Scope is the help overlay only.

## Repository Research

Two overlays, two color mechanisms:

- **Manual / changelog** — `MarkdownDocScreen` in `yate/editor_view/manual.py`
  (L143-L228): chrome comes from Textual design tokens
  (`border: tall $primary`, `background: $surface`,
  `color: $text-muted`). `show_doc()` in `yate/app_features/docs.py`
  (L22-L34) sets `app.theme = "catppuccin-mocha"` **before** pushing the
  screen and restores the previous theme in the pop callback. Result: the
  pink/mauve frame in screenshot 1.
- **F1 help** — `HelpScreen` in `yate/editor_view/modals.py` (L61-L111) via
  `_OverlayScreen.DEFAULT_CSS` (L31-L46): it uses the **same** tokens, but
  `YateApp.show_help()` in `yate/app.py` (L1402-L1405) never switches
  `app.theme`, so the tokens resolve against `textual-dark` → the blue
  frame/scrollbar in screenshot 2. The body is a Rich `Text` colored from
  yate's own `theme.active()` (`yate/editor_view/theme.py`, L376-L378;
  Mocha by default: blue title, mauve categories, green keys) — only the
  frame chrome is wrong.

The Mocha pin is an existing, intentional pattern (see the module docstring
of `yate/editor_view/manual.py`, L1-L8); the help overlay was simply never
wired into it. Both entry points to help — the `f1` keymap action
(`yate/keymaps/vsc.py` → `yate/actions.py` L167) and `:help`
(`yate/app_features/commands.py` L185) — route through the single
`YateApp.show_help()` method.

`OutputScreen` shares `_OverlayScreen` CSS but is deliberately **out of
scope**.

## Files and Modules

- `yate/app.py` — the only production change.
- `tests/test_app_textual.py` — extend the existing help test.

No changes to `yate/editor_view/modals.py`, `yate/editor_view/manual.py`,
`yate/app_features/docs.py`, keymaps, or CSS.

## Implementation Steps

### 1. Add a restore flag in `YateApp.__init__`

Next to `self._prev_doc_theme` at `yate/app.py:207`:

```python
self._prev_doc_theme: Optional[str] = None
self._prev_help_theme: Optional[str] = None
```

A separate flag (not reusing `_prev_doc_theme`) so that if overlays ever
stack (e.g. help underneath the manual), each pop restores the theme saved by
its own push — the flags cannot clobber each other.

### 2. Pin / restore the theme in `show_help()`

Replace `show_help()` (`yate/app.py:1402-L1405`) with the same
pin-before-push pattern as `docs.show_doc` (switching before push avoids an
unthemed first frame; the `push_screen` callback fires for every dismiss
path — esc, q, ctrl+c):

```python
def show_help(self) -> None:
    """Open the keybinding reference overlay."""
    if not self.mounted:
        return
    # The overlay chrome is styled via Textual design tokens ($primary /
    # $surface / $text-muted); pin Catppuccin Mocha for the overlay's
    # lifetime so F1 matches the F8 manual, then restore on dismiss.
    self._prev_help_theme = self.theme
    self.theme = "catppuccin-mocha"
    self._push_overlay(
        HelpScreen(self),
        callback=lambda _result: self._restore_help_theme(),
    )

def _restore_help_theme(self) -> None:
    """Return to the theme in use before the help overlay opened."""
    if self._prev_help_theme is not None:
        self.theme = self._prev_help_theme
        self._prev_help_theme = None
```

`_push_overlay` (already used here) also resets the stale bottom message;
its behavior is unchanged. Setting `app.theme` only swaps Textual tokens and
does not affect yate's global `theme.set_theme()` palette used by the editor.

### 3. Extend the help test

In `test_help_lists_terminal_key_and_commands`
(`tests/test_app_textual.py:3409`), after the existing body assertions,
mirror the manual test's theme checks
(`test_f8_opens_manual_and_esc_closes`, L1221-L1251):

```python
# chrome uses the same pinned Catppuccin Mocha theme as the F8 manual
assert app.theme == "catppuccin-mocha"
await pilot.press("escape")
await pilot.pause()
assert not isinstance(app.screen, HelpScreen)
assert app.theme == "textual-dark"
```

## Dependencies and Considerations

- `catppuccin-mocha` is a Textual built-in theme name already used by
  `yate/app_features/docs.py` — no new dependency, CSS, or token mapping.
- With the default Mocha yate theme, help body colors already equal
  Catppuccin Mocha's. With a non-Mocha yate theme selected, the help body
  keeps following the user's theme while the frame is pinned Mocha — exactly
  the trade-off the manual already makes today; this is what makes the two
  overlays consistent with each other.
- If the app quits while the overlay is open the restore callback is
  skipped; the process is exiting, so no state leaks.

## Validation

1. Targeted tests:
   `python -m pytest tests/test_app_textual.py -k "help or manual or overlay or changelog" -q`
2. Full suite: `python -m pytest -q` (baseline: 546 passed).
3. `pyright` — expect 0 errors / 0 warnings (project convention).
4. Visual smoke check: launch yate → `F1` shows the mauve frame and mocha
   surface identical to `F8`; esc/q restores; `:help` behaves the same.

## Risks

- **Theme left switched after close** — low: uses the identical
  save/restore-via-pop-callback mechanism already proven for the manual, and
  the test asserts restoration to `textual-dark`.
- **First-frame flash** — avoided by setting `app.theme` before
  `push_screen`, same as the manual.
- **Stacked overlays** — handled by the independent `_prev_help_theme` flag.
