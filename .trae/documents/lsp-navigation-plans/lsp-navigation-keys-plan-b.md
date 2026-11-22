# Plan b — shared keys and action registrations (wave 1)

Parent: [../lsp-navigation-plan.md](../lsp-navigation-plan.md).

## Input / output

Input: issue brief AC1-AC3, AC8; keymap facts in parent plan §2.
Output: five new shared key constants, vim `gd`/`gr` chords and `K`, vsc alt
keys and `K`, action names registered. No flow implementations here (wave d).

## Exclusive files

- `yate/keymaps/keys.py`
- `yate/keymaps/vim.py`
- `yate/keymaps/vsc.py`
- `yate/actions.py`
- `tests/test_lsp_navigation_keys.py` (new)

## Concrete changes

### 1. `keymaps/keys.py`

Add next to `HOVER_DOC_KEY` (`:57-60`), each with a `#:` comment:

```python
GOTO_DEF_KEY: str = "gd"             # vim chord
FIND_REFS_KEY: str = "gr"            # vim chord
GOTO_DEF_VSC_KEY: str = "<alt-g>"    # vsc single key
FIND_REFS_VSC_KEY: str = "<alt-r>"   # vsc single key
HOVER_POPUP_KEY: str = "<shift-k>"   # both keymaps, normalizes to "K"
```

Check `conflicts.py` reserved keys before adding: `<alt-g>` / `<alt-r>` /
`<shift-k>` are free in the current tables; do not use `<f12>` (macro replay).

### 2. `keymaps/vim.py`

- Import the five constants in the existing import block from `yate.keymaps.keys`.
- In `build_bindings` add help entries that reference the constants (never
  literals): `KeyBinding(parse_key(GOTO_DEF_KEY), "goto_definition", ...)`,
  same for `FIND_REFS_KEY`, and
  `_k(HOVER_POPUP_KEY, "show_hover_docs", ...)` using the file's helper.
  Update `chord_hints()` for prefix `g` to mention `d definition / r references`.
- In `_handle_normal`, insert before the generic unknown-follower branch at
  `:896`:
  - `self.prefix == "g" and key == "d"` → clear prefix/count,
    `ctx.ui.execute_action("goto_definition")`, return `True`.
  - `self.prefix == "g" and key == "r"` → same with `find_references`.
  Do not consume other `g` followers; keep `gg`/`gj`/`gk`/`gc` behavior intact.
  `K` reaches the extension-binding fallback at `:1095-1097`, so the new help
  binding makes `<shift-k>` dispatch to `show_hover_docs`.

### 3. `keymaps/vsc.py`

Import the three single-key constants and add to `build_bindings` near the
existing hover entry (`:142`):

```python
_k(GOTO_DEF_VSC_KEY, "goto_definition", "Go to definition", "NAV"),
_k(FIND_REFS_VSC_KEY, "find_references", "Find references", "NAV"),
_k(HOVER_POPUP_KEY, "show_hover_docs", "Show hover documentation", VIEW),
```

Never spell `<alt-g>` / `<alt-r>` / `<shift-k>` literally in `build_bindings`.

### 4. `actions.py`

Register near `show_hover_docs` (`:267-268`), all as lambdas calling the
future flow object (wave d supplies the methods):

```python
reg("goto_definition", lambda ctx: editor.lsp_navigation.goto_definition(), ...)
reg("find_references", lambda ctx: editor.lsp_navigation.find_references(), ...)
reg("show_outline", lambda ctx: editor.lsp_navigation.show_outline(), ...)
reg("rename_symbol", lambda ctx: editor.lsp_navigation.rename_symbol(), ...)
reg("show_code_actions", lambda ctx: editor.lsp_navigation.show_code_actions(), ...)
reg("show_signature_help", lambda ctx: editor.lsp_navigation.show_signature_help(), ...)
```

Keep `show_hover_docs` unchanged (`K` reuses it). No `commands.py` changes.

## Tests (`tests/test_lsp_navigation_keys.py`)

- `test_lsp_navigation_keys_are_distinct_and_defined_once`: all five constants are distinct; `parse_key(HOVER_POPUP_KEY) == "K"`.
- `test_vsc_lsp_shortcuts_resolve_to_actions`: `VscKeymap().lookup(parse_key(GOTO_DEF_VSC_KEY)).action == "goto_definition"`, likewise refs and `HOVER_POPUP_KEY -> show_hover_docs`.
- `test_vim_k_resolves_to_hover_action`: `VimKeymap().lookup(parse_key(HOVER_POPUP_KEY)).action == "show_hover_docs"`.
- `test_vim_g_chords_call_navigation_actions`: with a minimal `ActionContext` whose `ui.execute_action` records names, feed `g` then `d`, assert `["goto_definition"]`; reset and feed `g` then `r`, assert `["find_references"]`; assert `prefix` is cleared after both. Reuse the context/UI stub pattern from existing vim keymap tests (find it in `tests/`; do not modify those files).
- `test_vim_gd_does_not_break_existing_g_chords`: `gg`, `gj`, `gc` still take their prior paths (assert via the same stub that no navigation action was recorded and prior state transitions still occur).
- `test_builtin_actions_include_lsp_navigation_names`: populate an `ActionRegistry` with `populate(reg, editor_stub)` and assert the six new names resolve; a stub editor exposing `lsp_navigation` suffices.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation_keys.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps yate/actions.py tests/test_lsp_navigation_keys.py
```

Exit 0 required. Note: `keymaps/vim.py` is size-exempt; plan e updates the
recorded line count after this plan (no count edit here).

## Risk / rollback

Risk: vim `K` might be intercepted before the extension fallback by
`_SHIFT_KEYS`; the test above must verify actual dispatch. If it is, add an
explicit `K` branch before `_SHIFT_KEYS` handling and record the deviation.
Risk: `alt-g`/`alt-r` could conflict with terminal sequences; run
`python -m tools.check_keys` equivalent test in the local test file via
`conflicts.find_key_conflicts`. Rollback: revert this plan's commits; wave d
cannot start until the action names are settled.
