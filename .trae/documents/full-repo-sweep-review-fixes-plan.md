# Full-repo sweep fixes: review/gate-fix plan

> **实施状态**：✅ 已实施 —— 2026-11-20（main-agent gate caught one regression; fixed and re-verified）

Parent: [full-repo-sweep-plan.md](full-repo-sweep-plan.md).

## Trigger

The main agent's final `pytest tests/ -q -n auto` gate failed at
`tests/test_cli.py::test_diag_prints_report_without_running_tui` after the R3
diagnostics snapshot change: `_FakeEditor` did not expose the six fields the
new L4 snapshot builder reads, so `cli.py` raised `AttributeError: '_FakeEditor'
object has no attribute 'config'`. This is a real regression in the test double, not a timing flake.

## Finding

- `[major]` `tests/test_cli.py:55-71,381-399` — the CLI `--diag` contract changed
  from "pass Editor to `format_report`" to "build `DiagnosticsInput` from Editor",
  but the fake editor and the call assertion still pinned the old contract.
  Evidence: `PYTEST_AUTO=1`, `FAILED tests/test_cli.py::test_diag_prints_report_without_running_tui`,
  `AttributeError: '_FakeEditor' object has no attribute 'config'` at `yate/cli.py:521`.

## Second finding (self-review)

- `[minor]` `yate/diagnostics.py:55`, `yate/cli.py:521`, `tests/test_diagnostics.py:52-59` —
  `DiagnosticsInput` was frozen but held a plain `dict` for `lsp_states`, so a
  consumer could mutate the "snapshot". Changed the field to `Mapping[str, ServerState]`
  and wrap the state mapping in `MappingProxyType` at both construction sites; the
  read-only test now asserts mutation raises `TypeError`.

## Fix (single wave)

Exclusive files: `tests/test_cli.py`, `yate/diagnostics.py`, `yate/cli.py`,
`tests/test_diagnostics.py`.

1. Extend `_FakeEditor` with `config`, `ext_dirs`, `ext_files`, `extension_loader.loaded`,
   `lsp.configs()` and `lsp.states()` (small private fakes, no new Protocol).
2. Assert that `format_report` receives a `DiagnosticsInput` whose fields are the
   frozen editor values, while keeping the existing checks that extension loading
   and LSP registration ran.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -q
.venv\Scripts\python.exe -m pyright tests/test_cli.py
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
```

Both targeted commands exited 0; the full gate result is recorded in the parent
plan's execution log.
