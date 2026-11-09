# Plan c — one shared hover key in both keymaps (wave-1, L1)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), decision D1

## Input

- `yate/keymaps/keys.py:18-55` (notation / `SPECIAL_KEYS`), `:93-152`
  (`parse_key` folds shift into ctrl codes).
- `yate/keymaps/base.py:21-26` (re-export of notation names), `:120-153`
  (binding index keyed by raw key).
- `yate/keymaps/vsc.py:36-122`, `yate/keymaps/vim.py:145-233`,
  `yate/keymaps/vim.py:80`, `:238-266` (`_FUNCTION_KEYS` fast path).
- `yate/keyproto/key_codec.py:20` (`_NAMED_KEYS` built from `SPECIAL_KEYS`).
- `yate/services/extensions/api.py:295-305` (`keymap="both"` → both targets).
- `tests/test_keymaps_conflicts.py`, `tests/conftest.py:366-377`
  (`make_action_context`).

## Decision under implementation (must be honored)

`<ctrl-k>` from the issue is rejected: `parse_key("<ctrl-k>") ==
parse_key("<ctrl-shift-k>") == "\x0b"`; vsc binds `\x0b` to `delete_line`
(`vsc.py:47`) and `tools/smoke_test/scenarios/edit.py:48-52` asserts it.
AC2 forbids that conflict. The single default is **`<f7>`** (`\x1b[18~`), free
in both tables, present in `SPECIAL_KEYS` and `key_codec._NAMED_KEYS`, and
dispatched by vim's `_FUNCTION_KEYS` branch before any mode handling — so all
vim modes and vsc use exactly the same key. Both tables and every document
must reference the same value.

## Exclusive files

- `yate/keymaps/keys.py`
- `yate/keymaps/base.py`
- `yate/keymaps/vsc.py`
- `yate/keymaps/vim.py`
- `tests/test_hover_key_binding.py` (new)

`yate/actions.py` is **not** in this plan (owned by wave-4 h, which registers
the `show_hover_docs` action). Until then the binding resolves to an
unregistered action, which is harmless: `Keymap.dispatch` reports a dead
action and `Editor.execute_action` returns `False`; no test asserts that every
table action is pre-registered (verified by the acceptance commands below).

## Concrete changes

1. `yate/keymaps/keys.py:55` — add, right after `SPECIAL_KEYS`:

   ```python
   #: Shared default for the "show API documentation" action. Both built-in
   #: keymaps import this single L0 constant (AC2); <ctrl-k> is NOT usable
   #: because it aliases <ctrl-shift-k> (delete_line) at raw byte \x0b.
   HOVER_DOC_KEY: str = "<f7>"
   ```

2. `yate/keymaps/base.py:21-26` — add `HOVER_DOC_KEY as HOVER_DOC_KEY` to the
   `from yate.keymaps.keys import (...)` re-export block (same `X as X` style
   as `KEY_ALIASES`). If the module defines `__all__`, add the name there.
3. `yate/keymaps/vsc.py:102-121` (VIEW section) — add
   `_k(HOVER_DOC_KEY, "show_hover_docs", "Show API documentation at cursor", VIEW)`;
   import `HOVER_DOC_KEY` from `yate.keymaps.base` (keep alphabetical import
   order).
4. `yate/keymaps/vim.py:212-233` (HLP section) — add
   `KeyBinding(parse_key(HOVER_DOC_KEY), "show_hover_docs",
   "Show API documentation at cursor", HLP)`; import the constant from
   `yate.keymaps.base` in the existing grouped import (`:33-39`).
5. Do not touch `RESERVED_KEYS`, `_MOTION_CODES`, `_FUNCTION_KEYS` or
   `toggle_keymap`. No new `Protocol`, no relative import, ASCII comments only.

## Tests (`tests/test_hover_key_binding.py`)

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_hover_key_constant_is_f7_and_maps_to_f7_raw` | `parse_key(HOVER_DOC_KEY)` | `HOVER_DOC_KEY == "<f7>"` and raw `== "\x1b[18~"` (`SPECIAL_KEYS["f7"]`) |
| `test_vsc_and_vim_bind_the_same_raw_key_to_hover_action` | `VscKeymap().lookup(raw)`, `VimKeymap().lookup(raw)` | both `is not None`, both `.action == "show_hover_docs"`, and both raw keys identical |
| `test_hover_key_is_not_a_conflict_in_either_keymap` | `find_key_conflicts(VscKeymap())`, `find_key_conflicts(VimKeymap(), reserved=RESERVED_KEYS)` | no conflict whose `.raw == raw`; `VscKeymap().lookup("\x0b").action == "delete_line"` still holds |
| `test_hover_key_is_not_a_vim_motion_or_reserved_key` | inspect `RESERVED_KEYS`, `_MOTION_CODES` | `raw not in` either; `HOVER_DOC_KEY not in ("<f1>","<f2>","<f8>","<f9>","<ctrl-shift-k>")` |
| `test_both_tables_reference_the_shared_constant` | `ast.parse` of `vsc.py` and `vim.py` source | each has exactly one `Name(id="HOVER_DOC_KEY")` inside `build_bindings`; no literal `"<f7>"` in either table (drift guard) |
| `test_vim_dispatches_hover_key_in_normal_insert_and_visual_modes` | for each `VimMode`, build `make_action_context`, monkeypatch `ctx.ui.execute_action` with a recorder, call `VimKeymap().handle_key(ctx, raw)` | `handle_key` returns `True` and recorder receives `["show_hover_docs"]` in **all three** modes |
| `test_toggle_keymap_preserves_hover_binding` | `KeymapSet()` with vsc+vim, `lookup(raw)` before/after `toggle()` (twice) | both actives expose `show_hover_docs` for the same raw |
| `test_key_name_round_trip_displays_the_hover_key` | `key_name(raw)` | contains `"f7"` (help/which-key display) |

Plan h additionally covers `bind_key(..., keymap="both")` on this action and
adds an AST guard in `tests/test_architecture.py`.

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m pytest tests/test_hover_key_binding.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_keymaps_conflicts.py tests/test_key_notation.py tests/test_keyproto.py tests/test_action_table.py tests/test_keymap_set.py -q -n 1
```

Both exit codes 0. The second command is the regression guard proving no
existing binding/action-table behavior changed while the new action is not yet
registered.

## Risks and rollback

- Risk: a runtime check discovers a table action must be registered. In that
  case **stop and report**; the main agent will decide whether to move the
  action registration earlier (it requires the `Editor.hover_flows` attribute,
  which is a wave-4 deliverable).
- Risk: a terminal does not deliver `<f7>`. `key_codec._NAMED_KEYS` maps it;
  plan i presses `f7` in smoke. If a real conflict is proven, change only
  `HOVER_DOC_KEY` and re-run plan f's docs-consistency test.
- Rollback: revert this commit; no other wave-1 plan depends on the tables.
