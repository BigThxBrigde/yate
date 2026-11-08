# 2026-11-08 IKTF4Y extension trust hardening - code review r2 (Lua argv boundary only)

- Branch: `enh/extension-trust-hardening`, range `aa72147..HEAD`; the commit under review is `24f3ba4` (fix(security): normalise Lua argv tables at the extension boundary), 2 files / +65 -5.
- Reviewer: `code-review-expert` (`.trae/agents/code-review-expert.md`). The `Skill` tool returned `python-code-review not found`, so the agent file fallback frame was applied by hand (6 dimensions / 3 severities / finding format; `blocker` / `major` / `minor` labels). Forced self-critique executed before output.
- Narrowed scope by instruction: **only** the Lua argv boundary fix. `trust.py` / `bridges.py` / docs / plan records / `README.md` index are out of scope and not reviewed here.
- In-scope files: `yate/services/extensions/api.py` (`:14`, `:88-107`, `:646-663`), `tests/test_lua_extensions.py` (`:14`, `:34`, `:118`, `:121`, `:333-363`).
- Context read for evidence (read-only, unchanged): `yate/services/shell.py`, `yate/extensions/_yate.lua`, `yate/extensions/_yate.d.lua`, `tests/test_lua_defs.py`, `tests/test_extension_api.py`, `.trae/documents/extension-trust-hardening-review-fixes-plan.md` section 3.

## Verdict

**APPROVE - 0 blocker / 0 major / 3 minor.**

First-pass blocker #1 (Lua `yate.shell_argv` raised `TypeError` on first use) is **closed**, verified by a live lupa round-trip rather than text parity alone.


## 1. Gate commands I ran myself (exit codes)

Full six-gate suite was run by the main agent per instruction and is not re-run here. Rows below are the reviewer's own targeted evidence.

| Command | Result | Exit |
|---|---|---|
| `python -m pyright yate/services/extensions/api.py tests/test_lua_extensions.py` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_lua_extensions.py -q -k shell_argv` | `2 passed, 49 deselected` | 0 |
| `pytest tests/test_lua_extensions.py -q` (whole file) | 51 passed | 0 |
| `pytest tests/test_lua_extensions.py tests/test_extension_api.py tests/test_lua_defs.py tests/test_lua_engine.py -q -n 0` (plan section 3.3 acceptance set) | 110 passed | 0 |
| `pytest tests/test_lua_defs.py -q` | `3 passed` | 0 |
| `pytest tests/test_extension_api.py -q -k shell_argv` | `2 passed, 28 deselected` | 0 |

All runs used `-p no:cacheprovider`; no parallel-only failure surfaced in these files, so no `-n 1` recheck was needed.


## 2. Re-verification of the four mandatory questions

### Q1 - `_argv_values` covers both paths; does the duck typing misfire? (`api.py:88-107`)

**Both paths are correct.**

- Python `Sequence[str]` path: `api.py:96` `getattr(argv, "values", None)` is `None` for `list` / `tuple` / `deque`, so `api.py:101` `items = list(argv)` runs. Measured: `_argv_values(["a","b"]) -> ["a","b"]`, `_argv_values(("a","b")) -> ["a","b"]`, `_argv_values(deque(["a"])) -> ["a"]`.
- 1-based Lua table path: a lupa table is **not** a `dict` (measured `isinstance(t, dict) -> False`) but **does** expose a callable `values` (measured `callable(getattr(t, "values", None)) -> True`), so `api.py:97-99` takes the `values()` branch. Measured on `lua.eval('{ 1, 2 }')`: `list(t) -> [1, 2]` (the integer **keys**) while `list(t.values()) -> [1, 2]` (the **values**). For a string table such as `{"echo", "hi"}`, `values()` yields the strings `["echo", "hi"]` where `list()` yields `[1, 2]`. The 1-based-key bug of first-pass blocker #1 is therefore fixed at the right layer: `services/shell.py` keeps its `Sequence[str]` contract untouched.
- Non-string entries: `api.py:103-105` loops every item and raises `TypeError("shell_argv entries must be strings")` **before** `run_argv` is called, so the failure no longer surfaces as a confusing `TypeError` inside `" ".join` at `shell.py:155+`. The message is unique in the repository (grep: only `api.py:105`), which is why the negative test's `match=` is source-traceable.
- Duck-typing misfire assessment: a plain `dict` **is** treated as a Lua table (`_argv_values({"0": "x", "1": "y"}) -> ["x", "y"]`, measured). This is a real behavioural quirk but **not** a defect against the declared contract: the parameter is annotated `Sequence[str]` (`api.py:646`) and a `dict` is not a `Sequence`, so passing one is a caller-side contract violation that pyright strict rejects. Plan risk row (`extension-trust-hardening-review-fixes-plan.md:198`) registered this trade-off explicitly and chose the per-item `isinstance(str)` validation as the mitigation, which is present at `api.py:104`. Recorded as minor #1 below, not as a blocker.

### Q2 - Is the new lupa test a real round-trip, or vacuous? (`test_lua_extensions.py:333-351`)

**Real round-trip, non-vacuous. Evidence:**

- Path actually exercised: `runtime.execute("return yate.shell_argv({_PY_EXE, '-c', _LUA_CODE})")` (`:344-346`) builds a **real Lua table literal**, `_yate.lua:159-161` forwards it as `api.shell_argv(argv)`, `api.py:663` normalises via `_argv_values`, and `run_argv` spawns the process. The test is `requires_lupa`-guarded and **runs** on this host (`2 passed, 49 deselected`, not skipped; lupa 2.8 present).
- Assertions are all non-trivial: `isinstance(result, ShellResult)` (`:348`) proves a **real** `ShellResult` crossed back over the lupa boundary; `result.returncode == 0` (`:349`) proves the child really ran; `"argv-lua-ok" in result.output` (`:350`) proves the `-c` payload reached the child as an argv element (i.e. the vector was not empty and not mangled); `result.cwd == tmp_path` (`:351`) is a genuine cwd assertion - `:338` sets `bundle.workspace.root = tmp_path` and `shell_cwd` (`shell.py:65`) prefers `workspace_root` over the document dir, so the value is not accidental.
- `type(yate.shell_argv) == "function"` (`:343`) additionally proves the Lua wrapper exists, so a missing wrapper cannot pass silently.
- Negative test `test_shell_argv_rejects_non_string_table_entries` (`:354-363`) does reach the intended failure: `{1, 2}` delivers Lua integers, `_argv_values` rejects them at `api.py:104-105`, and the message surfaces through the lupa boundary. Measured `1 passed`.
- Discrimination check: the first-pass blocker was reached through `list()`, which yields integer keys; the new positive test passes a string table, for which `list()` yields the integer keys `[1, 2, 3]` and `run_argv` would raise inside `" ".join` at `shell.py`, so the positive test **would** have failed against the pre-fix code. The test is a genuine regression lock, not a tautology.

Residual strictness gap (minor #2 below): the negative test asserts `pytest.raises(Exception, ...)` rather than `TypeError`, so it locks the message but not the exception class.

### Q3 - Return-type tightening and whether shell.py was touched

**Tightening is correct and consistent.**

- `run_argv` returns `ShellResult` unconditionally (`shell.py:140-119`: both the timeout path `:112-114` and the normal path `:119` construct and return a `ShellResult`; the empty-vector case raises `ValueError` at `:157` and the `OSError` case is handled inside). It never returns `None`. So `shell_argv(self, argv: Sequence[str]) -> ShellResult` (`api.py:646`) is exactly right, and the docstring update (`api.py:651-653`) states the reason.
- Lua wrapper and its stub stay compatible: `_yate.lua:157-161` and `_yate.d.lua:59-63` both declare `---@return any result`, i.e. unconstrained, so no Lua-side change was required and none was made. Docs (`extensions.en.md:335-337`, `extensions.zh.md:305-306`, `manual.en.md:1264-1267`, `manual.zh.md:1136-1137`) describe argv semantics without promising `nil`, so they do not contradict the tighter annotation.
- `shell.py` untouched, verified two ways: `git diff aa72147..HEAD -- yate/services/shell.py` is **empty** (exit 0), and `git log --oneline -3 -- yate/services/shell.py` shows the last commit touching it is `3a93570`, which is an ancestor of `aa72147`. Therefore `run_shell` / `run_argv` / `_popen` / `_capture` are byte-identical to the pre-fix baseline. `ExtensionContext.run_shell` (`api.py:170`) and `ExtensionAPI.shell` (`api.py:642-644`) keep `ShellResult | None`, correctly, because `_ctx.run_shell` genuinely can return `None`.

### Q4 - New blocker/major, and first-pass blocker closure

**No new blocker or major. First-pass blocker #1 is closed.**

Checked and clean:

- No new `# pyright: ignore` / `type: ignore` in the commit; local pyright on both changed files reports `0 errors, 0 warnings, 0 informations` (exit 0).
- `24f3ba4` touches exactly 2 files (`yate/services/extensions/api.py`, `tests/test_lua_extensions.py`); `git show 24f3ba4 --stat` confirms. `yate/editor.py` not touched, facade `__all__` not touched (`git diff aa72147..HEAD -- yate/ | findstr` for `pyright:` / `editor.py` / `__all__` returned nothing).
- No relative imports added: `api.py:14` extends the existing absolute `from collections.abc import ...` line; `Iterable` is a stdlib ABC, and `cast` / `Callable` were already imported (`:14`, `:17`). No `TYPE_CHECKING`, no new `Protocol`, consistent with `.trae/rules/architecture-boundaries.md`.
- Layering preserved: lupa knowledge stays in the L3 extension adapter (`api.py`), not pushed down into L0 `yate/services/shell.py`; `api.py` imports only `yate.services.shell` among services, no `editor_view` / `editor` / `app` edge introduced.
- Contracts intact: `test_extension_api.py:585-608` (Python `list` path, metacharacter non-interpretation, empty-vector `ValueError` with `Popen` spy) still passes unchanged; the pre-existing `assert result is not None` at `:589` is now redundant but harmless and out of the fix's write scope.
- `tests/test_lua_defs.py` three-surface static guard passes (`3 passed`), so the Lua/Python surface parity is unchanged.

First-pass blocker #1 evidence of closure: the crash was `TypeError: sequence item 0: expected str instance, int found` from `list(_LuaTable)` yielding integer keys. With the fix, the same real-Lua call returns `ShellResult(returncode=0, output containing argv-lua-ok, cwd=tmp_path)`, asserted in a live test. Root cause addressed at the boundary, contract layer untouched.


## 3. New findings

### [minor] 1 - `_argv_values` reads a caller-supplied `dict` by value (accepted trade-off, documented reason)

- Location: `yate/services/extensions/api.py:96-99`.
- Measured: `_argv_values({"0": "x", "1": "y"}) -> ["x", "y"]`, i.e. a mapping is silently treated as a Lua table and its **values** become argv. A plain `Sequence[str]` caller is unaffected.
- Why minor, not major: the declared parameter is `Sequence[str]` (`api.py:646`), a `dict` is not a `Sequence`, and pyright strict flags such a call, so this needs a contract-violating caller. The plan registered the trade-off and chose per-item validation as mitigation (`extension-trust-hardening-review-fixes-plan.md:198`, implemented at `api.py:104`). The failure mode is also loud, not silent corruption of a valid vector.
- Optional hardening (not required for approval): gate the branch on `not isinstance(argv, Mapping)` or on `not isinstance(argv, Sequence)`, so a mapping is rejected with the existing `TypeError` instead of becoming argv. If taken, add a test next to `:354`.

### [minor] 2 - Negative lua test matches `Exception`, not `TypeError`

- Location: `tests/test_lua_extensions.py:362` - `pytest.raises(Exception, match="shell_argv entries must be strings")`.
- The `match` string is unique to `api.py:105`, so the assertion is source-traceable and not vacuous; but any exception carrying that text would satisfy it. Prefer `pytest.raises(TypeError, match=...)` per `extension-trust-hardening-review-fixes-plan.md:98-101`, which itself asked to tighten to the measured type. Measured behaviour supports `TypeError`: `api.py:105` raises exactly that. lupa re-raises across the boundary, so verify the propagated class before tightening.
- Non-blocking: the test does catch regressions that lose the validation.

### [minor] 3 - Two different idioms read a Lua table in the same module

- Locations: `api.py:96-99` uses `values()`; `api.py:126-148` (`_coerce_completer_result`) uses callable `keys()` + 1-based `__getitem__` walk.
- Both are correct and both are measured on real lupa tables, so this is maintainability, not correctness: a future reader has two patterns to reconcile. Optionally extract one small `_lua_table_values(raw)` helper next to `_coerce_completer_result`, or note in one docstring why the two differ (completer skips non-strings and must not coerce; argv rejects them).


## 4. Forced self-critique (status per candidate)

| Candidate | Counter-evidence | Status |
|---|---|---|
| `_argv_values` duck typing misfires on `dict` | Real (`{"0": "x"} -> ["x"]`) but needs a `Sequence[str]` contract violation; pyright rejects it; plan registered the trade-off and added per-item validation | **Kept, minor #1** (not major: no valid-caller path) |
| `str` input split into characters: `_argv_values("ab") -> ["a", "b"]` | Measured. **Not a regression**: `str` is a `Sequence[str]`, and pre-fix `run_argv("ab")` also did `list()` -> `["a", "b"]` then `join` -> `"ab"`, identical outcome. Behaviour is unchanged by this commit | **Deleted** (pre-existing, not introduced here) |
| `pytest.raises(Exception, ...)` too broad | `match` text is unique to `api.py:105`, so the assertion is traceable; only the class is unpinned | **Kept, minor #2** (downgraded from a would-be major: the test does catch the regression) |
| Two Lua-table idioms in one module | Both correct on real lupa tables | **Kept, minor #3** (downgraded to maintainability) |
| `result.cwd == tmp_path` might be tautological | `:338` sets `workspace.root`; `shell_cwd` (`shell.py:65`) prefers it, so the assertion is genuine | **Deleted** (no defect) |
| New test might be vacuous | Positive test traverses a real `{...}` literal through `_yate.lua` -> `api.shell_argv` -> `run_argv`; asserts real `ShellResult`, `returncode == 0`, child stdout, cwd. Would fail pre-fix because `list()` yields integer keys | **Deleted** (no defect) |

Missed-dimension reverse sweep: correctness (covered, Q1/Q2), boundary conditions (empty vector still `ValueError` via `run_argv:157`, verified by `test_shell_argv_rejects_empty_vector`; non-string entries covered), exception handling (validation before spawn; message unique), concurrency (no shared mutable state added; pure local function), performance (one extra `list()` over a small argv - negligible), types (pyright 0; annotation tightened in the right direction; `shell` correctly keeps `| None`), test coverage (new live tests + existing Python-path tests; `test_lua_defs` parity intact). No further gap found.

## 5. Verdict and recommendations

**APPROVE for merge from the Lua argv boundary perspective: 0 blocker / 0 major / 3 minor.**

- First-pass blocker #1: **CLOSED** (live lupa round-trip, real `ShellResult`, asserted in `test_lua_extensions.py:333-351`; root cause addressed at the L3 boundary).
- First-pass minor #4 (`ShellResult | None` too wide): **CLOSED** at `api.py:646`.
- The three minors above are all optional polish; none blocks merge. minor #2 is the cheapest and most valuable (pin `TypeError`).
- Out of scope here by instruction: trust store write-side symmetry, bridges docstring, docs, plan/record corrections - not reviewed in this round.

