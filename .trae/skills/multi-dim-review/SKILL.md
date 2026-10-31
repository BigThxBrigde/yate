---
name: multi-dim-review
description: >
  Multi-dimensional review framework for the yate repo. Consolidates the
  repo's review practice into one entry point: the six generic dimensions of
  python-code-review / pr-review, the twelve dimensions of the 2026-10-18
  full-repo audit, a dedicated algorithm & complexity dimension (always
  prefer low time / space complexity), cross-layer call logging, and this
  repo's hard gates. Scope-adaptive: single file,
  branch diff, module, or whole-repo audit. Use when the user asks for a
  "多维度 review / 多维度审核", "comprehensive review", "full review",
  "repo audit", or a post-refactor quality sweep. For one snippet or file
  prefer python-code-review; for a pre-merge PR pass prefer pr-review; for
  runtime UI evidence use textual-pilot-smoke.
version: 1.0.0
---

# Multi-Dimensional Review (yate)

A scope-adaptive, **read-only** review framework that unifies this repo's
review practice into one checklist: the generic dimensions of
`python-code-review` / `pr-review`, the twelve dimensions of the 2026-10-18
full-repo audit (`../../reviews/2026-10-18-full-repo-audit-r3.md`), and the
repo's hard gates — thirteen dimensions in total, with a dedicated algorithm
& complexity dimension (lowest time / space complexity preferred by
construction) and cross-layer call observability. It produces
findings and verdicts only — it never edits
product code; fixes go through the plan workflow (`plan-before-execute.md`).

## Step 1: Load the Normative Sources

Read before judging; never review from memory:

- `../../rules/architecture-boundaries.md` — layers L0-L4, R1-R15, the §五
  self-check list and §六 guard-case table (authoritative architecture source)
- `../../rules/python-coding-style.md` — PEP 8 + PEP 20 dual track,
  pyright strict zero-diagnostics, §五 quick checklist
- `../../rules/doc-conventions.md` — doc naming, relative paths, bilingual pairs
- For audit scope also: `../../reviews/README.md` — open and deliberately
  deferred items; do not re-raise closed or deferred findings without new evidence

## Step 2: Determine Scope and Route

| `$ARGUMENTS` looks like | Scope | Depth |
|---|---|---|
| inline snippet or one `.py` path | single target | D1-D5, D8, D9 in depth; D6/D7 as a quick pass; D10-D13 only when behavior changed |
| `diff`, branch name, or base ref | branch diff | all 13 dimensions on the diff + hard gates (Step 5) |
| directory / module name / `repo` / `全仓库` | audit | all 13 dimensions; fan-out pattern (Step 6); review record (Step 8) |

Route instead of duplicating sibling skills:

- one snippet / one file deep-dive → `../python-code-review/SKILL.md`
- pre-merge PR pass with Gitee bot semantics and `impact` / `ask` modes →
  `../pr-review/SKILL.md`
- runtime or rendered-pixel evidence for UI behavior →
  `../textual-pilot-smoke/SKILL.md`

This skill is the right entry when the user wants all dimensions at once, a
whole-repo / module audit, or a post-refactor verification sweep.

## Step 3: The Thirteen Dimensions

Apply every dimension. A dimension with nothing to flag is reported as
"clean" in the summary table, never silently dropped. Repo-specific items
are what separate a real finding from a generic false positive — check the
registered exemption sets (Step 9) before flagging any of them.

### D1 Correctness
- Logic bugs, off-by-one, operator precedence; edge cases (empty / `None` /
  zero / very large); mutating caller data; mutable default arguments
- Behavior changes that break existing callers of a touched API
- Repo-specific: pane-tree invariants (closing docs must keep the active tab
  identity, not a numeric clamp); undo/redo delta semantics;
  `TextBuffer.take_dirty_range` (consuming) vs `dirty_range` (peek) contracts

### D2 Robustness & Error Handling
- No bare `except:`; every `except Exception` carries `# noqa: BLE001` with a
  reason; no silent swallowing — log or re-raise; resources via `with`
- Raise specific exception types, not bare `Exception`
- Repo-specific: `filterwarnings = ["error::RuntimeWarning"]` makes unawaited
  coroutines fail the suite — every `run_worker` coroutine must actually start

### D3 Security
- Generic: hardcoded secrets; `shell=True` + user input; unsafe
  deserialization (`pickle` / `yaml.load`); `eval` / `exec` on untrusted
  strings; path traversal from user input
- Repo-specific trust model: `extensions/` auto-load, project-level `yaterc`,
  and workspace themes are gated by workspace trust — any new auto-load or
  exec path must go through the same trust gate (r3 audit F2 precedent:
  an ungated project rc exec is an RCE-class finding)
- `.yxp` packaging: member-name casefold dedup, symlink guards, install /
  uninstall records; shell flows must not build commands by string concat

### D4 Algorithm & Complexity
- **Always prefer the lowest time complexity and the lowest space complexity
  implementation available.** This is a selection rule applied at
  construction time and judged by reading the code — never deferred to
  profiling:
  - Time: O(n^2) / O(n^3) scans where a dict/set index, sort, bisect, or
    incremental structure works; repeated min/max scans where a heap fits;
    quadratic string building
  - Space: O(n) auxiliary memory where O(1) / in-place works; materialized
    collections mid-pipeline where a generator / streaming / lazy view works;
    unbounded caches or lists that grow with usage and need a bound
    (bounded-cache precedent)
- Right data structure: list where membership testing needs a set; repeated
  dict lookups that should bind one result
- Work recomputed per call that should be precomputed once or updated
  incrementally
- Repo-specific: document / pane operations must not scale a full-document
  scan per keystroke; `editor_core/buffer.py` primitives and the
  `editor_view/*` render path are the benchmark (bisect interval-table
  precedent in `filled_rows`)
- Severity: a naive higher-complexity choice where a standard
  lower-complexity alternative exists is a finding **by construction** —
  MAJOR on hot or large-input paths, MINOR elsewhere; the D5 profiler
  discipline governs constant-factor tuning only, never the complexity
  class itself

### D5 Performance (I/O, Caching, Hot Paths)
- Generic: I/O inside loops (N+1); recomputed values (missing cache);
  string `+=` in loops instead of join; whole-file loads where streaming
  works; needless deep copies; sync work that could be deferred
- Repo-specific hot paths: the Textual render loop — flag render-path work
  that runs on every key event
- House rule for **constant-factor tuning**: no unmeasured optimization. A
  tuning finding without a profiler measurement is reported as a suspect
  (疑点, needs profiler), not a defect (r3 precedent: "0 defects, 2
  suspects"). This does not apply to complexity-class findings (D4): the
  class is established by construction and needs no profiler

### D6 Architecture Boundaries
Run the §五 self-check of `../../rules/architecture-boundaries.md` on the
target. Non-negotiable highlights (any violation is `[BLOCKER]` by definition):
- R1: only `cli.py` imports `yate.app`; R3: `editor_view/*` never imports
  `editor` / `app`; R4: UI-free packages/files never import `editor_view`
- R2: no new `Protocol` (frozen whitelist: `PaneRegistry`, `SyntaxBackend`,
  `_TsPoint`, `_TsNode`); R6: zero `TYPE_CHECKING` repo-wide
- R5/R7: built-in tables direction and shell-only population
- R9: widget ids frozen — changes must sync `yate/resources/app.tcss`
- R10: one keypress one dispatch; unrecognized keys fall through, never an
  unconditional swallow (the completion-popup lesson)
- R11: flows modules import `editor_view` only inside `UI_FROZEN_FILES`;
  new imports must be registered there first
- R12: logs only via `tracing.get_logger(__name__)` with lazy `%` placeholders;
  no `self.log` / `self.app.log`, no devtools channel access
- R13: theme ownership in L2; no class-level `ScrollBar.renderer` patch
- R14: extension facade's 14 frozen names; no direct submodule imports
- R15: scrollable widgets call `apply_slim_scrollbars` + `apply_scrollbar_theme`
- Banned identifiers: `*Feature` / `*Host` / `*Ops` / `*Delegate` /
  `*Controller` (whitelist: `PaneHost`, `*Manager`; flow modules are
  `*Flows`, sync adapters named by verb such as `LspSync`)

### D7 Project Structure & Module Responsibility
- Single file > 800 lines triggers a disposal review — check `SIZE_EXEMPT_FILES`
  (mirrors architecture-boundaries §三.7) before flagging; multi-responsibility
  mixing must split, single-responsibility long files may be exempt
- Package `__init__.py` stays lazy: no re-exports except registered facade
  exceptions (`editor_view/theme.py`, `services/extensions/` facade,
  L0 leaf re-exports with exception notes)
- New flow modules follow the §三.8 checklist: `*_flows.py` / `*Flows`,
  declared on `Editor`, built in `_build_*` factories with injected
  collaborators, no App handle
- No central interface / public-type layer; share concrete objects

### D8 Typing & Static Discipline
- `from __future__ import annotations` as the first executable line of every
  module; full annotations on public APIs; pyright strict zero diagnostics
- Native lowercase generics (`list[str]`), `X | None` not `Optional`,
  PEP 695 `type X = ...` for module/class-level `Callable` aliases
- No `Any` without a reason comment, no `# type: ignore`; `App[None]` /
  `Screen[None]` are the only precise forms; `@override` on overrides
- Absolute imports everywhere — `from .x` is banned even inside a package

### D9 Style & Idiom (PEP 8 + PEP 20)
- 4-space indent, lines <= 100 chars, house naming table; guard clauses and
  early returns, nesting <= 3; truthiness tests; comprehensions over
  append-loops where they stay readable
- Comments and docstrings: **English only, ASCII only** (no CJK, fullwidth
  punctuation, `§` / `°`) — new hits must be rewritten,
  `NON_ASCII_COMMENT_EXEMPT` is frozen
- No `print()` in `yate/` outside `PRINT_EXEMPT_SITES`; log via tracing with
  lazy `%` placeholders, never f-strings
- Prose docstrings with Sphinx cross-refs; `#:` for module-level constants

### D10 Concurrency, Runtime & Observability
- Async work via `App.run_worker` / `*_later` helpers; debounce via
  `asyncio.get_running_loop().call_later`; no cross-thread UI mutation
- **Cross-module / cross-layer calls are observable**: significant
  invocations across a module or layer boundary (flows reaching into
  collaborators, worker threads, callbacks without App context) log via
  `tracing.get_logger(__name__)` with lazy `%` placeholders — a cross-layer
  call whose failure leaves no log record is a finding
- Key paths must not double-dispatch (R10) and must fall through keys they do
  not consume; the `support_mouse` gate stays inside `YateApp.on_event`
- Theme is process-global — tests and smokes that switch themes must restore
- Timing-sensitive code paths must be tested without real sleeps

### D11 Tests & Verification
- Touched behavior has tests; guard-worthy violations become
  `tests/test_architecture.py` cases, validated by a negative drill
  (revert the fix, watch the guard fail, restore)
- No real-sleep assertions: monkeypatch the window constant or poll with
  `wait_until`; `caplog` tests must set the `yate` logger `propagate=True`
  (the root logger is silenced by design)
- UI / interaction / render / keypath changes must run the smoke runner
  (`tools.smoke_test`); intentional UI changes re-snapshot baselines
- Coverage of touched modules in question → run the coverage gate (Step 7)
  and list uncovered lines

### D12 Docs, Bilingual Sync & Commit Hygiene
- Bilingual pairs updated together: `yate/docs/*.en.md` + `*.zh.md`,
  `manual.{en,zh}.md` for user-visible behavior, `README.md` + `README.zh.md`
- `CHANGELOG.md` / `CHANGELOG.zh.md` are generated by `tools.changelog` —
  never hand-edited; behavior changes must land with changelog-covered
  commit messages
- `.trae/` markdown uses relative paths, no machine-local paths
- Commit messages follow `../../rules/git-commit-message.md`:
  `type(scope): subject`, English throughout

### D13 Hard Gates (run, don't guess)
Run the commands in Step 7 and report real exit codes; a red gate is
`[BLOCKER]`. Pure-docs changes are exempt from tests per `misc-rules.md` §三 —
state the exemption explicitly instead of skipping silently.

## Step 4: Evidence Discipline (before any finding is reported)

1. Every finding carries `file:line` verified by re-reading the current file,
   never from memory.
2. Adversarial self-check per finding: does context invalidate it (caller
   guarantees, registered exemptions, existing guards, rule exception
   clauses)? Is the severity inflated or deflated? Delete or downgrade with a
   one-line reason; prefer withholding an uncertain claim over asserting
   without evidence.
3. Miss sweep: re-walk all 13 dimensions for obvious gaps before finalizing.
4. Gate numbers are real: run the commands yourself and report exit codes.
   Never quote a number you did not produce — subagent self-reports included;
   re-run their scope independently (only landed, verifiable results count).

## Step 5: Branch-Diff Scope Extras

- Base ref: merge-base with `main` (fall back to `master`) when not given.
- Noise filter: lock files, binaries, `*.pyc`, pure reformatting hunks —
  mention once as skipped, do not review their content.
- Modes: `review` (default: all dimensions + verdict + action plan),
  `impact` (change overview + risk tiers, no verdict),
  `dims=<list>` to restrict dimensions (e.g. `dims=algo,perf` → D4, D5).
- Every changed file is evaluated against all requested dimensions; verdict
  and finding format per Step 8.

## Step 6: Audit Scope — Fan-Out Pattern

For directory / repo audits (precedent:
`../../reviews/2026-10-18-full-repo-audit-r3.md` §二):

1. Group the 13 dimensions, <= 3 dimensions per reader (precedent shape,
   r3 audit's 5 readers: SA correctness + robustness, SB security +
   algorithms + performance, SC architecture + structure + responsibility,
   SD typing + style + runtime observability, SE tests + docs + gates —
   5 readers for 13 dimensions).
2. Spawn read-only explorers in waves (batch <= 3, hard cap 6 concurrent);
   each returns only `file:line -> evidence -> conclusion`; no file edits,
   no gate runs by readers.
3. The main agent re-verifies every reported finding (Step 4) and runs all
   gates personally (Step 7).
4. Registered / deferred items are re-checked for current validity, not
   re-raised as new findings.

## Step 7: Gate Commands

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m tools.changelog check
```

- Coverage threshold (75) is single-sourced in `pyproject.toml`; a partial
  run must pass `--cov-fail-under=0`.
- pyright may need its bundled node on PATH:
  `$env:PATH = "$env:LOCALAPPDATA\pyright-python\nodeenv\Scripts;$env:PATH"`.
- `-q` output may omit the summary line on some runners — trust exit codes.
- After editing files, run pytest on a fresh state; immediate re-runs can hit
  stale `__pycache__` timing artifacts.
- A parallel-run failure is re-run with `-n 1` / `--jobs 1`: a real defect and
  a load-timing assumption are both fixed, never recorded as "flaky".

## Step 8: Output Format

Start with a one-line verdict:

```
Overall: [APPROVE | REQUEST_CHANGES | BLOCKED — blocker(s) found]
```

Then a per-dimension summary (omit nothing; "clean" is a result):

| Dimension | Verdict | Key findings |
|---|---|---|
| D1 Correctness | clean / 1 MAJOR | ... |

Then findings grouped by severity, omitting empty tiers:

```
[BLOCKER|MAJOR|MINOR] <file>:<line> — Short title
Problem: what is wrong and why it matters, with the evidence quote.
Fix:
  <suggested direction or snippet> — a suggestion only, never applied.
```

| Severity | When to use |
|---|---|
| `[BLOCKER]` | security vulnerability, architecture violation, red hard gate, crash in normal use |
| `[MAJOR]` | edge-case bug, significant performance issue, swallowed exception, broken bilingual sync |
| `[MINOR]` | style / readability / idiom, dead code, naming, doc drift |

Then a **Deferred** section: findings confirmed real but deliberately not
fixed now (登记不修), each with its reason — keep findings separate from
scheduling, per the house review-record convention. End with a short
**Strengths** section.

Audit scope additionally writes the record to
`../../reviews/YYYY-MM-DD-<topic>.md` (topic in lowercase hyphenated English;
a read-only facts document — findings and verdicts only, no fix scheduling,
per `doc-conventions.md` §二.1) and appends one row to that directory's
`README.md` index. For diff scope, write a record the same way when this is a
formal round (pre-merge review, audit round, or user-requested registration).

## Step 9: Registered Exemptions — Check Before Flagging

These live in `tests/test_architecture.py` and the rule texts; a hit inside a
registered set is compliant, a new hit outside them is a finding:

- `SIZE_EXEMPT_FILES` — files over the 800-line threshold (D7)
- `UI_FROZEN_FILES` — flows modules allowed to import `editor_view` (D6 R11)
- `NON_ASCII_COMMENT_EXEMPT` — frozen; new non-ASCII comments must be
  rewritten, never registered (D9)
- `PRINT_EXEMPT_SITES` — sanctioned `print()` hosts in `yate/` (D9)
- R2 `Protocol` whitelist and naming-guard whitelists (D6)
- `SCROLLBAR_EXEMPT` — scrollable widgets without the R15 scrollbar pair (D6)

## Step 10: Feedback Loop

If the user rejects a finding with context ("not an issue because ..."),
re-run the affected dimension with that context, state explicitly which
findings were withdrawn and why, and do not re-raise them in the session
without new evidence.

## Decision Guidance

- Pre-review, not gatekeeper: findings frame risks; the human merges.
- Do not rewrite working logic for style; the readability gain must be clear
  and behavior equivalent.
- A consistent deviation from the style rules is noted once, not per instance.
- Scope discipline: review the target; do not speculate about untouched code.
- Rule conflicts: `task-orchestration.md` wins over other process rules;
  product-side conflicts resolve per `architecture-boundaries.md`.
