# D3: refresh `tests/README.md` coverage map (plan e)

> **实施状态**：❌ 未实施 —— 方案已落盘（2026-11-20）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../tests/README.md:13-18` claims "2026-10-29 measurement: 98 of the 134 `yate/` modules ... 150 `.py` files". Current measurement: 149 non-`__init__.py` modules and 169 `.py` files. The file itself states at `:13` that the map is a spot-check, not an exhaustive registry.

## Exclusive files

- `../../../tests/README.md`

## Design

1. Replace the stale numeric sentence with a dynamic statement: the spot-check map is intentionally not a complete registry; the authoritative file set is guarded by `test_source_files_within_size_threshold` in `../../../tests/test_architecture.py` and the module-level constants there.
2. If counts are retained, recompute them with `len(list(Path("yate").rglob("*.py")))` and the non-`__init__` filter and label them `2026-11-20 measurement`. Prefer the dynamic wording to avoid a third drift.
3. Keep the rest of the README (organization, indirect coverage table, conventions, `conftest.py` pointers) untouched.

## Verification

- Document-only change: no test run required by `../../rules/misc-rules.md` §三; re-read the edited paragraph and mechanically re-run the count expression used in the text.

## Risk / rollback

Risk: removing concrete numbers reduces guidance; mitigate by pointing readers at the executable guard. Rollback: restore the original paragraph.
