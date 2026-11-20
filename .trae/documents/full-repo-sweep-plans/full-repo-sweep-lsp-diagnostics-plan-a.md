# P1: diagnose `diagnostic_at` via the per-row index (plan a)

> **实施状态**：❌ 未实施 —— 方案已落盘（2026-11-20）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/editor_lsp/manager.py:763-773` rebuilds `_diagnostics_by_row[uri][row]` on every publish; `:780-784` `diagnostics_for` copies the whole table and `:793-808` `diagnostic_at` scans it. The hot path is `../../../yate/editor.py:447-453,499-503` -> `../../../yate/flows/lsp_sync.py:95-101`.

## Exclusive files

- `../../../yate/editor_lsp/manager.py`
- `../../../tests/test_lsp.py`

## Design

1. Keep `_diagnostics` as the only source of truth and keep `_index_diagnostics` / `_forget_diagnostics` untouched.
2. Rewrite `diagnostic_at` to:
   - return `None` when `doc.path is None` (matches `diagnostics_for`);
   - resolve `uri = self._uri(doc)` and use `self._diagnostics_by_row.get(uri, {}).get(row, ())` as the candidate set;
   - evaluate the **existing** coverage predicates verbatim: single-line `d.start_col <= col < max(d.end_col, d.start_col + 1)`; first row `col >= d.start_col`; last row `col <= d.end_col`; inner row always covered;
   - keep `best is None or d.severity < best.severity` so the smallest (most severe) severity wins and ties keep the first indexed diagnostic (publish order, identical to the old list order).
3. Do not change `diagnostics_for`, `diagnostics_on_line`, `counts_for`, or any public signature. Do not add caches: the index is already rebuilt at each publish.

## Tests (in `../../../tests/test_lsp.py`, next to `test_diagnostics_delivery_and_queries` at `:916`)

- `test_diagnostic_at_matches_linear_reference_for_multirow_matrix`: publish a matrix of single-line, multi-line (3 rows), zero-width (`end_col == start_col`), and `doc.path is None` diagnostics; for a grid of `(row, col)` points compare `manager.diagnostic_at(doc, row, col)` against a local reference function implementing the exact old loop over `diagnostics_for(doc)`. Assert `severity`, `start_row` and `start_col` of the returned objects are equal (and both `None` where applicable).
- `test_diagnostic_at_prefers_most_severe_on_same_row`: three diagnostics on one row with severities 3, 1, 2; assert the returned one has severity 1; add a second same-severity pair and assert the earlier-published one wins.
- `test_diagnostic_at_large_d_uses_row_index`: publish 2000 diagnostics on row 0 plus one on row 40 and one spanning rows 38-42; assert `diagnostic_at(doc, 40, 0)` returns the spanning diagnostic; monkeypatch `manager.diagnostics_for` to raise `AssertionError("full table copy used")` for the duration of the call and assert no exception (proves the hot path no longer copies the table).
- Keep `test_diagnostics_row_index_multi_row_and_rebuild` (`:949`) and `test_diagnostics_index_cleared_with_table` (`:1018`) unchanged; they verify rebuild/invalidation.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q
.venv\Scripts\python.exe -m pyright yate/editor_lsp/manager.py tests/test_lsp.py
```

Pass: exit code 0, old/new equivalence over the whole matrix, no full-table copy in `diagnostic_at`.

## Risk / rollback

Risk: multi-line boundary semantics or tie-breaking drift. Rollback: restore the original `diagnostic_at` body; the per-row index and tests can remain.
