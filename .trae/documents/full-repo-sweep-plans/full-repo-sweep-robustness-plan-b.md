# B1: self-nesting guard for `move_entry` (plan b)

> **实施状态**：✅ 已实施 —— 2026-11-20（`ac4eda02`，负向用例先红后绿）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/services/workspace.py:519-545` `copy_entry` rejects a directory copied into its own subtree; `:547-559` `move_entry` only checks `target.exists()`. Cut/paste reaches it at `../../../yate/editor_components/file_manager/screen.py:1007`.

## Exclusive files

- `../../../yate/services/workspace.py`
- `../../../tests/test_workspace_file_manager.py`

## Design

1. In `move_entry`, after computing `target = dest_dir / src.name`, reuse the `copy_entry` ancestor test: when `src.is_dir()` and `target.resolve().relative_to(src.resolve())` does not raise `ValueError`, raise `OSError(f"cannot move {src.name} into itself")`. Put the guard **before** the `target.exists()` check so a recursive destination is rejected even when the target path does not yet exist.
2. Keep the existing `FileExistsError` semantics and `shutil.move` cross-volume behavior unchanged.
3. Update `move_entry`'s docstring to state the new `OSError` case (English, per `../../rules/misc-rules.md` §四).

## Tests (negative first in `../../../tests/test_workspace_file_manager.py`)

- `test_move_entry_rejects_moving_dir_into_own_subtree`: create `src/child`; call `workspace.move_entry(src, src / "child")`; assert `pytest.raises(OSError, match="cannot move src into itself")`; assert `src` and `src/child` still exist (no partial mutation).
- `test_move_entry_rejects_self_nesting_across_mocked_volume`: same tree, `monkeypatch.setattr(shutil, "move", fake_move)` where `fake_move` raises `AssertionError` if called; assert `OSError` is raised and `fake_move` is never called (covers the cross-volume recursion branch without real volumes).
- `test_move_entry_same_dir_target_still_raises_file_exists_error`: keep the existing behavior at `:113` (existing target name raises `FileExistsError`); assert a regular unrelated move still returns the expected target path.

Sequence: add the two negative tests first, run the file and observe exactly those two failures, then implement the guard and re-run (red -> green evidence must be recorded in the wave commit message body).

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_workspace_file_manager.py -q
.venv\Scripts\python.exe -m pyright yate/services/workspace.py tests/test_workspace_file_manager.py
```

## Risk / rollback

Risk: `resolve()` on a symlinked destination could change the user-visible error; the guard mirrors `copy_entry`, so behavior stays consistent. Rollback: remove the ancestor check from `move_entry`.
