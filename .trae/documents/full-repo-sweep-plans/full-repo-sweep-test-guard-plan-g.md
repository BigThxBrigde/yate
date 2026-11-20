# B3 + R2: in-process size guard and rule-text synchronization (plan g)

> **实施状态**：❌ 未实施 —— 方案已落盘（2026-11-20）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

- `../../../tests/test_macro_wiring.py:95-125` nests `subprocess.run([sys.executable, "-m", "pytest", ...])`, which fails only under parallel coverage (`1 failed / 3961 passed`).
- `../../rules/architecture-boundaries.md:331-337` says `keymaps/vim.py` 1595 (actual 1679), `:389-396` says `editor_components/view.py` 824 (actual 879), `:67` says 37 guards (actual 45; §六 at `:508` is already 45). The remaining five exempt files are also +1 from their last recorded numbers.
- `../../../tests/test_architecture.py:377-385` `SIZE_EXEMPT_FILES` has the correct 7 keys; `:919-941` inlines the size-check loop; `:1828-1844` checks only `editor.py` membership and the set size.

## Exclusive files

- `../../../tests/test_architecture.py`
- `../../../tests/test_macro_wiring.py`
- `../../rules/architecture-boundaries.md`

## Design

1. Extract the body of `test_source_files_within_size_threshold` into a module-level function `size_exemption_violations() -> list[str]` in `test_architecture.py`; the existing test calls it and asserts an empty list. No behavior change.
2. Add `SIZE_EXEMPT_LINE_COUNTS: dict[str, int]` to `test_architecture.py` with the **final measured** `splitlines()` counts for all seven keys, taken after waves 1 and 2 have landed (wave 3 is deliberately later). Add `test_size_exemption_line_counts_match_rule` that parses the new rule table (below) and asserts each key/count pair matches the constant **and** the actual file line count.
3. Add a 7-row table to `../../rules/architecture-boundaries.md` §三.7 (heading e.g. `Current measured line counts (2026-11-20)`) with columns `exempt file | lines`; update the stale in-prose numbers for `vim.py`, `view.py`, and the five +1 files, and update `:67` from 37 to 45 guards. Keep the historical chronology text but make its latest number agree with the table.
4. Rewrite `test_size_exemption_rule_and_guard_are_in_sync` in `test_macro_wiring.py`: keep the rule/constant string assertions, iterate all seven keys (assert each key present in both the constant block and the rule table), and replace the nested pytest with an in-process call to `size_exemption_violations()` loaded via `importlib.util.spec_from_file_location` (tests is not a package). Assert the returned list is empty. Remove now-unused `sys` / `subprocess` imports only if no other test in the file uses them (`:183-191` still uses `sys`/`subprocess` for the pyright check — keep them).

## Tests

- `test_size_exemption_line_counts_match_rule` (new, in `test_architecture.py`): for each of 7 keys, parse the backticked path and integer from the rule table; assert `parsed == SIZE_EXEMPT_LINE_COUNTS[key] == len(file.read_text(encoding="utf-8").splitlines())`; assert the parsed key set equals `set(SIZE_EXEMPT_FILES)`.
- `test_size_exemption_rule_and_guard_are_in_sync` (rewritten): assert each of the 7 keys appears in the rule table and the guard set; assert `size_exemption_violations() == []`; no subprocess pytest.
- Keep `test_editor_size_exemption_is_registered` (`:1828-1844`) unchanged.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_wiring.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n 1
```

Pass criteria: both coverage runs exit 0 with no failed test; architecture test count becomes 46; rule table numbers match `splitlines()` output.

## Risk / rollback

Risk: line-count table goes stale on later edits; that is the intended early-warning signal, and wave 5 / review iterations must re-measure. Rollback: restore the subprocess test and the old rule numbers only if the in-process guard cannot be loaded reliably; record the evidence.
