# Plan a — Shared result model and docked panel

Parent: [`../quickfix-nav-plan.md`](../quickfix-nav-plan.md). Rules: [`../../rules/python-coding-style.md`](../../rules/python-coding-style.md), [`../../rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md).

## Input / output

Input: diagnostics/search/reference payload facts in the parent plan §3.
Output: an inert but independently testable L1 model and L2 panel; no Editor wiring yet.

## Exclusive files

- `yate/session.py`
- `yate/editor_components/quickfix_panel.py` (new)
- `tests/test_quickfix_model.py` (new)
- `tests/test_quickfix_panel.py` (new)

## Concrete changes

1. `yate/session.py` (near `JumpEntry`, current lines 125-132): add frozen dataclass `QuickFixEntry` with `provider: str`, `path: Path`, `row: int`, `col: int`, `label: str`, `detail: str = ""`, `severity: str = ""`; positions are 0-based. Add class `QuickFixList` with `entries: tuple[QuickFixEntry, ...]`, `selected: int`, `label: str`, methods `replace(provider, entries, label) -> None`, `clear() -> None`, `at(index) -> QuickFixEntry | None`, `current() -> QuickFixEntry | None`, `step(delta) -> QuickFixEntry | None` (wrap-around, empty-safe), `snapshot() -> tuple[QuickFixEntry, ...]`. `replace` drops every prior entry of the same provider before appending, resets selection to `0` when the previous selection is invalid, and keeps pure-data semantics (no widget, document, callback or server reference).
2. `yate/editor_components/quickfix_panel.py` (new, L2): module docstring states injected callbacks and R13/R15 ownership. Define `type PickFn = Callable[[int], None]` and `type CloseFn = Callable[[], None]` via PEP 695. Class `QuickFixPanel(VerticalScroll)` with `__init__(entries: QuickFixList, *, on_pick: PickFn, on_close: CloseFn, id: str = "quickfix-panel")`; compose a `Static(id="quickfix-body")` showing either `(no results)` or one line per entry (`provider | severity | label @ path:line:col`, selected line prefixed `> `). `on_mount` calls `apply_slim_scrollbars(self)`, `theme.attach(self, self._paint)`; `_paint` calls `apply_scrollbar_theme(self)`; `on_unmount` calls `theme.detach(self)`. `on_key` consumes `up/down/enter/escape` only: up/down call `entries.step(±1)` then `_paint` and `scroll_to` if needed; enter calls `on_pick(entries.selected)`; escape calls `on_close()`. Every handled key calls `event.stop()` + `event.prevent_default()`; other keys fall through (R10).
3. No new `Protocol`, `TYPE_CHECKING`, `Any`, `print`, non-ASCII comment or relative import. All comments/docstrings English.

## Tests (case name → arrange / act / assert)

- `tests/test_quickfix_model.py::test_replace_drops_only_the_same_provider_and_wraps_selection`: `QuickFixList` seeded with diagnostics `[d1,d2]` and search `[s1]`; replace references `[r1,r2]`; assert `snapshot() == (d1,d2,s1,r1,r2)`, `selected == 0`; replace diagnostics `[d3]`; assert no `d1/d2`, `(d3,s1,r1,r2)`; `step(-1)` returns `r2` and sets `selected == 3`.
- `...::test_clear_and_empty_step_are_safe`: clear a non-empty list; assert snapshot `()`, `current() is None`, `step(1) is None`, `selected == 0`.
- `...::test_entries_are_immutable_pure_data`: `replace` a list, mutate the source list; assert snapshot unchanged; `dataclasses.is_dataclass(entry)` and `frozen` assignment raises `FrozenInstanceError`.
- `tests/test_quickfix_panel.py::test_panel_renders_entries_and_empty_state`: minimal host `App` pushes a panel around a `QuickFixList`; use `plain_text` on `#quickfix-body`; assert non-empty text contains provider, severity, `path.name`, 1-based line/col and `>` marker; clear list and call `_paint`; assert `(no results)`.
- `...::test_panel_up_down_enter_escape_consume_only_handled_keys`: `_StubKey` from `tests/test_lsp_chooser.py` pattern; press up/down/enter/escape and one unhandled `x`; assert callbacks receive the selected index once / close once, `stop_called` for handled keys only, and selection wraps.
- `...::test_panel_attaches_theme_and_scrollbar_helpers`: monkeypatch `theme.attach`, `theme.detach`, `scrollbars.apply_slim_scrollbars`, `scrollbars.apply_scrollbar_theme`; mount then unmount; assert each called exactly once in the expected order.

## Acceptance commands (from worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_quickfix_model.py tests/test_quickfix_panel.py -q
.venv\Scripts\python.exe -m pyright yate/session.py yate/editor_components/quickfix_panel.py tests/test_quickfix_model.py tests/test_quickfix_panel.py
```

## Risks / rollback

- Risk: `session.py` size creep; measure with `splitlines()` after edit; if >800, move the model to a dedicated L1 module and register its layer rank (not expected: baseline ~600).
- Risk: R15 guard false negative; ensure both scrollbar helper names appear in the same module that defines the `VerticalScroll` subclass.
- Rollback: revert this subplan's four files; no other module references them yet.
