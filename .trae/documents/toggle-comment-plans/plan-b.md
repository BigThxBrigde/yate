# Wave b: action, command, dispatch, keymaps and help overlay

Source: [`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.4/§3.

## Input
Wave a output plus these verified facts:
- vsc binding at `yate/keymaps/vsc.py:121`; vim binding at
  `yate/keymaps/vim.py:247` and special case at `:275-281`.
- action table `yate/actions.py` (populate, editing section);
  command table `yate/commands.py` (keymap/help section, `:vim`/`:vsc`).
- dispatch globals at `yate/editor_dispatch.py:128-160`; raw conversion at
  `:167-174`; `event_to_raw("ctrl+shift+/") is None` verified.
- `help overlay` `yate/editor_components/modals.py:91-93` and GLOBAL KEYS.

## Changes
1. `actions.py`: register `toggle_comment`, resolve `LangSpec` via
   `lang_for(ctx.doc.filetype)` (L3 -> L0 legal), row span via
   `selected_rows()` or current row, delegate to `comment_range`, apply one
   `TextBuffer.replace_range`, restore cursor clamped; no marker -> message.
2. `commands.py`: `toggle-comment` command forwarding to
   `editor.execute_action("toggle_comment")`.
3. `editor_dispatch.py`: before `event_to_raw`, intercept
   `event.key in {"ctrl+shift+/"}` (constant plus `ctrl+shift+slash` alias)
   and call `ed.execute_action("toggle_keymap")`, return True. Place after
   prompt ownership check.
4. `vsc.py` / `vim.py`: replace `\x1f` binding with
   `_k(TOGGLE_COMMENT_KEY, "toggle_comment", "Toggle comment", ...)`;
   add help-only row on `TOGGLE_KEYMAP_KEY` in both tables; delete vim's
   `\x1f` keymap-toggle special case.
5. `modals.py`: header + GLOBAL KEYS text says `ctrl+shift+/`.

## Exclusive files
`yate/actions.py`, `yate/commands.py`, `yate/editor_dispatch.py`,
`yate/keymaps/vsc.py`, `yate/keymaps/vim.py` (binding rows and special-case
removal only), `yate/editor_components/modals.py`,
`tests/test_toggle_comment.py`, `tests/test_editor_dispatch.py`.

## Acceptance
```
.venv\Scripts\python.exe -m pytest tests/test_toggle_comment.py tests/test_editor_dispatch.py tests/test_vsc_keymap.py tests/test_keymaps_conflicts.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/actions.py yate/commands.py yate/editor_dispatch.py yate/keymaps/ yate/editor_components/modals.py
```
