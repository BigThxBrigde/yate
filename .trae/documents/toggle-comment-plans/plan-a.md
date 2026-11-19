# Wave a: key constants and reversible comment engine

Source: [`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.1/§2.3/§3.

## Input
- Shared constants `TOGGLE_COMMENT_KEY = "<ctrl-/>"` (raw `\x1f`) and
  `TOGGLE_KEYMAP_KEY = "ctrl+shift+/"` (event-key name, documented as such)
  in `yate/keymaps/keys.py`; add a help-friendly alias entry only if needed,
  no `parse_key` of the shift spelling (it collapses to `\x1f`).
- `yate/editor_core/commenting.py` (new L0 module, stdlib-only + `LangSpec`
  dataclass shape passed in as plain markers): expose
  `comment_range(lines: Sequence[str], first: int, last: int, *, line_comment:
  str | None, block_comment: tuple[str, str] | None) -> list[str]`. Detection
  rules from main plan §2.3. Blank rows untouched; mixed rows converge to
  commented then restore exactly; block-only languages wrap/unwrap per row;
  no markers -> return the original lines unchanged.

## Exclusive files
`yate/keymaps/keys.py`, `yate/editor_core/commenting.py`,
`tests/test_commenting.py`, `tests/test_key_notation.py`.

## Output
Constants importable from `yate.keymaps.keys`; pure helper with docstrings;
round-trip tests for python `#`, c `//`, html `<!-- -->`, css `/* */`, lua
`--`, blank lines, mixed lines, no markers.

## Acceptance
```
.venv\Scripts\python.exe -m pytest tests/test_commenting.py tests/test_key_notation.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/keymaps/keys.py yate/editor_core/commenting.py
```
