# Plan b — Global actions, commands and synchronized key bindings

Parent: [`../quickfix-nav-plan.md`](../quickfix-nav-plan.md). Rules: [`../../rules/architecture-boundaries.md`](../../rules/architecture-boundaries.md), [`../../rules/python-coding-style.md`](../../rules/python-coding-style.md).

## Input / output

Input: unused keys `<alt-j>` / `<alt-k>` / `<alt-q>` (probe in parent plan §3), existing shared-key pattern. Output: three actions and matching commands/keyboard rows, plus architecture guard; flows need not exist yet because action lambdas resolve lazily.

## Exclusive files

- `yate/actions.py`
- `yate/commands.py`
- `yate/keymaps/keys.py`
- `yate/keymaps/vsc.py`
- `yate/keymaps/vim.py`
- `tests/test_architecture.py`
- `tests/test_quickfix_keys.py` (new)

## Concrete changes

1. `yate/keymaps/keys.py` after `MARKS_OVERLAY_KEY` (line 218): `QUICKFIX_NEXT_KEY`, `QUICKFIX_PREV_KEY`, `QUICKFIX_PANEL_KEY` as `parse_key("<alt-j>")`, `parse_key("<alt-k>")`, `parse_key("<alt-q>")` with `#:` doc comments.
2. `yate/keymaps/vsc.py`: import the three constants; add three `_raw(...)` rows near the jump-list rows (lines 153-155) binding to `quickfix_next`, `quickfix_prev`, `quickfix_open`; category `NAV`.
3. `yate/keymaps/vim.py`: import the three constants; include them in `_NAVIGATION_KEYS` (lines 100-102) so the raw alt keys are consumed before INSERT/NORMAL/VISUAL dispatch and clear pending chords; add three `KeyBinding(..., "quickfix_*", ...)` rows near lines 277-279; category `NAV`.
4. `yate/actions.py` near `jump_back` (lines 323-328): register `quickfix_next`, `quickfix_prev`, `quickfix_open` with lambdas that call `editor.quickfix_flows.next()/prev()/open()` lazily.
5. `yate/commands.py` near `:diagnostics` (lines 570-581): register `:quickfix`, `:cnext`, `:cprev` calling the same three flow methods; descriptions in the existing lowercase style.
6. `tests/test_architecture.py`: add `test_quickfix_keys_are_shared_and_identical` after `test_lsp_navigation_keys_are_shared_and_identical`; AST-assert both `build_bindings` methods reference all three constants and contain no `"<alt-j>"` / `"<alt-k>"` / `"<alt-q>"` literals; runtime assert each raw key maps to the same action in both keymaps. Update the §六 header count from 47 to 48 in `../rules/architecture-boundaries.md` **only if that rule file is in scope for this wave**; if not, wave c owns the count update. (Decision: wave c owns rule-doc line-count/count updates because `editor.py` changes there.)
7. `tests/test_quickfix_keys.py`: use `_dispatch_stub` pattern from `tests/test_toggle_comment.py:27-70` and real `ActionRegistry`/`CommandRegistry` to assert registration + prompt/modal guard.

## Tests

- `test_quickfix_actions_and_commands_are_registered`: build real registries with a stub editor recording calls; assert the three action names and three command names exist and each invocation calls the expected stub method.
- `test_quickfix_keys_dispatch_once_in_both_keymaps`: for vsc and vim, send each raw key through `_handle_key` with `prompt_bar.active_mode = ""` and `has_modal_screen = False`; assert exactly one `action:quickfix_*` call and no `raw:` call; vim case starts in INSERT mode to prove the pre-dispatch branch.
- `test_quickfix_keys_are_ignored_while_prompt_or_modal_active`: repeat with `active_mode = ":"` and then `has_modal_screen = True`; assert zero action and zero raw calls.
- `test_quickfix_keys_have_no_conflicts`: build both keymaps and `find_key_conflicts(...)` with their reserved keys; assert empty result.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_quickfix_keys.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/actions.py yate/commands.py yate/keymaps/keys.py yate/keymaps/vsc.py yate/keymaps/vim.py tests/test_quickfix_keys.py tests/test_architecture.py
```

## Risks / rollback

- Risk: `<alt-j>` / `<alt-k>` collide with extension bindings at runtime; `:check-keys` test covers built-ins, extension collisions are user-configurable and out of scope.
- Risk: vim INSERT mode consumes alt+letter as meta-prefixed character; covered by the pre-dispatch set test.
- Rollback: revert the seven files; no production behavior depends on them until wave c.
