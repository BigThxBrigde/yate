# 2026-11-06 unnamed-buffer LSP attach review round 2 (post-iteration)

- Branch: `fix/enew-args-lsp-attach` · primary range `383affe..HEAD` (3 plan/review commits + wave-3 code `28a5fdf`), plus full-range recheck `8e60598..HEAD`.
- Reviewer: `code-review-expert` (`.trae/agents/code-review-expert.md`), `python-code-review` skill from `.trae/skills/`, forced self-critique applied.
- Verdict: **LOOKS GOOD — 0 blocker / 0 major / 2 minor**. Round-1's 2 majors are closed; all 4 round-1 minors are disposed of. Can enter step 7.
- This is a read-only fact document; remediation is recorded in the plan, not scheduled here.

## 1. Round-1 major closure (verified with probes)

| Major | Closure evidence |
|---|---|
| #1 save-as onto a URI owned by another tab | `manager.py:462-464` owner branch + `:465` `on_document_shown`; measured notify sequence `didOpen, didOpen, didClose, didClose, didOpen`, `_open[y.py].doc is a`, new owner's didOpen carries `text == "a\n"`; negative drill on `383affe`: `AssertionError: assert new_uri in closes` |
| #2 path spelling vs URI equivalence | `manager.py:454-460` compares `protocol.path_to_uri`, drops the stale cache key; same-path save-as sends only `didOpen, didSave`, no didClose round-trip, cache has 1 key; negative drill on `383affe`: `AssertionError: assert ['textDocument/didClose'] == []` |

`_uri_cache.pop(previous_path)` was probed for accidental deletion: `_uri(doc)` runs first and rewrites the key, so no consequence. 4/4 wave-3 negative drills (including both `_opening` re-check cases) fail on the old implementation and pass on `28a5fdf`.

## 2. Findings (this round)

### [minor] 1 — plan-e §6 execution record still placeholders

`.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md:187-200` had all 8 rows `pending`, although plan-e §4.1/§5 require recording the negative drills and measured results. Rule: `plan-before-execute.md` (verifiable acceptance records). **Resolution**: resolved at step 7 — the main agent backfilled plan-e §6 (and every other sub-plan's execution record) with measured commands, exit codes and deviations; see [`../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md`](../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md) §6.

### [minor] 2 — same-URI retarget of a never-shown document does not attach

`yate/editor_lsp/manager.py:455-460`: when `previous_uri == new_uri`, `notify_saved(doc)` returns silently if the URI was never in `_open` (measured `_open == []`, `is_open == False`, `_clients == 0`). Normal UI flow is covered because `_submit_save_as` ends with `_refresh_ui()` → `doc_shown_later()` → didOpen, so downgraded to minor. Reviewer suggests falling back to `on_document_shown(doc)` when `new_uri not in self._open`, or documenting the caller precondition. **Disposition**: registered as residual backlog in main plan §6, not fixed in this issue (rules §二.6: minor-only → backlog). Note `manager.py` is at 797 lines; a fix must also respect the §三.7 800-line guard.

## 3. Self-critique registration

Confirmed: A (plan-e §6 backfill), B (same-URI never-shown attach). Deleted as
false positives / non-issues: C (`_uri_cache.pop` mis-delete — probed harmless),
D (`previous_uri` not cached — one save-as per user action, not a hot path),
E (`shutdown_all` leaking `_opening` — `finally` clears it, measured empty),
G (non-English test comments — architecture guard 37 passed), H (duplicate
didClose — same-URI branch returns early), I (tests rewriting existing cases —
numstat shows pure appends: `test_lsp.py` +267/−0, `test_cmd_enew.py` +10/−0).
Downgraded F (two tabs sharing one URI can still send didChange against the
other tab's state) to the already-registered residual backlog in main plan
§6, since the pre-fix behavior was "no attach at all" and the fix is a net
improvement.

Six-dimension leak check: correctness (owner / equivalent-URI / same-path /
concurrent-different-URI paths all probed), boundaries (`path is None`,
`previous_path is None`, `owner.doc is doc`, notify failure), exception
handling (best-effort didOpen/didClose/didSave with lazy `%` logging),
concurrency (`_opening` two re-checks + `finally`), performance (O(1) dict
lookups, no hot-path regression), types/coverage (pyright 0, manager.py 92%).

## 4. Gate commands actually executed (reviewer, exit codes)

| Command | Result | Exit |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` | 0 |
| `python -m pytest tests/ -q -n auto` | `3422 passed, 10 skipped in 76.56s` | 0 |
| `python -m pytest tests/test_architecture.py -q` | `37 passed` | 0 |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | `3422 passed, 10 skipped`; `TOTAL 19425 1081 6206 572 93%`; `Total coverage: 92.97%` (≥75) | 0 |
| `python -m tools.smoke_test run --jobs 4` | `1464/1464 checks`, `121/121 scenarios passed`, 76.08s | 0 |
| line count `manager.py` | `797` (`< 800`, no `SIZE_EXEMPT_FILES` registration) | 0 |
| `-n 1` recheck (focused set) | `83 passed`, agrees with `-n auto` | 0 |
| `tests/test_app_lsp.py` | `14 passed` | 0 |

Uncovered lines in `manager.py` no longer include round-1's `:364`,
`:387-388`, `:445` nor the wave-3 second `_opening` re-check. Negative drills
were run in an isolated clone of `383affe` in the system temp directory and
cleaned up afterwards; the main worktree stayed untouched.

## 5. Plan-conformance checks

All five plan-e rulings conform: URI identity, URI ownership, close-beats-open,
no new module/public method/`<800` lines, no `resolve()`/`normpath` in
`DocumentFlows`. Exclusive-file constraints hold (only `manager.py`,
`tests/test_lsp.py`, `tests/test_cmd_enew.py` + plan/review documents changed);
manuals, smoke files and other product sources are untouched in this wave.
Commit messages all follow `type(scope): subject`. The one plan deviation is
minor 1 above (backfill), now resolved. Main-agent step-7 gate re-measured
coverage at `92.86%` (vs `92.97%` here); both exceed the 75% threshold and the
difference is a normal parallel-coverage variance, recorded in main plan §7.
