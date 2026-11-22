# R4: extract the workspace ignore subsystem (plan l)

> **实施状态**：✅ 已实施 —— 2026-11-20（`dd61c63f`，ignore 子系统 L0 迁移）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/services/workspace.py:19,35,39` constants, `:117` `_IgnorePattern`, `:139-146,183-195` state, `:179-197` `_load_root_ignores`, `:199-236` `_parse_ignore`, `:238-265` `_dir_ignores`, `:267-311` `_is_ignored`, `:643` `_anchored_match` form a self-contained subsystem. Consumers are `list_dir :315-342`, `walk_files :344+`, `../../../tests/test_workspace_filter.py`, and `../../../yate/editor_components/explorer.py:23` (imports `IGNORED_NAMES`). No closures; state lives on `self` plus module constants.

## Exclusive files

- `../../../yate/services/workspace.py`
- new `../../../yate/services/workspace_ignores.py`
- new test `../../../tests/test_workspace_ignores_module.py`

## Design

1. New L0 module `workspace_ignores.py` owns `IGNORED_NAMES`, `IGNORE_FILENAMES`, `_DIR_IGNORE_CACHE_MAX`, `_IgnorePattern`, `_parse_ignore`, `_anchored_match`, and an `IgnoreIndex` class holding `root_ignores`, `root_has_anchored`, and the mtime-keyed `dir_ignore_cache`. `IgnoreIndex` exposes `set_root(root)`, `ignored(path, is_dir, dir_ignores=None)` and `dir_ignores(directory)` with the same algorithms and cache-eviction threshold.
2. `Workspace` keeps thin delegating private methods with unchanged names/signatures (`_load_root_ignores`, `_parse_ignore`, `_dir_ignores`, `_is_ignored`) backed by `self._ignore_index`; `IGNORED_NAMES` remains re-exported from `workspace.py` so `explorer.py:23` and existing tests keep working. Re-export is documented in the new module's docstring (L0 leaf packages allow limited re-export with a note, per `../../rules/architecture-boundaries.md` §三.5).
3. No behavior change: last-match-wins, negation, anchored rules, comment/blank skipping, mtime cache identity and full-cache clearing at `_DIR_IGNORE_CACHE_MAX` must stay identical. No new `editor_components` import (R4 guard).
4. Both files must stay under 800 `splitlines()`; no exemption needed or added.

## Tests

- All existing `../../../tests/test_workspace_filter.py` cases must pass unchanged (`test_comments_and_blank_lines_skipped`, `test_negation`, `test_last_match_wins`, `test_anchored_rules_are_skipped_outside_the_root`, `test_set_root_reloads_ignores`, `test_load_root_ignores_without_a_root`).
- `test_ignore_subsystem_lives_in_dedicated_module` (new test file `../../../tests/test_workspace_ignores_module.py` — add to exclusive files at execution): assert `_IgnorePattern`, `_parse_ignore`, `_anchored_match` are defined (not merely imported) in `workspace_ignores.py`; assert `Workspace._is_ignored` source is a thin delegation (≤ 5 source lines); assert `from yate.services.workspace import IGNORED_NAMES` still resolves.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_workspace_filter.py tests/test_workspace_file_manager.py tests/test_workspace_ignores_module.py -q
.venv\Scripts\python.exe -m pyright yate/services/workspace.py yate/services/workspace_ignores.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## Risk / rollback

Risk: cache identity changes alter ignore results after file edits. Rollback: restore the inline methods and constants in `workspace.py` and delete the new module; no other file depends on the new module directly.
