# Wave c: vim `gc{motion}` / `gcc` / visual `gc`

Source: [`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.2/§3.

## Input
Wave b output; `yate/keymaps/vim.py` state machine details:
- `g` prefix arm at `_handle_normal` (`:873-878`), follower branches for
  `gg` (`:831-833`), `gj`/`gk` (`:834-844`), visual counterparts
  (`:575-589`), hints (`:403-404`), operator-pending (`:1071-1097`).
- `ctx.ui.execute_action("toggle_comment")` is the single action entry.

## Changes
- NORMAL: arm `g` -> `c` follower resolves a comment operation:
  - `gcc` (with optional count) applies to the current line;
  - `gc{motion}` uses the existing motion resolution to derive a row span
    (at minimum `j`, `k`, `w`, counts) and applies the same action;
  - any other `g` follower behaves exactly as before.
- VISUAL / VISUAL-LINE: `gc` applies to selected rows and returns to NORMAL.
- which-key `g` prefix hint gains the `c` row; no changes to other hints.
- Register/prefix/count state is cleared on resolution so nothing leaks.

## Exclusive files
`yate/keymaps/vim.py` (state machine only), `tests/test_vim_keymap.py`,
`tests/test_toggle_comment.py` (vim parts), `tests/test_whichkey_flows.py`.

## Acceptance
```
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_toggle_comment.py tests/test_whichkey_flows.py tests/test_soft_wrap_keys.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py
```
