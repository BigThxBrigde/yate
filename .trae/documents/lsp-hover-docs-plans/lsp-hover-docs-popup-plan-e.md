# Plan e — self-contained hover card (wave-2, L2)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), decision D4

## Input

- `yate/editor_components/completion.py:78-179` (`can_focus=False`,
  `DEFAULT_CSS = load_tcss(...)`, `show()`/`close()`, `styles.offset`,
  overflow flipping).
- `yate/editor_components/manual.py:146-165` (`render_doc_lines` pure
  Markdown→`Strip` measurement with `theme.active()`), `:41` (`rich.markdown`).
- `yate/editor_components/scrollbars.py:94-130`,
  `yate/editor_components/theme/__init__.py:174-193` (attach/detach),
  `yate/editor_components/view.py:206-228` (mount/unmount pattern).
- `yate/paths.py::load_tcss`; `yate/resources/completion-popup.tcss` as a
  formatting precedent; R9 component-owned ids, R13, R15.

## Exclusive files

- `yate/editor_components/hover_popup.py` (new)
- `yate/resources/hover-popup.tcss` (new)
- `tests/test_hover_popup.py` (new)

## Concrete changes

1. `yate/editor_components/hover_popup.py` — module docstring in English
   (ASCII), `from __future__ import annotations`, then imports grouped
   stdlib / third-party / `yate`. Define:

   ```python
   class HoverPopup(VerticalScroll):
       """Non-focusable floating Markdown card for LSP hover docs."""
   ```

   - `can_focus = False`; `DEFAULT_CSS = load_tcss("hover-popup.tcss")`.
   - constants `MAX_ROWS: int = 12`, `MIN_WIDTH: int = 24`,
     `MAX_WIDTH: int = 72`, each with `#:` comments.
   - `compose()` yields one `Static("", id="hover-docs-body")`; keep the
     reference via `self.query_one(...)` in `show` (no new protocol/types).
   - `is_open` property: `bool(self.display) and bool(self._text)`.
   - `show(text: str, anchor: tuple[int, int], inner_size: tuple[int, int],
     gutter: int, origin_y: int = 0) -> None`:
     - `if not text.strip(): self.close(); return` (second AC5 defence).
     - `box_w = max(MIN_WIDTH, min(MAX_WIDTH, max(theme.cell_len(line) for
       line in text.splitlines()) + 2))`; compute the row count with
       `render_doc_lines(text, box_w - 2, active=theme.active())` and
       `box_h = min(MAX_ROWS, len(rows) + 2)`.
     - horizontal/vertical flipping copied from `completion.py:142-153`
       (`x = min(gutter + anchor[0], max(0, inner_size[0] - box_w))`,
       below-else-above for y), then `styles.width/height/offset =
       ScalarOffset.from_offset((x, y))`.
     - update the `Static` with `Markdown(text)` (Rich renderable), set
       `display = True`, `refresh()`.
   - `close() -> None`: clear `_text`, clear the body, `display = False`.
   - `on_mount`: `display = False`; `apply_slim_scrollbars(self)`;
     `_apply_theme()`; `theme.attach(self, self._apply_theme)`.
   - `on_unmount`: `theme.detach(self)`.
   - `_apply_theme()`: `t = theme.active()`; set `styles.background = t.panel`,
     `styles.color = t.fg`; `apply_scrollbar_theme(self)`; `refresh()`.
     **R13**: the component owns all painting; no L3 code touches its styles.
   - **R15**: the module contains both `apply_slim_scrollbars` and
     `apply_scrollbar_theme` calls, as required by
     `test_scrollable_widgets_apply_theme_scrollbar_pair`.
   - No `Any`, no `TYPE_CHECKING`, no relative imports, `log =
     tracing.get_logger(__name__)` only if a debug line is needed (lazy `%`).
2. `yate/resources/hover-popup.tcss` — header comment: "selector id frozen by
   R9: `#hover-docs`; component-owned CSS, not referenced by app.tcss".
   Rules for `#hover-docs` and `#hover-docs-body` using Textual theme tokens
   (`$panel`, `$foreground`, `$accent`), `border: round $accent`,
   `padding: 0 1`, `height: auto`, `max-height`, `overflow-y: auto`; no
   hard-coded colors. The id is passed by the Editor in plan h.
3. Keep the module under 800 lines (expected ~130); no
   `SIZE_EXEMPT_FILES` change.

## Tests (`tests/test_hover_popup.py`)

Use the no-App construction pattern from `tests/test_completion_popup.py:29-43`
for pure geometry where possible, and `app.run_test()` for mount/theme tests.
Use `theme.active()` snapshots; no real sleeps.

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_show_with_empty_or_whitespace_text_closes_card` | parametrized `""`, `"  \n "` | `is_open is False`, `display is False` |
| `test_show_positions_card_below_anchor` | `inner_size=(80,24)`, `anchor=(10,5)`, `gutter=6`, `origin_y=2` | `styles.offset` resolves to `(16, 8)` (gutter+col, origin+bottom) |
| `test_show_flips_above_when_bottom_overflows` | `anchor=(5, 22)` with a 10-row card | resulting y is above the anchor and `>= origin_y` |
| `test_show_clamps_x_when_card_would_overflow_right_edge` | `anchor=(78, 3)` | `x == inner_size[0] - box_w` and `x >= 0` |
| `test_show_renders_markdown_source_in_body` | `text = "**f()** docs"` | `query_one(...).renderable` is a `Markdown` whose `markup` equals the text |
| `test_long_text_caps_card_height` | 40-line text | `styles.height <= MAX_ROWS` |
| `test_card_never_grabs_focus` | construct | `HoverPopup.can_focus is False` and `popup.can_focus is False` |
| `test_mount_applies_scrollbar_pair_and_theme_subscription` | monkeypatch the two scrollbar functions and `theme.attach` with spies, mount in pilot | each spy called once with the popup; `attach` received `popup._apply_theme` |
| `test_theme_change_repaints_scrollbar_theme` | call `theme.set_theme(...)` (or `_apply_theme()` directly) | `apply_scrollbar_theme` spy called again and `styles.background` equals `theme.active().panel` |
| `test_unmount_detaches_theme_listener` | mount then unmount | `theme.detach` spy called with the popup |
| `test_close_hides_card_and_clears_body` | show then close | `display is False`, `_text == ""`, body renderable empty |
| `test_architecture_scrollbar_pair_guard_covers_new_widget` | run `tests/test_architecture.py::test_scrollable_widgets_apply_theme_scrollbar_pair` | exit code 0 |

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_popup.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_completion_popup.py tests/test_architecture.py -q -n 1
```

Both exit codes 0. The architecture suite here is a deliberate early check of
R15/R9 before the wiring wave.

## Risks and rollback

- Risk: `Static.update(Markdown(...))` may need an explicit `rich` renderable
  adaptation on Textual 8.2.8. If it fails, keep the same public API and
  render the `Strip` rows from `render_doc_lines` through a small child
  `Widget.render_line` instead; **report the deviation with the failing
  command output** before changing the design.
- Risk: `scroll_offset` unit tests depend on `ScalarOffset` internals. Assert
  via `popup.styles.offset.x`/`.y` values rather than a string representation;
  if that is unstable, assert on the resolved `(x, y)` helper used by
  `completion.py` tests.
- Risk: theme token names differ (`$foreground` vs `$text`). Copy the exact
  tokens from `completion-popup.tcss` / another component tcss; never invent
  a hard-coded color.
- Rollback: revert this commit; plan g/h are the only consumers (wave 3/4).
