# Plan a — normalize `Hover.contents` (wave-1, L0)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)

## Input

- `yate/editor_lsp/parsing.py:1-50` (module style, `__all__`, `_to_utf16`),
  `:67-135` (`_unwrap_completion` / `_range_from` defensive-shape style),
  `:200-230` (`_parse_diagnostics` "never raise" policy).
- Issue brief §3.4 / AC4 / AC5: `MarkupContent` markdown + plaintext,
  `MarkedString`, string arrays, mixed arrays, `null`, `{}`, empty string,
  whitespace-only, empty array must all normalize to a **display string** or
  `""`.

## Exclusive files

- `yate/editor_lsp/parsing.py`
- `tests/test_lsp_hover_parsing.py` (new)

## Concrete changes

1. `yate/editor_lsp/parsing.py:32` — extend `__all__` with
   `parse_hover_contents`; keep the module's "pure, total, defensive" contract.
2. Add, after `_from_utf16` (`parsing.py:64`):

   ```python
   def parse_hover_contents(raw: object) -> str:
       """Normalize an LSP Hover payload into Markdown text ("" when empty)."""
   ```

   Data flow: unwrap `{"contents": ...}` (also accept a bare `contents`
   payload for server tolerance) → `_hover_part(value)` → join non-empty parts
   with `"\n\n"` → return `text` only when `text.strip()` is non-empty, else
   `""`.
3. `_hover_part(value: object) -> str` (module-private, prose docstring):
   - `str` → the string itself (no fenced wrapping).
   - `dict` → `cast(dict[str, object], value)`; if it has a string `value`
     field:
     - `language` is a non-empty string (LSP `MarkedString`) →
       ```` ```{language}\n{value}\n``` ```` so signatures render as a fenced
       code block (matches the reference screenshot);
     - else (`MarkupContent`, `kind` markdown/plaintext/unknown) → `value`.
     - missing/non-string `value` → `""`.
   - `list` → recursively normalize each element, drop empty parts, join with
     `"\n\n"`.
   - anything else (`None`, `int`, `bool`, unexpected objects) → `""`.
   - Guard against unbounded recursion: nested lists are allowed but each level
     only recurses into `list`; no dict self-reference is followed (a dict's
     `value` is used as a string only).
4. No logging of user-facing hints; a `log.debug` for a discarded malformed
   shape is optional and must use lazy `%` formatting. No `Any`, no
   `TYPE_CHECKING`; `cast` comes from the existing `typing` import.

## Tests (`tests/test_lsp_hover_parsing.py`)

All cases are arrange/act/assert on the pure function; no App, no LSP server.

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_parse_hover_contents_with_none_returns_empty_string` | `parse_hover_contents(None)` | `== ""` |
| `test_parse_hover_contents_with_empty_dict_returns_empty_string` | `parse_hover_contents({})` | `== ""` |
| `test_parse_hover_contents_with_missing_contents_returns_empty_string` | `{"range": {...}}` | `== ""` |
| `test_parse_hover_contents_with_markup_markdown_returns_value` | `{"contents": {"kind": "markdown", "value": "**f()** docs"}}` | `== "**f()** docs"` |
| `test_parse_hover_contents_with_markup_plaintext_returns_value` | `{"kind": "plaintext", "value": "plain docs"}` (bare payload) | `== "plain docs"` |
| `test_parse_hover_contents_with_whitespace_only_returns_empty_string` | `"  \n\t "` and `{"contents": {"kind":"markdown","value":" \n "}}` (parametrized) | `== ""` for both |
| `test_parse_hover_contents_with_bare_string_returns_text` | `{"contents": "hover text"}` | `== "hover text"` |
| `test_parse_hover_contents_with_marked_string_wraps_language_in_fence` | `{"language": "python", "value": "def f(x: int) -> str:"}` | starts with `` ```python `` and contains the signature |
| `test_parse_hover_contents_with_string_array_joins_nonempty_parts` | `["sig", "", "docs"]` | `== "sig\n\ndocs"` |
| `test_parse_hover_contents_with_mixed_array_preserves_order` | `[{"language":"python","value":"def f():"}, {"kind":"markdown","value":"docs"}, "tail"]` | fenced signature first, then `docs`, then `tail` |
| `test_parse_hover_contents_with_empty_array_returns_empty_string` | `[]`, `["", "  "]` (parametrized) | `== ""` |
| `test_parse_hover_contents_with_malformed_shapes_returns_empty_string` | `{"contents": 42}`, `{"value": 7}`, `{"contents": [None, True, {"value": None}]}`, `object()` | `== ""` for each |
| `test_parse_hover_contents_is_total_for_hostile_input` | loop over the malformed corpus | no exception raised (wrap each call in the loop; assert all results are `str`) |

Negative-path intent: every AC5 empty shape must collapse to `""` here, before
any UI code can see it.

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover_parsing.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp_parsing.py tests/test_lsp.py -q -n 1
```

Both exit codes must be 0. Main-agent wave-1 gate also runs full pyright and the
architecture suite.

## Risks and rollback

- Risk: servers put a fenced code block inside a `MarkedString` already. The
  wrapper is only applied when `language` is present; double fencing is
  cosmetic and covered by the mixed-array test.
- Risk: `cast(dict[str, object], ...)` widens pyright inference. Keep all
  reads behind `isinstance(..., str)` guards so strict mode stays clean.
- Rollback: revert this one commit; `parse_hover_contents` is only consumed by
  plan d, which has not been executed in wave 1.
