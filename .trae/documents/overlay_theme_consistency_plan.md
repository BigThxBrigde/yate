# Overlay Theme Consistency — Implementation Plan

## Goal

Make every modal/prompt screen (F1 help, F8 manual, changelog, command/file
palette, shell/diagnostics output) use **the same color theme as the running
yate theme**, and remove the temporary global theme switch + save/restore
machinery (`app.theme = "catppuccin-mocha"` / `_prev_doc_theme`) used today by
the manual/changelog viewer.

## Repository Research

### Two parallel theme systems

1. **yate's own palette** — the frozen `Theme` dataclass in
   `yate/editor_view/theme.py` (mocha/frappe/macchiato/latte/onedark/onelight/
   gruvbox-dark/gruvbox-light + user-registered themes in the global
   `THEMES`). All editor chrome and the Rich `Text` bodies of the help/output
   overlays read it through `theme.active()`.
2. **Textual design tokens** (`$primary`, `$surface`, `$text-muted`,
   `$background`, `$panel`, `$text`, …) drive the frame chrome of every
   overlay:
   - `yate/editor_view/modals.py` (HelpScreen / OutputScreen) — border
     `$primary`, bg `$surface`, hint `$text-muted`
   - `yate/editor_view/manual.py` (MarkdownDocScreen) — same tokens plus the
     built-in Markdown widget, whose headings/code/tables use `$primary`,
     `$text`, `$panel`, `$boost`, etc.
   - `yate/editor_view/palette.py` (PaletteScreen) — border/bg tokens
   - `yate/editor_view/commandline.py`, `yate/editor_view/explorer.py`,
     `yate/editor_view/panes.py` also consume tokens in the main UI.

Textual's tokens are **app-global**, generated from the active
`textual.theme.Theme` via `ColorSystem.generate()` (verified in the installed
Textual 8.2.8: `.venv/Lib/site-packages/textual/app.py` `get_css_variables`,
L1418-L1436; tokens cannot be scoped per selector — `$var: value` are
stylesheet-global, so per-screen scoping is not an option).

### Why the screens look different today

- The app normally runs Textual's default `textual-dark` theme → tokens
  resolve to its blue (`#0178D4`) primary — the blue help frame.
- `show_doc()` in `yate/app_features/docs.py` (L22-L50) temporarily sets
  `app.theme = "catppuccin-mocha"` before pushing MarkdownDocScreen and
  restores the previous theme via pop callback, with `_prev_doc_theme`
  declared at `yate/app.py:207` — the mauve manual frame. It only matches
  yate when yate itself runs Mocha; under onedark/gruvbox/custom themes it is
  still forced Catppuccin, and every other overlay stays `textual-dark` blue.

### Chosen approach

**Bridge yate palettes into Textual themes and keep the app permanently on a
yate-derived Textual theme.** Register one Textual theme per yate theme
(named `yate-<yate-theme-name>`, e.g. `yate-mocha`, `yate-onedark`,
`yate-<custom>`) with colors mapped from the corresponding yate `Theme`;
set the app's initial Textual theme from the yate theme chosen at startup,
and switch it inside the existing `YateApp.set_theme()` (`:theme` command).
Because the tokens then equal yate's palette app-wide at all times:

- all overlays match yate with **zero** save/restore state and **zero**
  per-screen theme switching;
- opening a doc never changes/restores anything (first frame is already
  themed);
- the Markdown widget (headings, code fences, tables, links) follows yate;
- palette, inputs, explorer/pane keylines and scrollbars follow yate too.

Token mapping (yate `Theme` → Textual `Theme`), based on how
`ColorSystem.generate()` consumes fields:

| Textual field | yate field | Notes |
|---|---|---|
| `primary` | `accent2` | mauve/purple — overlay borders, markdown h1-h3 (matches the current manual look) |
| `secondary` | `accent` | blue |
| `accent` | `orange` | |
| `warning` | `yellow` | |
| `error` | `red` | |
| `success` | `green` | |
| `foreground` | `fg` | |
| `background` | `bg` | also the modal dim backdrop |
| `surface` | `surface` | |
| `panel` | `panel` | markdown code/tables |
| `dark` | `dark` | |

Extra theme `variables` (these override generated defaults in
`get_css_variables`):

- `text` = `fg`, `text-muted` = `fg_muted`, `foreground-muted` = `fg_dim`
  (exact yate muted colors instead of auto alphas);
- `doc-hit-background` = `"<yellow> 12%"`,
  `doc-hit-current-background` = `"<yellow> 40%"` — replaces the two
  hardcoded Mocha-yellow tints in `manual.py` (current `#f9e2af1f` /
  `#f9e2af66`, ~12%/40% alpha), so manual/changelog search highlights follow
  the active yate theme.

Custom variable references must exist at CSS parse time; the app will provide
the two doc-hit defaults via the `get_theme_variable_defaults()` hook
(built-in extension point, app.py L1399-L1416), derived from the active yate
theme.

### Strict validation for custom themes

Custom themes are arbitrary user Python registered through the injected
`register_theme()` (yaterc / `theme_dirs` / `--theme-dir`). The bridge must
**never** trust their color strings, because a bad value surfaces late and
hard: `ColorSystem.generate()` parses colors when the CSS is refreshed, so an
invalid hex on a registered-but-active theme would crash the whole app, and an
invalid inactive theme would break token generation for every overlay.

Rules enforced by a new `validate_theme(t: Theme) -> list[str]` helper in
`yate/editor_view/theme.py` (returns human-readable problems, empty when
valid), checked with `textual.color.Color.parse` (already a transitive
dependency via Textual):

1. `name` is a non-empty `str`.
2. `dark` is a `bool`.
3. Every color field involved in the Textual mapping (`bg`, `panel`,
   `surface`, `fg`, `fg_dim`, `fg_muted`, `fg_bright`, `accent`, `accent2`,
   `green`, `yellow`, `red`, `orange`) parses as a color; additionally the
   opaque fields (`bg`, `panel`, `surface`, `fg`) must be fully opaque
   (alpha == 1.0) so modal dim/backdrop and overlay bodies composite
   predictably.
4. The two generated doc-hit variables validate as `<hex> <percent>`: the hex
   base parses and the percentage is in `0-100`.

Enforcement points:

- `register_theme()` calls the helper and **raises `ValueError`** listing
  every problem. This is safe for the loader: `load_theme_file()`
  (theme.py L424-L446) already catches exceptions from the theme file exec
  and converts them into a `"<path>: <problem>"` entry in `config.errors`,
  so a malformed custom theme is rejected at load with a clear message and
  never enters `THEMES` — exactly how broken theme files behave today.
  Existing custom-theme tests only register valid palettes (verified:
  test_config.py L707-L724, test_cli.py L29); the `Theme()` string in
  test_user_setup.py L42 is only written to disk, never executed.
- The bridge loop in `YateApp.__init__` still wraps registration/bridging
  defensively: a theme that somehow passed registration but fails bridging
  is skipped and recorded in `self.config.errors` (never fatal). If the
  selected startup theme is missing/invalid, fall back to the built-in
  `mocha` bridge instead of leaving `app.theme` on an unregistered name
  (the reactive validator would raise `InvalidThemeError`).

Exactness check of the mapping itself: a test iterates **every** built-in
yate theme and asserts the generated Textual theme carries the exact yate
hex values field by field (`primary == accent2`, `secondary == accent`,
`background == bg`, `surface == surface`, `panel == panel`,
`foreground == fg`, `variables["text"] == fg`,
`variables["text-muted"] == fg_muted`,
`variables["foreground-muted"] == fg_dim`, warning/error/success/accent),
that `dark` matches, and that `to_color_system().generate()` succeeds with
no exceptions — guaranteeing the mapped colors are acceptable to Textual.

## Files and Modules

- `yate/editor_view/theme.py` — add the bridge (mapping + naming helper) and
  strict theme validation; make `register_theme()` reject invalid colors.
- `yate/app.py` — register yate Textual themes at startup, pick initial one,
  switch in `set_theme()`, add defaults hook; delete `_prev_doc_theme`.
- `yate/app_features/docs.py` — strip theme switch/restore from `show_doc()`.
- `yate/editor_view/manual.py` — search-hit CSS uses the new variables;
  docstring/comment updates.
- `tests/test_app_textual.py` — update F8 theme assertions; add bridge/
  follow-the-theme tests.
- `tests/test_changelog_view.py` — update the fake-app wiring tests for the
  no-switch behavior.

No CSS/token changes in `modals.py`, `palette.py`, `commandline.py`,
`explorer.py`, `panes.py` — they already consume tokens and will follow
automatically.

## Implementation Steps

1. **Validation + bridge in `yate/editor_view/theme.py`**
   - Import `from textual.color import Color` and
     `from textual.theme import Theme as TextualTheme`.
   - Add `TEXTUAL_THEME_PREFIX = "yate-"` and
     `textual_theme_name(name) -> str` returning `f"yate-{name}"`.
   - Add module-level tuple of the color fields the bridge consumes and an
     `_OPAQUE_FIELDS` subset; implement
     `validate_theme(t: Theme) -> list[str]` per the rules above (empty
     list = valid; parse each value with `Color.parse`, catching
     `ValueError`; check alpha of opaque fields; validate doc-hit alpha
     syntax).
   - Make `register_theme(theme)` run `validate_theme` first and raise
     `ValueError` with the joined problems on failure (built-ins bypass it
     because they are constructed directly in `THEMES`).
   - Add `to_textual_theme(t: Theme) -> TextualTheme` that asserts
     validation up front (defensive; raises on misuse) and implements the
     mapping table and `variables` map above (hex strings are plain
     `#rrggbb` on yate fields; alpha-suffixed values use Textual's
     `" 12%"` syntax).
2. **App wiring in `yate/app.py`**
   - In `__init__`, right after the existing `theme.set_theme(...)`
     try/except (L163-L167) and after `YateConfig` has registered custom
     themes into `THEMES`: loop `theme.THEMES.values()`, call
     `self.register_theme(theme.to_textual_theme(yt))` inside a
     per-theme try/except that appends `"yate theme '<name>': <error>"` to
     `self.config.errors` and skips on failure, then set
     `self.theme` to `textual_theme_name(theme.active().name)`, guarded by
     an availability check that falls back to `yate-mocha` (and records an
     error) if the selected theme has no usable bridge. Must run after
     `super().__init__()` (which seeds built-in Textual themes) and before
     the reactive is assigned (its validator requires registration).
   - Remove `self._prev_doc_theme` (L207).
   - In `set_theme()` (L564-L576): after `theme.set_theme(name)` succeeds,
     lazily ensure the bridge exists (an extension may register a yate
     theme after startup): if `self.get_theme(textual_theme_name(name))` is
     None, build and `register_theme()` it through the same defensive
     try/except as startup; then set
     `self.theme = theme.textual_theme_name(name)` (the reactive watcher
     regenerates tokens and repaints); keep `apply_theme()` and the success
     message. Unknown names still take the existing KeyError branch.
   - Add `get_theme_variable_defaults()` returning the two doc-hit variables
     from `theme.active()` so the manual CSS parses under any Textual theme.
3. **Simplify `yate/app_features/docs.py`**
   - `show_doc()` keeps only the mounted / not-already-on-doc-screen guard
     and the `app._push_overlay(MarkdownDocScreen(...))` call — no callback,
     no theme mutation. Delete `_restore_theme()`; update the module
     docstring (the `_prev_doc_theme` contract is gone).
4. **Manual screen in `yate/editor_view/manual.py`**
   - `.doc-hit { background: $doc-hit-background; }` and
     `.doc-hit-current { background: $doc-hit-current-background; }`
     (keep `text-style: bold`).
   - Update the module docstring (L4-L7) and the CSS comment (L213-L214)
     that claim the viewer is always Catppuccin Mocha.
5. **Tests**
   - `tests/test_app_textual.py`, `test_f8_opens_manual_and_esc_closes`
     (L1239-L1249): while open assert `app.theme == "yate-mocha"`; after
     esc assert it is **still** `"yate-mocha"` (no restore).
   - Add a startup test: after `run_test()`, `app.theme == "yate-mocha"` and
     `app.get_theme("yate-mocha")` is not None; custom yate themes from
     yaterc also get a `yate-<name>` Textual theme.
   - Add a follow-the-theme test: run `:set theme latte` →
     `app.theme == "yate-latte"`; open F1 and resolve the overlay border:
     `screen.query_one("#overlay").styles.border.color` parses to the Latte
     `accent2` hex (`#8839ef`). Repeat one dark non-Mocha theme (e.g.
     `onedark`, primary `#c678dd`) to prove the blue `textual-dark` frame is
     gone.
   - `tests/test_changelog_view.py`: drop `_prev_doc_theme` from `_FakeApp`;
     rename `test_show_changelog_pushes_doc_screen_and_switches_theme` to
     `..._pushes_doc_screen_without_changing_theme` — assert the screen is
     pushed, `callback is None`, and the sentinel `app.theme` is untouched;
     the not-mounted test keeps asserting no push and unchanged theme.
   - **Strict validation tests (new, primarily in
     `tests/test_theme_palettes.py`):**
     - exact-mapping test over every built-in theme: the field-by-field
       equality listed under "Strict validation" above, plus
       `to_color_system().generate()` returns without raising and contains
       `primary`, `surface`, `text`, `text-muted`, `markdown-h1-color`;
     - `validate_theme(THEMES["mocha"])` returns `[]`;
     - malformed custom themes are rejected with problems naming the bad
       field: bad hex (`bg="#gggggg"`), empty name, `dark="yes"`, and a
       translucent background (`bg="#1e1e2e80"`) each return at least one
       problem; `register_theme(bad)` raises `ValueError` and leaves
       `THEMES` unchanged;
     - end-to-end through the loader: a theme file with an invalid color
       produces a non-empty `config.errors` entry via `load_theme_paths`
       (and inline `register_theme(...)` in a yaterc via `load_config`),
       and the bad theme is not registered;
     - app startup with an invalid selected theme does not crash and falls
       back to the `yate-mocha` bridge with an error recorded in
       `config.errors`; a **valid** custom theme gets a working
       `yate-<name>` bridge whose overlay border resolves to its
       `accent2` hex.

## Dependencies and Considerations

- Textual 8.2.8 is already the project dependency; `register_theme`, the
  `theme` reactive and `get_theme_variable_defaults` are public API.
- This is a **global token change**, not an overlay-only one: default
  foregrounds/backgrounds of explorer, inputs, option lists, pane keylines
  and scrollbars now derive from the yate palette. That is the intended
  outcome of "all prompt screens keep the same theme", and the main editor
  chrome is already painted explicitly from yate colors, so the visual delta
  is mainly accent-colored details becoming on-palette.
- Light themes (`latte`, `onelight`, `gruvbox-light`): `dark=False` flips
  ModalScreen dimming, auto text-alpha blending and generated shades; verify
  manually under a light theme.
- `:theme` switching while an overlay is open is not reachable through key
  dispatch (modals swallow keys) and needs no special handling.
- User themes registered via yaterc / `--theme-dir` are in `THEMES` before
  `YateApp.__init__`, so they get bridged automatically.
- The Textual theme-palette command palette remains disabled
  (`ENABLE_COMMAND_PALETTE = False`); yate's `:theme` is the only switcher.

## Validation

1. Targeted:
   `python -m pytest tests/test_app_textual.py tests/test_changelog_view.py tests/test_theme_palettes.py tests/test_config.py -q`
   — must include the strict-validation and loader-error cases.
2. Full suite: `python -m pytest -q` (baseline: 546 passed).
3. `pyright` — expect 0 errors / 0 warnings.
4. Visual smoke (each: mocha, onedark, gruvbox-dark, latte): F1 help, F8
   manual (incl. `/` search hit tints), `:changelog`, ctrl+p palette,
   `:!ls` output — frame/bg/headings/scrollbars match the editor; run
   `:set theme=<other>` from the editor and reopen each overlay.

## Risks

- **Global look-and-feel shift in the main UI** — mitigated by explicit
  yate-colored styling on all primary chrome; full-suite + multi-theme
  visual smoke catch token-derived surprises.
- **Unknown/custom theme name edge** — bridge is registered before the
  reactive assignment; unknown names fail in `theme.set_theme()` first and
  keep the existing error path.
- **Malformed colors in a custom theme** — rejected up front by
  `validate_theme()` inside `register_theme()`, surfaced as a
  `config.errors` entry through the already-existing exception handling in
  both `load_theme_file()` and `load_config()`; such a theme never reaches
  `THEMES`, the bridge, or `ColorSystem.generate()`, so it cannot crash CSS
  token generation. Startup falls back to `yate-mocha` when the selected
  theme's bridge is unusable.
- **Over-strict rejection of legitimate themes** — every shipped palette
  (8 built-ins + the two `*.example` templates: Dracula, Ayu) passes
  validation via the all-built-ins exact-mapping test; `on_accent` and the
  `syn_*` fields are deliberately excluded from opacity checks (they are not
  mapped and may legitimately differ).
- **CSS parse failure on custom variables** — mitigated by
  `get_theme_variable_defaults()`; CSS refresh happens on mount after
  registration.
- **Stale tests relying on `textual-dark` / catppuccin pin** — enumerated in
  step 5; grep found no color-value assertions against the old tokens.
