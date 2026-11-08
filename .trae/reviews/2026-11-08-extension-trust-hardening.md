# 2026-11-08 IKTF4Y extension trust hardening review (#64)

- Branch: `feature/enh-extension-trust-hardening`, range `af81d11..HEAD` (6 commits, not 8: `3af3c3a`, `31ce397`, `01a80d3`, `3a93570`, `9112a91`, `aa72147`; `git log --oneline af81d11..HEAD` measured).
- Reviewer: `code-review-expert` (`.trae/agents/code-review-expert.md`); the `Skill` tool returned `Skill "python-code-review" not found`, so the fallback frame in `.trae/skills/python-code-review/SKILL.md` (6 dimensions / 3 severities / finding format) was applied by hand, and the agent file's older `blocker` / `major` / `minor` labels. Forced self-critique applied.
- Scope: the 6 product files `yate/services/shell.py`, `yate/services/trust.py`, `yate/services/data_store.py`, `yate/services/yxp/{install,manifest}.py`, `yate/services/extensions/{api.py,lua/runtime.py}`, `yate/cli.py`, `yate/diagnostics.py`, `yate/flows/shell_flows.py`, the two Lua surfaces, 11 test files, 8 bilingual docs, 11 plan/issue docs.
- Requirement source: [`../documents/extension-trust-hardening-issue.md`](../documents/extension-trust-hardening-issue.md) (Gitee IKTF4Y, 8 findings + section 5 acceptance); plan and rulings in [`../documents/extension-trust-hardening-plan.md`](../documents/extension-trust-hardening-plan.md) and [`../documents/extension-trust-hardening-plans/overview.md`](../documents/extension-trust-hardening-plans/overview.md).
- Verdict: **BLOCKED - 1 blocker / 1 major / 4 minor**. Read-only fact document; remediation is not scheduled here.

## 1. Gate commands actually executed (reviewer, exit codes)

Full six-gate run is left to the main agent by instruction; the rows below are what this reviewer ran itself.

| Command | Result | Exit |
|---|---|---|
| `python -m pyright yate/services/shell.py ... yate/flows/shell_flows.py` (9 changed product modules) | 0 errors, 0 warnings, 0 informations | 0 |
| `python -m pyright` on the 11 changed test files | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| `pytest tests/test_trust.py test_data_store.py test_shell.py test_diagnostics.py test_yxp.py test_extension_api.py test_extension_bridges.py test_cli.py test_shell_flows.py test_lua_engine.py -q -n 1` | all green (3 skips: `test_trust.py:94` POSIX bits, `test_shell.py:355/366` POSIX shell discovery) | 0 |
| `pytest ... --cov=yate.services.shell,trust,data_store;yate.diagnostics;yate.services.yxp.install --cov-branch --cov-fail-under=0` | TOTAL 96%; trust.py 100%, shell.py 97%, diagnostics.py 98%, install.py 93%, data_store.py 90% | 0 |
| `python -m tools.mdlint yate/docs yate/resources README.md README.zh.md --auto-lang --check` | `check: 311 violation(s) in 21 files` (pre-existing baseline; see section 3) | 1 |

Targeted runs above were executed with `-n 1` only; no parallel-only failure surfaced, so no flake-vs-defect split was needed for these files. `pytest tests/ -q -n 1` was started but exceeded the tool timeout after ~10% (no failures observed in the completed portion); the full suite remains a main-agent gate.

Uncovered lines in changed modules are all pre-existing error branches, not new code: `shell.py:108-109` (double-failure reap `log.error`), `data_store.py:102-104/148-150/161-163` (`OSError` warnings), `install.py:109-110` (`mkdir` `OSError`).

## 2. Findings

### [blocker] 1 - Lua `yate.shell_argv` raises `TypeError` on first use

- Evidence: `yate/extensions/_yate.lua:159-161` forwards `api.shell_argv(argv)`; `yate/services/extensions/api.py:624` annotates `argv: Sequence[str]`; `yate/services/shell.py:155-159` does `args = list(argv)` then `label = " ".join(args)`.
- A Lua table arrives as `lupa.lua54._LuaTable`; `list()` on it yields the integer **keys**, not the string values, so `args == [1, 2]` and `" ".join` raises `TypeError: sequence item 0: expected str instance, int found`.
- Reproduced directly against the shipped code (exit 1):
  `python -c "from lupa.lua54 import LuaRuntime; from yate.services.shell import run_argv; rt=LuaRuntime(unpack_returned_tuples=True); rt.globals().run_argv=run_argv; rt.execute('return run_argv({\"echo\",\"hi\"})')"` -> traceback ending at `shell.py:159` `label = " ".join(args)` / `TypeError: sequence item 0: expected str instance, int found`. A probe of the raw conversion showed `TYPE _LuaTable` / `ASLIST [1, 2]`.
- Impact: the interface is documented as Lua-callable in six places (`_yate.lua:74`, `_yate.d.lua:63`, `yate/docs/extensions.en.md:1041`, `extensions.zh.md:951`, `manual.en.md:1264`, `manual.zh.md:1135`) yet crashes on the first documented call. `blocker` per the "regular use crashes" rule. No test covers the Lua to Python path: `tests/test_extension_api.py:580-610` exercises only the Python `api.shell_argv`; `tests/test_lua_defs.py:41,77` only asserts text parity.
- Fix direction: normalise in `run_argv` (e.g. accept an iterable of `str` and validate per element with a clear `ValueError`), or convert at the boundary - but a `_LuaTable` must be read by value (sequence comprehension over `1..n` or `table.unpack`) rather than `list()`. Add a real lupa round-trip test (guarded by `requires_lupa`) asserting `yate.shell_argv({"echo", "x"})` returns a `ShellResult`-shaped value, so `test_lua_defs` text parity cannot mask this again.

### [major] 2 - symlinked trust store: `:trust` reports success but never persists

- Evidence: `yate/services/trust.py:83-85` makes `load_trusted_workspaces` return `set()` for a symlinked store, while `trust_workspace` (`trust.py:128`) consults that same loader only to skip duplicate writes, then appends through the link at `trust.py:140-141` and returns `True` at `:144`.
- Reproduced (exit 0): `trust_workspace(repo, link) -> True`, `is_trusted(repo, link) -> False`, and the link target did receive the resolved repo line.
- Impact: a user who symlinks `~/.yate/trusted_workspaces` into a dotfiles repo gets `trusted <cwd>` on the message bar from `yate/flows/extension_flows.py:79-91`, extensions load for that session, and every later start silently refuses (`is_trusted` is False) with only a per-read warning. This is fail-closed, hence `major` rather than `blocker`, but the command output is factually wrong and the entry is unrevokable through the UI.
- Fix direction: reject a symlinked store on the write side too (return `False`, same warning), or make the read side follow the link while keeping the "link-free root" invariant on the recorded values. Document whichever is chosen in the `trust.py` docstring, which currently only covers a symlinked *parent*.

### [minor] 3 - `DataExtensionBridge` docstring not updated although plan section 3 promised it

- `yate/services/extensions/bridges.py:461-471` still says only that names go through `yate.services.data_store`; the new real-path rejection is unmentioned. Plan table (`extension-trust-hardening-plan.md:57`) states "`bridges.py` docstring is covered by plan_b"; `bridges.py` is absent from the changed-file list. Behaviour itself is correct and tested (`tests/test_extension_bridges.py:570-600`), so this is documentation drift only.

### [minor] 4 - `ExtensionAPI.shell_argv` return annotation is wider than reality

- `yate/services/extensions/api.py:624` returns `ShellResult | None`, but `run_argv` never returns `None`; the union is copied from `shell`, whose `None` comes from `_ctx.run_shell`. Harmless but it forces callers to null-check for no reason and weakens the contract the docstring describes.

### [minor] 5 - `run_argv` label is lossy for arguments containing spaces

- `yate/services/shell.py:159` uses `" ".join(args)` as the `ShellResult.command`, which the output overlay renders. `["echo", "a b"]` and `["echo", "a", "b"]` produce the same label. The docstring documents the label semantics, so this is accepted design, but a quoting-aware join (or carrying the raw vector) would make the overlay unambiguous.

### [minor] 6 - plan records 8 commits, branch has 6

- `.trae/documents/extension-trust-hardening-plan.md:146` and the task brief both say 8 commits; `git log --oneline af81d11..HEAD` lists 6 (`3af3c3a`, `31ce397`, `01a80d3`, `3a93570`, `9112a91`, `aa72147`). The wave table maps 4 waves onto 6 commits, so this looks like a counting slip rather than lost work; still worth correcting so the record matches the branch.

## 3. Verified sound (explicit no-finding statements)

Recorded so the main agent does not re-litigate these.

### S-02 yxp checksum gate

- The reject is genuinely first: `yate/services/yxp/install.py:87-93` raises before the `records.is_symlink()` probe (`:101`), before `ext_dir.mkdir` (`:107`) and before any record write. `ext_dir`/`package` come from `default_extensions_dir()` and `read_package()`, both side-effect free (`manifest.py:82-84`, `:147+`).
- Both product call sites behave: `yate/cli.py:317-326` passes `allow_unverified=args.allow_unverified`; `yate/commands.py:576` uses the default, so `:install-extension` rejects. No third call site exists (`git grep install_package -- yate tools pack`).
- Message/constant contract holds: `CHECKSUM_NAME` is imported from `manifest.py:53` (not a literal), and `tests/test_yxp.py:262` matches `missing 'checksum'`.
- Legacy opt-in tests were converted, not bypassed: `test_install_without_checksum_installs_unverified` (`test_yxp.py:251-256`) and `test_install_without_checksum_logs_warning` (`:608-615`) both now pass `allow_unverified=True`, and the new default-reject test asserts `not base.exists()` and no record.
- CLI subprocess path verified end to end (`tests/test_cli.py`, 2 passed), including the `Path.home()/.yate/extensions/hello.py` absence assertion.

### S-05 data_store real-path gate

- `_assert_inside_data_root` (`data_store.py:38-42`) compares `target.resolve()` against `data_root().resolve()` and is called from `resolve()` (`:86`), again after `mkdir` in `write_text` (`:122`) and again before `unlink` in `remove` (`:143`); the uncovered middle segments are the pre-existing `OSError` warnings only.
- Intermediate-directory symlinks are covered because `Path.resolve()` resolves every component, matching the four new tests (write/remove/read/names each assert the *outside* file is untouched).
- The tests are not vacuous: the symlink really is created on this host (`pytest -k symlink` on `test_data_store.py` -> `4 passed`, no skip) and `test_remove_...` asserts the victim content survived.
- `DataExtensionBridge` failure contract is intact: `False` / `None` / `[]` plus a warning (`bridges.py:473-504`), asserted at `test_extension_bridges.py:596-600` with a caplog check.

### S-03 shell refactor

- `_capture`/`_popen` are a pure extraction: `run_shell` keeps `shell=True`, the same Popen kwargs, the `[yate] failed to run shell` OSError fallback (`shell.py:135-136`), rc 124 and the `[yate] command timed out after {timeout}s` message (`:112-114`); 4 timeout/kill-tree tests pass.
- `run_argv` uses `shell=False`, rejects an empty vector with `ValueError` before `Popen` (`:156-157`, proven by the `spy_popen` test), and degrades a spawn failure to rc 1 (`:162-163`).
- cwd really is single-sourced: `shell_cwd` (`shell.py:63-65`) is used by both `ShellFlows._cwd` (`shell_flows.py:112-116`) and `ExtensionAPI.shell_argv` (`api.py:634-639`), and `test_shell_flows.py:128-137` pins the shared helper.
- Facade contract intact: `len(yate.services.extensions.__all__) == 14` (measured), `yate/editor.py` and `tests/test_architecture.py` are absent from `git diff --name-only` (800-line guard untouched), and the 3-way Lua/Python parity guards pass.

### S-04 trust hardening

- `_POSIX` is a module seam defaulting to `os.name == "posix"` (`trust.py:48`); `_chmod_quietly` (`:58-65`) covers **both** call sites (`:139` dir, `:143` file) and logs a warning instead of `contextlib.suppress`. The test asserts exactly two warnings (`test_trust.py:120`).
- The symlink refusal is on the store **file** only (`:83`), so a symlinked parent (`$HOME` -> elsewhere) is unaffected, matching the docstring at `:14-17` and the stated legitimate layout.
- The docstring claims nothing beyond the implementation: permanent path grant, manual revocation, best-effort POSIX chmod, Windows ACL explicitly out of scope (`:1-17`). No content-fingerprint or ACL promise.

### S-01 Lua trust boundary

- `_COMPILE_EXPR` (`runtime.py:69`) is a literal with no interpolation, and both parking globals are cleared unconditionally in `finally` (`:97-99`), so the exception path is covered too; the hostile-chunkname test passes and asserts both globals are `None` afterwards.
- The misleading phrasing is gone: the `package.path` note now says explicitly that `io`/`os` stay available and that this is not a sandbox (`runtime.py:118-125`), mirrored in `manual.{en,zh}.md` and `extensions.{en,zh}.md`.
- The three remaining "no file I/O" hits are coding conventions inside bundled game libraries (`game_engine.lua:22`, `engine_layout.lua:30`, `engine_json.lua:19`), not runtime-sandbox claims - correctly left alone.
- Contract-pinning test is real: `test_lua_engine.py:392-398` asserts `type(os.execute)..type(io.open)..type(require) == function:function:function`.
- The plan_d deviation is correct: `runtime.eval("return ...")` does raise `LuaSyntaxError: unexpected symbol near 'return'` (reproduced, exit 1), so `runtime.execute` is the right call; `_compile_chunk` keeps `eval` because `_COMPILE_EXPR` is a bare expression.

### S-07 diagnostics privacy note

- `_PRIVACY_NOTE` (`diagnostics.py:66-70`) is emitted after the divider and before the section loop (`:111-112`), i.e. ahead of the first `[system]` section; the test asserts index order (`test_diagnostics.py:62-69`) and that coloured output keeps the note verbatim. No field was redacted: `format_report` only gained two lines.

### Docs and engineering discipline

- 8 user-facing docs are paired en/zh and reference each other's anchors that actually exist (`extensions.en.md:134` "Trust model", reached from `:925`; `extensions.zh.md:118` "信任模型", reached from `:844`).
- No un-implemented capability is promised: no "signed", no lockfile, no CI SCA, no Windows ACL - each is labelled a known limitation / tracked separately (`README.md:65-69`, `README.zh.md:93-96`, `extensions.en.md:163-166`).
- 144 added lines across the 8 docs, **none** over 100 chars, so the `mdlint` exit 1 is entirely the pre-existing 311-violation baseline, not new debt.
- No `# type: ignore`, no `# pyright: ignore`, no bare `except:`, no relative imports, zero non-ASCII characters on added Python lines, and `from __future__ import annotations` present in every touched module.
- All 6 commits use English conventional-commit subjects with bodies.

## 4. Forced self-critique log

Each initial candidate was re-read against the source before this report was emitted.

| # | Candidate | Status | Reason |
|---|---|---|---|
| 1 | Lua `shell_argv` `TypeError` | **kept as blocker** | Re-verified by reading `shell.py:155-159` again and by reproducing the traceback through the real `run_argv`; six doc sites advertise it, and no test covers the Lua path. Not a UserError-style graceful failure - it is an uncaught `TypeError` on the documented call. |
| 2 | symlinked trust store asymmetry | **kept as major** | Re-verified by execution (`True` then `False`); failed upward classification to blocker because there is no data loss, no security bypass and no crash - it fails closed with a misleading success message. |
| 3 | `bridges.py` docstring drift | **kept as minor** | Confirmed `bridges.py` is absent from the diff while the plan promises the edit; behaviour is right, so minor. |
| 4 | ShellResult union annotation | **kept as minor** | Confirmed `run_argv` has no `None` return path; annotation-only, pyright is clean either way. |
| 5 | lossy `command` label | **kept as minor** | Confirmed at `shell.py:159`; downgraded from a suspected correctness bug to minor because `run_argv`'s docstring documents the joined label as intentional. |
| 6 | 6-vs-8 commit count | **kept as minor** | Measured with `git log --oneline`; affects plan bookkeeping only. |
| 7 | candidate: `data_store` TOCTOU still open | **deleted** | The check/`mkdir`/`unlink` sequence still has a theoretical window, but the module docstring and the second re-check are exactly the mitigation scope issue S-05 asked for; flagging "TOCTOU remains" would be an unfunded demand, not an evidence-backed defect. |
| 8 | candidate: `--allow-unverified` accepted without `--install-extension` | **deleted** | Verified `parse_args(["--allow-unverified"])` succeeds with an empty install list and does nothing; a silent no-op flag matches every other side-command flag in the same parser. |
| 9 | candidate: symlink tests are vacuous on Windows | **deleted** | Disproved by running them: `-k symlink` gives 4 passed with no skip on `test_data_store.py` and 1 passed on `test_extension_bridges.py`. |
| 10 | candidate: `_POSIX` seam leaks a test-only knob into production | **deleted** | The seam is a module-level constant read at call time, defaulting correctly; it is the minimal way to exercise the warning on Windows and is documented as such. |
| 11 | candidate: chunkname now accepts arbitrary text (contract loosening) | **deleted** | `_MODULE_NAME_RE` still gates shared module names; the chunkname is only a diagnostic label passed as a value, and the injection risk the issue flagged is gone. |

Reverse sweep for missed dimensions: concurrency (no new shared mutable state; `_capture` is per-process), performance (no new I/O or loops on the startup path; the trust read is unchanged in cost), exception handling (every new `except` logs - verified no bare or `except Exception` in the three touched L0 leaves), typing (pyright strict 0 on all 20 changed Python files), and test coverage (new branch lines covered except the pre-existing `OSError` warnings listed in section 1).

## 5. Follow-ups (not fixed here)

1. Fix finding 1 before merge and add a lupa-guarded Lua round-trip test; consider extending `tests/test_lua_defs.py` or a new test so text parity can never again stand in for a runtime call.
2. Decide the symlinked-store policy (finding 2) and align `trust.py`'s docstring, `trust_workspace`'s return value and the `:trust` message.
3. Update the `DataExtensionBridge` docstring (finding 3) and correct the commit count in the plan (finding 6).
4. Confirm the remaining gates the main agent owns: `pyright yate/ tests/ tools/ pack/`, `pytest tests/ -q -n auto`, coverage `--cov-fail-under=75`, `tools.smoke_test run --jobs 4`, `tools.changelog check`.
5. S-06 (dependencies / lockfile / CI SCA) and S-08 (`--translate-cmd`) stay documented-only / tracked separately, as the plan rules; the docs state that honestly and no code change is expected.

## 6. Main-agent errata and iteration disposition (2026-11-08)

- Commit-count correction (minor #6): `git log --oneline af81d11..HEAD` measures
  **6** commits (`3af3c3a`, `31ce397`, `01a80d3`, `3a93570`, `9112a91`,
  `aa72147`). The "8 commits" figure came from the main agent's review task
  brief, not from `extension-trust-hardening-plan.md`; this record's `:58`
  citation of plan line `:146` points at the wave-4 placeholder row instead.
  Index entry #64 records the measured 6.
- mdlint scope: the reviewer scanned `yate/docs yate/resources README.md
  README.zh.md` (311 hits, all pre-existing). The wave-3 gate scans only the
  8 changed documents: baseline 199 / current 199 / normalised diff 0. Both
  are pre-existing-only; the different file sets explain the different totals.
- blocker #1 fixed in `24f3ba4`: the L3 boundary helper `_argv_values()` reads
  a 1-based Lua table's `values()` instead of integer keys, `shell_argv` now
  returns `ShellResult`, and a `@requires_lupa` round-trip test asserts a real
  `ShellResult` (rc 0, output `argv-lua-ok`). Main-agent rerun: pyright 0,
  combined regression 297 passed / 1 skipped.
- major #2 fixed in `f526733`: `trust_workspace` refuses a symlinked store on
  the write side and returns `False`; the new test proves zero write-side side
  effects; `trust.py` docstring and 4 bilingual docs were aligned. Main-agent
  mdlint rerun on those 4 docs: baseline 146 / current 146 / normalised diff 0.
- minor #3 fixed in `f526733` (the `DataExtensionBridge` docstring keeps the
  atomic-write sentence and adds the real-path rule); minor #4 fixed in
  `24f3ba4` (return type tightened).
- minor #5 registered as a separate backlog: `ShellResult.command` is a
  display label (`run_argv`'s docstring says "not an executable command
  string"); a quoting-aware join would ripple into the label consumers, the
  Lua surface and every label assertion, so the churn outweighs the gain.
- Iteration design and acceptance criteria:
  [extension-trust-hardening-review-fixes-plan.md](../documents/extension-trust-hardening-review-fixes-plan.md).
- Re-review (index #65, scope `aa72147..HEAD`): the first re-review spawn
  returned nothing and wrote no file; one config-changing retry (batch 1 -> 2,
  split into F1/F2) delivered two independent `code-review-expert` records
  (`2026-11-08-extension-trust-hardening-r2-lua.md` and
  `...-r2-trust.md`). Both APPROVE with **0 blocker / 0 major**; blocker #1
  and major #2 are confirmed closed. Their 5 new minors were triaged: 3 fixed
  in `aa112a0` (tightened negative-test exception type, accurate `:trust`
  refusal message plus regression test, Chinese line reflow) and 2 registered
  with reasons (dict-as-values is a caller contract violation; two Lua-table
  reading conventions are a maintainability item).
- Final six gates, re-run by the main agent after those minor fixes: pyright
  `yate/ tests/ tools/ pack/` 0; `pytest tests/ -q -n auto` exit 0
  (3479 collected = 3469 passed / 10 skipped); architecture 37; coverage
  92.96% (threshold 75); smoke 121/121 scenarios with 1464/1464 checks;
  `tools.changelog check` 0 and `git diff --check` 0. Working tree clean,
  no push and no merge into develop.
