# R3: remove diagnostics' reverse dependency on Editor (plan k)

> **实施状态**：✅ 已实施 —— 2026-11-20（`dd61c63f` + `8a247d98`，headless import 无 editor）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../yate/diagnostics.py:25` imports `Editor` from `yate.editor`; six signatures (`:82,131,268,298,355,399`) and eight property reads (`:271,299,368,371,375,382,400,401`) depend on it. `../../../yate/cli.py:31-32,507-525` builds the app then calls `diagnostics.print_report(app.editor)`. The architecture diagram only draws `ED -> DIAG`. `tests/test_diagnostics.py` has 53+ call sites using `format_report(app.editor)` / `print_report(app.editor)`.

## Exclusive files

- `../../../yate/diagnostics.py`
- `../../../yate/cli.py`
- `../../../tests/test_diagnostics.py`

## Design

1. Define a frozen `DiagnosticsInput` dataclass in `diagnostics.py` with explicit fields gathered from the eight reads: `config: YateConfig`, `ext_dirs: tuple[Path, ...]`, `ext_files: tuple[Path, ...]`, `loaded_extensions: tuple[<registered record type>, ...]`, `lsp_configs: tuple[<LSP config type>, ...]`, `lsp_states: dict[str, <LSP state type>]`. Import those concrete leaf types (no `Protocol`, no `TYPE_CHECKING`, no `Any`); use local imports only if a top-level import would create a cycle, and document why in the docstring.
2. Change `format_report`, `print_report`, `_section_yaterc`, `_section_config`, `_section_extensions`, `_section_lsp` to accept `DiagnosticsInput`. Keep all report text, section order, colorization and error downgrade behavior byte-identical.
3. Build the snapshot at the L4 call site in `cli.py` after `load_extensions()` / `register_configured_servers()`: a small private helper `_diagnostics_input(editor)` constructs `DiagnosticsInput` from the live editor. `diagnostics.py` must have no `from yate.editor import Editor` after this wave.
4. Update all call sites in `tests/test_diagnostics.py` through one test-side helper `_snapshot(editor: Editor) -> diagnostics.DiagnosticsInput`; replace `format_report(app.editor)` with `format_report(_snapshot(app.editor))` and likewise for `print_report`. No assertion strings change.
5. Update the architecture dependency diagram in `../../rules/architecture-boundaries.md` **only if** plan g has already added a note; otherwise report the needed one-line diagram edit to the main agent instead of editing the rule file here (file ownership belongs to plan g).

## Tests

- Existing 50+ report tests must pass with unchanged expected text (header, twelve sections, color/plain output, probe-failure downgrade).
- `test_diagnostics_input_snapshot_is_read_only`: construct a `DiagnosticsInput`, attempt to mutate a tuple field (assert `AttributeError`/immutability) and confirm `format_report` output is identical before and after mutating the originating editor's unrelated state.
- `test_diagnostics_module_does_not_import_editor`: AST/text assertion in `../../../tests/test_architecture.py` is owned by plan g; if this wave lands before that guard, add the assertion inside `tests/test_diagnostics.py` as a module-level source scan so the new edge cannot regress here.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/diagnostics.py yate/cli.py tests/test_diagnostics.py
.venv\Scripts\python.exe -c "import sys, yate.diagnostics; assert 'yate.editor' not in sys.modules"
```

The last command must exit 0 (proves headless import no longer drags in the TUI stack).

## Risk / rollback

Risk: 50+ test call sites and subtle report-text drift. Rollback: restore `Editor` signatures and the old test call sites; the snapshot dataclass can be kept unused if needed.
