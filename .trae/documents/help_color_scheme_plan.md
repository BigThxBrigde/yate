# Help Overlay Color Scheme Fix — Implementation Plan

## Repository Research

The two overlays in the screenshots are implemented separately and get their
colors from two different mechanisms:

- **User Manual / Changelog** — [MarkdownDocScreen](file:///e:/Jermaine/yate/yate/editor_view/manual.py#L143-L228) (F8 / `:manual`). Its chrome is driven by Textual design
  tokens in `DEFAULT_CSS` (`border: tall $primary`, `background: $surface`,
  `.hint { color: $text-muted }`). Before it is pushed,
  [show_doc()](file:///e:/Jermaine/yate/yate/app_features/docs.py#L22-L34) switches Textual's reactive
  `app.theme` to the built-in **`catppuccin-mocha`** and restores the previous
  theme via the screen-pop callback (`_restore_theme`). That is why the manual
  has the mauve/pink border and dark mocha surface (screenshot 1).

- **F1 Help** — [HelpScreen](file:///e:/Jermaine/yate/yate/editor_view/modals.py#L61-L111) (F1 / `:help`). It
  subclasses `_OverlayScreen`, whose [DEFAULT_CSS](file:///e:/Jermaine/yate/yate/editor_view/modals.py#L31-L46)
  uses the **same** tokens (`$primary`, `$surface`, `$text-muted`), but
  [YateApp.show_help()](file:///e:/Jermaine/yate/yate/app.py#L1402-L1405) never switches `app.theme`. The
  tokens therefore resolve against Textual's default `textual-dark` theme,
  producing the blue border / blue scrollbar in screenshot 2. The body text
  itself is a Rich `Text` colored explicitly from yate's own
  [`theme.active()`](file:///e:/Jermaine/yate/yate/editor_view/theme.py#L376-L378) palette (blue title,
  mauve category headers, green keys — already the Mocha palette by default),
  so only the **frame/scrollbar/hint chrome** is inconsistent.

The manual's Catppuccin pin is intentional (documented in the
[manual.py module docstring](file:///e:/Jermaine/yate/yate/editor_view/manual.py#L1-L8): the Markdown
widget's built-in styling follows Textual design tokens, and Mocha matches
yate's default palette). The help overlay was simply never brought under the
same pin.

Conclusion / fix direction: pin `app.theme` to `catppuccin-mocha` for the
lifetime of `HelpScreen`, exactly like the manual, and restore the previous
theme when it is dismissed. The body colors already match Mocha; this makes
border, background, scrollbar and footer hint match the manual.

### Overlay nesting / state-flag analysis

The manual uses `self._prev_doc_theme` (declared at
[app.py:207](file:///e:/Jermaine/yate/yate/app.py#L207)). A **separate** flag
(`_prev_help_theme`) will be used for help so the two overlays' save/restore
cycles cannot clobber each other if they ever stack (e.g. help saved
`textual-dark`, manual on top saves `catppuccin-mocha` and restores it, then
help closes and restores `textual-dark`). In practice modal key dispatch
prevents opening a second overlay while one is up, so no anti-stacking guard
is required.

`OutputScreen` (shell/diagnostics output) shares `_OverlayScreen` CSS and has
the same blue chrome today, but it is out of scope for this request and will
not be changed.

## Files and Modules

- `yate/app.py`
  - `__init__` (near line 207): initialize `self._prev_help_theme: Optional[str] = None`.
  - `show_help()` (lines 1402–1405): save `self.theme`, switch to
    `"catppuccin-mocha"` before pushing (so the first frame is already
    themed — same rationale as `docs.show_doc`), push `HelpScreen` through
    `_push_overlay` with a pop callback that restores the saved theme.
- `tests/test_app_textual.py`
  - Extend `test_help_lists_terminal_key_and_commands` (line 3409) with theme
    assertions mirroring `test_f8_opens_manual_and_esc_closes`:
    `app.theme == "catppuccin-mocha"` while the help screen is up, then after
    `escape` the screen is no longer `HelpScreen` and
    `app.theme == "textual-dark"` (Textual's default in the test harness).

No changes needed in `modals.py` (its CSS tokens resolve correctly once the
app theme is pinned), the manual viewer, keymaps, or docs.

## Implementation Steps

1. In `YateApp.__init__`, add `self._prev_help_theme: Optional[str] = None`
   next to `self._prev_doc_theme`.
2. In `YateApp.show_help()`:
   - keep the existing `self.mounted` guard;
   - save `self._prev_help_theme = self.theme`;
   - set `self.theme = "catppuccin-mocha"`;
   - call `self._push_overlay(HelpScreen(self), callback=...)` where the
     callback restores the saved theme and clears the flag (mirror
     `docs._restore_theme`, including the `is not None` guard so restore
     runs at most once).
3. Extend the help test with the open/close theme assertions above.

## Dependencies and Considerations

- `catppuccin-mocha` is a Textual built-in theme name already relied on by
  `app_features/docs.py`; no new dependency or CSS is introduced.
- The body Rich text uses yate's global `theme.active()`, not Textual tokens:
  with the default Mocha theme the colors are identical to Catppuccin Mocha.
  With a non-Mocha yate theme selected, the help body follows the user's
  theme while the chrome is pinned Mocha — this is the same trade-off the
  manual already makes, and is what makes the two overlays consistent.
- F1 (keymap `help` action in `keymaps/vsc.py`) and `:help`
  (`app_features/commands.py`) both route through `show_help()`, so one
  change covers both entry points.
- Setting/restoring `app.theme` only swaps Textual design tokens; it does not
  touch yate's global `theme.set_theme()` state used by the editor chrome.

## Validation

- `python -m pytest tests/test_app_textual.py -k "help or manual or overlay or changelog" -q`
- Full suite: `python -m pytest -q` (expect 0 failures; baseline 546 passed).
- `pyright` on the changed files / project (expect 0 errors, 0 warnings per
  project convention).
- Manual smoke check: launch yate, press F1 — border/surface/scrollbar/hint
  should match the F8 manual (mauve border, dark mocha surface); `esc`/`q`
  returns to the normal theme; verify `:help` behaves identically.

## Risks

- **Theme not restored if the dismiss callback is bypassed:** the manual uses
  the same callback mechanism (`push_screen(..., callback=...)` fires on any
  dismiss path — esc/q/ctrl+c), and existing tests prove restoration.
  Mitigation: mirror that mechanism exactly and assert restoration in the
  help test.
- **First-frame unthemed flash:** mitigated by switching `app.theme`
  *before* `push_screen`, as `docs.show_doc` already does.
- **Nested overlays clobbering the saved theme:** mitigated by a separate
  `_prev_help_theme` flag rather than reusing `_prev_doc_theme`.
