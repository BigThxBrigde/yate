# yate review specifics

Project-specific additions to the generic framework in `SKILL.md`. Read
this when reviewing inside the yate repository; the generic dimension list
still applies, but the authority for "is this correct" is the repository's
own rules, not general Python practice.

## Authoritative sources (read before reviewing)

1. `.trae/rules/architecture-boundaries.md` — layering, R1-R13, the §五
   self-check list, the §六 guard inventory.
2. `.trae/rules/python-coding-style.md` — PEP 8 + PEP 20, annotations,
   docstrings, logging, tests.
3. `.trae/rules/doc-conventions.md` — plan/review naming, relative paths,
   bilingual pairs.
4. `.trae/rules/subagent-workflow.md` — reporting discipline for delegated
   review.

Anything the framework's generic advice and these files disagree about is
decided by these files.

## Per-layer traps

### `tools/` — stdlib tooling layer (pack / changelog / translate / smoke_test)

- `print` on stderr/stdout is the established convention; the R12 tracing
  rule constrains `yate/` only. Neither report it as a violation nor
  "fix" it.
- Errors are data: every failure surfaces as `error[<CODE>]: <message>`
  (registry in `tools/pack/errors.py`). A traceback reaching the terminal
  is a finding; an unused code in that registry usually means a mapping is
  wrong, not that the code is redundant.
- Library code never calls `sys.exit`; only the CLI layer maps to codes.
- A per-item failure (one page, one commit) must degrade, not abort the run.
- Subprocess calls: UTF-8 forced on the pipe ends, timeout bounded, exit
  code classified (success / failure / cancellation / interrupt).
- Windows specifics: `.cmd` shims need `shutil.which` resolution; a console
  Ctrl+C reaches the whole process group and children report
  `STATUS_CONTROL_C_EXIT` (`0xC000013A`); a shell hook that ignores the
  console event must still be killable by the tool itself.
- Coverage: `pyproject.toml` sets `source = ["yate"]`, so `--cov=yate` says
  nothing about a `tools/` change — measure the module explicitly.
- Tests must not patch attributes on the real `subprocess` module; replace
  the module reference the code under test uses instead, or the fake
  reaches pytest, coverage and every other library in the run.

### `yate/` — the editor itself

- Dependency direction R1-R13; `editor_view/*` never imports upward, and
  new `editor_view` imports in L3 flow modules must be registered in
  `tests/test_architecture.py::UI_FROZEN_FILES`.
- No new `Protocol` (frozen whitelist only), no `TYPE_CHECKING`, no bare
  `Any` (a `# noqa: Any - <reason>` note is required where unavoidable),
  no `# type: ignore`.
- Logging goes through `log = tracing.get_logger(__name__)` with lazy `%`
  placeholders; no `self.log` / `self.app.log`.
- Theme and scrollbar ownership stays with the component (R13).
- Naming guard: no `*Feature` / `*Host` / `*Ops` / `*Delegate` /
  `*Controller`; flow modules are `*Flows`.

### `tests/`

- A guard must fail when its fix is reverted — prove it by mutating the
  source, not by reading the assertion. A test that passes against both the
  fixed and unfixed code is worse than no test: it reads as coverage.
  Three real examples from the 2026-10-06 review rounds: a manifest guard
  that stubbed the very helper whose argument it verified; a "late failure"
  guard that only exercised the queue API and passed with the buggy
  container; a progress-text guard that needed the *argument evaluation
  order* to be wrong.
- Drive the public entry point. `reportPrivateUsage` is on in strict
  pyright, so touching module-private names from a test is a diagnostic
  error; `getattr(module, "_name")` is the established escape hatch.
- No timing races for lower bounds: use `threading.Barrier` or events when
  the assertion is "at least N overlapped". An *upper* bound on started
  work (interrupt cases) needs headroom and a comment explaining it.
- Structural defects (a global installed outside the `try` that restores
  it) cannot be provoked from outside once the structure is right — guard
  them statically with AST, as `tests/test_architecture.py` does.

### Documents (`.trae/`)

- A plan document is the single source of truth: when the code moved, the
  plan moves in the same commit — function and parameter names, case
  names, gate commands, line-number citations. A citation into code that
  has since shifted is a finding.
- Review findings are filed per round as
  `.trae/reviews/YYYY-MM-DD-<topic>.md` (read-only fact document: findings,
  evidence, disposition) with a matching section in the plan; the legacy
  backlog keeps only a pointer. Two files tracking the same status drift.
- Bilingual docs (`README.md` + `README.zh.md`, `yate/docs/*.en.md` +
  `*.zh.md`) are updated as a pair, and a promise must match measured
  behaviour — "live progress" only holds on a terminal, and rich prints a
  final frame even when redirected.

## Gates to run and cite

| Command | Pass standard |
|---|---|
| `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 0 errors |
| `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-fail-under=75` | all green, coverage ≥ 75 |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 22 passed |
| `.venv\Scripts\python.exe -m pytest tests/<touched> -q` | all green |
| `.venv\Scripts\python.exe -m pytest tests/<touched> --cov=tools.pack.<mod>` | when the change lives in `tools/` |

`pyproject.toml` sets `addopts = "-q"`, so adding another `-q` swallows the
summary line; read it with `-o addopts=`.

## Loop discipline for a fix that is still under review

1. Review the cumulative diff, not just the last commit.
2. Fix what is found, then review again — a fix can hide the next defect
  (the collect-policy leak survived three rounds precisely because each
  round only read its own change).
3. Re-verify earlier findings against the current code; a record claiming
  "fixed" while the code does not show it is a finding of its own.
4. Stop when a full pass reports nothing new, and say so explicitly —
  list the dimensions checked and the mutations run.
