# B2: Unicode digit in screen-saver fraction (plan c)

> **实施状态**：❌ 未实施 —— 方案已落盘（2026-11-20）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/yaterc_options.py:171-202` `_parse_journey_fraction` uses `isdigit()` at `:190-191` (`'²'.isdigit()` is `True`) and bare `int()` at `:194-195`; the resulting `ValueError` bubbles through `../../../yate/yaterc.py:213-216` and aborts `_extract_options` at `:484-487`, skipping file_preview and large_file.

## Exclusive files

- `../../../yate/yaterc_options.py`
- `../../../tests/test_yaterc_options.py`

## Design

1. Replace both `isdigit()` calls with `isdecimal()` so non-decimal Unicode digits fail validation instead of reaching `int()`.
2. Wrap the `int(numerator) / bottom` conversion in a local `try/except ValueError` that appends the same friendly message used for other invalid values (`screen_saver {key} must be a float in (0, 1) or a fraction like "1/8", got {value!r}`) and returns `None`. This makes any future parse edge explicit and keeps `_extract_options` running.
3. Do not change the accepted decimal syntax, the `(0, 1)` range check, or the extraction order. Do not add broad `except Exception`.

## Tests (negative first in `../../../tests/test_yaterc_options.py`)

- `test_parse_journey_fraction_rejects_superscript_digit_with_friendly_error`: call `_parse_journey_fraction("²/8", "dist", config)`; assert return is `None`, `config.errors` has exactly one entry containing `must be a float in (0, 1)` and `"²/8"`, and no exception escapes.
- `test_extract_options_keeps_tail_extractors_after_unicode_fraction_error`: build a rc namespace with `screen_saver = {"dist": "²/8"}` plus valid `file_preview` and `large_file` settings; call `_extract_options`; assert the friendly error is recorded **and** both later config sections are populated (use the same assertions style as `test_extract_options_still_calls_dict_extractors_at_its_tail` at `:253`).
- Keep the existing fraction acceptance case at `:384` unchanged (`"1/8"` still parses to `0.125`).

Sequence: add the two new tests first, run the file, observe the two `ValueError` failures, then patch and re-run.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaterc_options.py -q
.venv\Scripts\python.exe -m pyright yate/yaterc_options.py tests/test_yaterc_options.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k option_definitions_have_single_source
```

## Risk / rollback

Risk: rejecting Unicode decimal digits that `int()` would accept in other scripts; `isdecimal()` matches `int()` for all decimal digits and is the intended narrowing. Rollback: restore `isdigit()` and remove the local `try/except`.
