# P2: O(k) diff3 region classification (plan d)

> **实施状态**：✅ 已实施 —— 2026-11-20（`78168722`，O(k) 游标 + 等价用例）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/editor_core/diff.py:133-200` calls `_side_span` (`:261-297`) and four `any(...)` (`:161-169`) per region; both scan sequences sorted by base line from the beginning, giving O(k^2). difflib opcodes are ordered and non-overlapping by contract; `_merge_spans` (`:250-258`) also returns sorted, coalesced spans.

## Exclusive files

- `../../../yate/editor_core/diff.py`
- `../../../tests/test_editor_core_diff.py`

## Design

1. Keep `diff3_regions`, `_merge_spans`, `_side_span`, `MergeRegion` public shapes and region order unchanged.
2. Precompute, once per side, the non-equal spans `[(i1, i2, j1, j2), ...]` in base order (already produced at `:150-151`).
3. Replace each side's repeated scans with a monotonic cursor advanced across the ordered spans/opcodes as `classify` visits regions in increasing base order. For a region `[start, end)`:
   - touched test for non-empty span: `s < end and e > start`; for zero-length span (pure insertion): `s <= start < e or s == start` (preserve the current two-clause rule verbatim);
   - the corresponding side span must reproduce `_side_span`'s result: equal opcodes map by offset, non-equal opcodes contribute their whole `j1:j2` segment, and `pieces[0][0] .. pieces[-1][1]` bound the result.
4. A small explicit cursor helper (module-private function, no new class protocol) may own the monotone index; nested ≤ 3 levels, guard clauses early-return. If preserving `_side_span` byte-for-byte proves simpler, keep it as the reference used by tests but do not call it in `classify`.
5. No behavior change for overlapping/adjacent spans, insertions at start/middle/end, or identical edits.

## Tests (in `../../../tests/test_editor_core_diff.py`)

- `test_diff3_cursor_classification_matches_reference_for_generated_inputs`: deterministic generation (fixed seed) of 100 small base/local/remote line-sequence triples, including empty sequences, pure insertions at 0/middle/end, deletions, and overlapping edits; compare the new `diff3_regions` output field-by-field against a local reference function that copies the old `classify` + `_side_span` logic. Assert both the full region list and the absence of exceptions.
- `test_diff3_regions_keeps_zero_length_insertion_semantics`: keep the six existing tests at `:120-159` unchanged (local insertion at start, remote insertion in the middle, insertion at end of file, conflict, disjoint, identical).
- `test_diff3_regions_classify_is_linear_in_region_count`: build 400 disjoint one-line changes; count opcode/span visits with a monkeypatched spy if needed; assert the visit count is bounded by a small constant times the number of regions (no quadratic rescan). If a spy is impractical, assert output correctness plus a wall-clock-free structural check (cursor helper called once per region).

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_core_diff.py tests/test_diff_integration.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core/diff.py tests/test_editor_core_diff.py
```

## Risk / rollback

Risk: zero-length spans and insert-at-EOF boundaries. Rollback: restore `_side_span` calls inside `classify`; the generated-input equivalence test should then pass against the restored implementation as well.
