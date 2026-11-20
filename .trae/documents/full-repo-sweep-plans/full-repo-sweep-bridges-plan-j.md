# R1: split the extension bridges module (plan j)

> **实施状态**：❌ 未实施 —— 方案已落盘（2026-11-20）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/services/extensions/bridges.py` is 679 lines and self-documents eleven domains; `api.py:33-47` imports 13 names, facade `__init__.py:67-79,81-96` re-exports the frozen 14 names. Direct internal imports exist in `../../../tests/test_extension_bridges.py:32`, `test_extension_api.py:29`, `test_ui_contributions.py:25`, `test_ts_backend.py:30,429`. No real import cycle exists today.

## Exclusive files

- new package `../../../yate/services/extensions/bridges/` with `__init__.py` plus 3-4 internal modules
- deletion of `../../../yate/services/extensions/bridges.py`
- new test `../../../tests/test_extension_bridges_package.py` (no existing test file is edited)

Do not modify `api.py`, the facade `__init__.py`, or existing tests: the package `__init__` must preserve every old module-level name and import path. If an existing test must change, stop and report instead.

## Design

1. Build the dependency groups from actual imports before splitting. Intended grouping: `ui.py` (StatusSegment, CanvasHandle, CanvasControls, CanvasOpener, UiExtensionBridge), `syntax_lsp.py` (Lsp/Syntax/Highlight/Sprite/Theme bridges), `data_event.py` (Event/Data/Clipboard/Docs/Action bridges). If a class in one group references another group, keep both in the same module and record the reason in the docstring; correctness beats the target group count.
2. `bridges/__init__.py` re-exports **all** old public names: 13 classes listed above plus the aliases `SegmentAlign`, `CanvasControls`, `CanvasOpener`; keep the module-level logger name `tracing.get_logger(__name__)` frozen to the old facade-level name if any caplog test depends on it (verify with `../../../tests/test_extension_bridges.py`; if needed use the registered subpackage-logger exception documented in `../../rules/architecture-boundaries.md` R12 and guard it with a structural test).
3. Keep every class body byte-identical apart from import lines: no behavior change, no rename, no new protocol. All package-internal imports remain absolute (`from yate.services.extensions.bridges.<module> import ...`), per R6/absolute-import rule.
4. R14 is satisfied: all machinery stays under `services/extensions/`; the frozen 14-name facade and plugin import paths are untouched. No new `editor_components` import.

## Tests

- Existing direct-import tests must pass unchanged: `test_extension_bridges.py`, `test_extension_api.py`, `test_ui_contributions.py`, `test_ts_backend.py`.
- `test_bridges_package_reexports_every_legacy_name` (new, in `../../../tests/test_extension_bridges.py` only if the file may be edited — otherwise add to a new `tests/test_extension_bridges_package.py`): import the package and assert each of the 13 class names plus `SegmentAlign`, `CanvasControls`, `CanvasOpener` is the same object as the corresponding attribute imported through `yate.services.extensions.api` / the facade where exported; assert the facade `tuple(__all__)` is unchanged.
- Import-cycle smoke: `python -c "from yate.services.extensions.bridges import UiExtensionBridge; from yate.services.extensions import UiExtensionBridge as B; assert UiExtensionBridge is B"`.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_extension_bridges.py tests/test_extension_api.py tests/test_ui_contributions.py tests/test_ts_backend.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/services/extensions/ tests/test_extension_bridges.py
```

Each new internal module must stay under 800 lines (verify with `splitlines()`); no new exemption.

## Risk / rollback

Risk: circular imports or caplog logger-name drift. Rollback: restore the single `bridges.py` file and delete the package directory; all other files remain unchanged.
