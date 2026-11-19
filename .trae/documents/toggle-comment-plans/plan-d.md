# Wave d: architecture guard and documentation

Source: [`../toggle-comment-plan.md`](../toggle-comment-plan.md) §3.

## Changes
1. `tests/test_architecture.py`: add guard #45
   `test_toggle_comment_keys_are_shared_and_identical` mirroring the
   hover/soft-wrap guards: AST asserts both `keymaps/vsc.py` and
   `keymaps/vim.py` reference `TOGGLE_COMMENT_KEY` inside `build_bindings`
   and never spell `"\x1f"` / `"<ctrl-/>"` literally; `keys.py` declares
   both constants; runtime asserts both keymaps resolve the raw key to
   `toggle_comment`. Negative drill: temporarily change one side, confirm
   failure, restore.
2. `.trae/rules/architecture-boundaries.md`: guard count 44 -> 45, add table
   row and wording; relative-path links only.
3. Bilingual manual (`yate/resources/manual.en.md` / `.zh.md`): key tables,
   keymap switching section, vim operator table, terminal-compat note
   (`Ctrl+Shift+/` unavailable on legacy terminals; use `:set keymap=`),
   prominent breaking-change note for `Ctrl+/`.
4. `yate/docs/which-key.en.md` / `.zh.md`: `g` prefix hint gains `gc`.
5. `CHANGELOG.md` / `CHANGELOG.zh.md`: Unreleased feature entry + breaking
   change note; generate with `python -m tools.changelog` if the checker
   requires it.

## Exclusive files
`tests/test_architecture.py`, `.trae/rules/architecture-boundaries.md`,
`yate/resources/manual.en.md`, `yate/resources/manual.zh.md`,
`yate/docs/which-key.en.md`, `yate/docs/which-key.zh.md`,
`CHANGELOG.md`, `CHANGELOG.zh.md`.

## Acceptance
```
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -n 1
.venv\Scripts\python.exe -m tools.changelog check
```
