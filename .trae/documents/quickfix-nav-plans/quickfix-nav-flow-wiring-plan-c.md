# Plan c — QuickFixFlows, dock wiring and architecture registration

Parent: [`../quickfix-nav-plan.md`](../quickfix-nav-plan.md). Rules: [`../../rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md), [`../../rules/doc-conventions.md`](../../rules/doc-conventions.md).

## Input / output

Input: waves a and b landed. Output: panel visible in the bottom dock, actions operable, no provider data yet.

## Exclusive files

- `yate/flows/quickfix_flows.py` (new)
- `yate/editor.py`
- `yate/editor_compose.py`
- `yate/resources/app.tcss`
- `tests/test_quickfix_flow.py` (new)
- `tests/test_architecture.py` (only `UI_FROZEN_FILES` + measured line counts)
- `.trae/rules/architecture-boundaries.md` (L3 flow registry, R11 registration, §六 48-case count/table)

## Concrete changes

1. `yate/flows/quickfix_flows.py` (new, L3): imports `Callable` aliases from `yate.flows` where appropriate, `QuickFixEntry`/`QuickFixList` from `yate.session`, and `QuickFixPanel` from `yate.editor_components.quickfix_panel` (R11 registration required **before** this import). Constructor: `QuickFixFlows(session: EditorSession, panel: QuickFixPanel, *, reveal: Callable[[Path,int,int],None], show: Callable[[],None], hide: Callable[[],None], message: MessageFn, refresh: Callable[[],None])`. Methods:
   - `set_results(provider, entries, label) -> None`: delegate to `list.replace`, repaint panel, `open()` when entries exist, explicit empty-state message on empty set without opening a stale view.
   - `open()`, `close()`, `toggle()`: show/hide panel via injected callbacks; `close()` keeps `list`; reopen restores `selected`.
   - `next()`, `prev()`: `step(±1)`, then `jump_to(list.selected)`; empty list emits `no quickfix entries` message.
   - `jump_to(index) -> None`: resolve entry, call `session.push_jump()` immediately before `reveal(entry.path, entry.row, entry.col)`, repaint, `refresh`, and message `jumped to <path>:<line>`; out-of-range indices are ignored with a message.
   - `active_entries` / `selected` read-only properties for tests and providers.
2. `yate/editor.py`: declare `quickfix_panel: QuickFixPanel` and `quickfix_flows: QuickFixFlows`; in `compose()` yield `self.quickfix_panel` inside `#bottom-dock` before `self.terminal_panel`; in `on_mount()` set `display = False`; add `show_quickfix()` / `hide_quickfix()` methods that only set `display` and refresh, no styling (R13).
3. `yate/editor_compose.py`: construct `QuickFixPanel` with lambdas resolving `ed.quickfix_flows` lazily for pick/close; construct `QuickFixFlows` after `ed.session` and the panel with `reveal=ed.reveal_match`, `show=ed.show_quickfix`, `hide=ed.hide_quickfix`, `message=ed.message`, `refresh=ed.refresh_ui`. Update the constructor-order comment. **Do not** add provider callbacks here — that is wave d.
4. `yate/resources/app.tcss`: add a frozen `#quickfix-panel` block under `#bottom-dock` (`height: 8; display: none; border-top: wide $border; padding: 0 1;`) following the file's existing syntax/theme variables; keep R9 id ownership in `Editor`.
5. `tests/test_architecture.py`: register `"flows/quickfix_flows.py": {"yate.editor_components", "yate.editor_components.quickfix_panel"}` in `UI_FROZEN_FILES` before any import; update `SIZE_EXEMPT_LINE_COUNTS` and `SIZE_EXEMPT_FILES` for any exempt file whose `splitlines()` count changed (`editor.py` expected to grow past 848; `view.py` untouched).
6. `.trae/rules/architecture-boundaries.md`: add the new flow to §一 L3 and R11 lists, record the registration, update §三.7 measured `editor.py` count and §六 count 47→48 + table row for the new guard. Keep Mermaid graph unchanged (no new layer edge: L3→L2 already drawn).

## Tests (`tests/test_quickfix_flow.py`)

- `test_set_results_replaces_provider_slice_and_opens_panel`: fake panel records paints and `show` calls; two sets from `diagnostics` and `references`; assert snapshot ordering, `show` once, selected `0`.
- `test_next_and_prev_wrap_and_jump_records_one_push`: three entries; drive `next()` three times and `prev()` twice with a real `EditorSession`; assert visited indices `[1,2,0,2,1]`, `reveal` calls match entry paths/rows/cols, and `session.jumps.stacks()[0]` grew by exactly three after the three pushes (continuous same-position dedupe disabled by distinct cursor positions).
- `test_close_keeps_entries_and_reopen_restores_selection`: close after selecting index 1; assert `snapshot()` unchanged and panel hidden; reopen; assert `selected == 1`.
- `test_empty_results_emit_message_and_do_not_show_stale_panel`: `set_results("diagnostics", [], "...")` with a prior non-empty set; assert panel hidden, snapshot cleared, message contains `no diagnostics`.
- `test_jump_to_out_of_range_is_ignored`: `jump_to(99)`; assert no reveal/push, explicit message.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_quickfix_flow.py tests/test_quickfix_keys.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/flows/quickfix_flows.py yate/editor.py yate/editor_compose.py tests/test_quickfix_flow.py
```

## Risks / rollback

- Risk: `editor.py` exceeds 800-line threshold (already exempt); synchronise both rule table and guard map with measured `splitlines()` value or the gate fails.
- Risk: flow imports L2 panel before R11 registration; add the guard key first.
- Risk: `reveal_match` synchronously opens a document and may throw on a deleted file; providers publish only scanned paths, and `jump_to` catches `OSError` with a message — no silent exception.
- Rollback: revert this wave; waves a/b remain individually testable.
