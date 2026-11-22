# Plan e — guards, docs, smoke and real-server AC (wave 4)

Parent: [../lsp-navigation-plan.md](../lsp-navigation-plan.md).

## Input / output

Input: final code from waves a-d. Output: architecture guard + line-count sync,
bilingual docs/manual updates, smoke scenario, real pyright two-file AC.

## Exclusive files

- `tests/test_architecture.py`
- `.trae/rules/architecture-boundaries.md`
- `yate/docs/lsp.zh.md`
- `yate/docs/lsp.en.md`
- `yate/resources/manual.zh.md`
- `yate/resources/manual.en.md`
- `tools/smoke_test/scenarios/lsp_navigation.py` (new)
- `tools/smoke_test/scenarios/__init__.py`
- `tests/test_lsp_real_server.py`

## Concrete changes

### 1. Architecture guard and counts

- Add `test_lsp_navigation_keys_are_shared_and_identical` next to
  `test_hover_key_is_shared_and_identical` (`tests/test_architecture.py:1666`),
  copying its AST + runtime shape:
  - AST: both `vsc.py` and `vim.py` `build_bindings` reference every shared
    constant (`GOTO_DEF_KEY`, `FIND_REFS_KEY`, `GOTO_DEF_VSC_KEY`,
    `FIND_REFS_VSC_KEY`, `HOVER_POPUP_KEY`) and contain none of the literal
    specs `"gd"`, `"gr"`, `"<alt-g>"`, `"<alt-r>"`, `"<shift-k>"`.
  - Runtime: `VscKeymap().lookup(parse_key(GOTO_DEF_VSC_KEY)).action ==
    "goto_definition"`, likewise refs and hover; `VimKeymap().lookup(
    parse_key(HOVER_POPUP_KEY)).action == "show_hover_docs"`; vim help entries
    for `gd`/`gr` resolve to the matching action names.
- Measure actual `splitlines()` for `keymaps/vim.py`, `editor.py`,
  `editor_lsp/manager.py` with `.venv/Scripts/python.exe -c "..."`. Update
  `SIZE_EXEMPT_LINE_COUNTS` in `tests/test_architecture.py` and the table in
  `.trae/rules/architecture-boundaries.md` §三.7 to the exact same numbers;
  keep the guard count description at 47 and add the new case to §六's list.
- Verify `UI_FROZEN_FILES` needs no new entry: `lsp_navigation_flows.py` must
  import only `editor_components.lsp_chooser` / `hover_popup` / `panes`; if it
  imports others, register the exact modules first (R11) and record it.

### 2. Docs (bilingual, sync in one commit)

- `yate/docs/lsp.zh.md` capabilities list (`:10-27`) and `lsp.en.md` (`:20-32`):
  add entries for `gd` definition, `K` hover (keep `<f7>`), `:lsp outline`
  (or action palette: `show_outline`), `gr` references, rename, code actions,
  signature help; state that all are server-capability gated and requests are
  async with explicit messages.
- Add a short two-file pyright example to both docs showing `gd`, `gr`, `K`.
- `yate/resources/manual.zh.md` §16 (`:1279-1402`) and `manual.en.md` §16
  (`:1430`+): add the same capability summary and key-table rows for `K`, `gd`,
  `gr`, `<alt-g>`, `<alt-r>`; keep the bilingual key-table sections consistent.

### 3. Smoke scenario

Add `tools/smoke_test/scenarios/lsp_navigation.py` following
`scenarios/hover.py` (`:41-224`): fake LSP client injected via the app's
`set_client_factory`; two-file project; assert:
- `gd` on a call site jumps to the other file's definition line;
- `gr` opens a chooser whose SVG text contains both file names, enter navigates;
- `K` and `F7` both render the same hover text;
- no-server case emits a warning message and leaves the buffer unchanged.
Register in `scenarios/__init__.py` with tag `("lsp-navigation",)`.

### 4. Real pyright AC

Extend `tests/test_lsp_real_server.py` (keep its `skipif` gate) with a
two-file scenario: A defines `def greet(name: int) -> str`, B imports and calls
it. After startup and didOpen for both, assert:
- `request_definition(doc_b, call_row, call_col)` returns a `LspLocation` whose
  resolved path is A and row/col match the `def greet` line;
- `request_references` returns at least two locations covering both files;
- `request_hover` returns non-empty text.
Keep the existing wire-recorder approach for diagnostics; do not assert on
manager's raw diagnostic key.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_lsp_real_server.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4 --tag lsp-navigation
```

Exit 0 required for architecture and smoke; real-server test must be either
passed or explicitly skipped by its existing environment gate (report which).

## Risk / rollback

Risk: line-count table mismatch is a hard gate — measure after all other waves,
never guess. Risk: smoke key events may be swallowed by vim prefix handling;
use the scenario's keymap-switch hook to test both keymaps. Risk: real pyright
may be unavailable on the runner; keep skipif and report honestly. Rollback:
revert this plan's commits; product code from waves a-d stays intact.
