# 2026-11-06 IKSFS7 review round 1

- Branch: `fix/iksfs7` · range `8e60598..383affe` (6 commits, issue notes + plan + wave-1/2 products).
- Reviewer: `code-review-expert` (`.trae/agents/code-review-expert.md`), `python-code-review` skill from `.trae/skills/`, forced self-critique applied.
- Scope: `yate/commands.py`, `yate/editor_lsp/manager.py`, `yate/flows/document_flows.py`, `tests/test_cmd_enew.py`, `tests/test_lsp.py`, `tests/test_document_flows_saveas.py`, four bilingual manual files, smoke scenario and one baseline.
- Specification sources: [`../documents/iksfs7-issue-notes.md`](../documents/iksfs7-issue-notes.md), [`../documents/iksfs7-plan.md`](../documents/iksfs7-plan.md), [`../documents/iksfs7-plans/overview.md`](../documents/iksfs7-plans/overview.md) and sub-plans a-d.
- Verdict: **NEEDS WORK — 0 blocker / 2 major / 4 minor**. This is a read-only fact document; remediation is recorded in the plan, not scheduled here.

## 1. Gate commands actually executed (reviewer, exit codes)

| Command | Result | Exit |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations | 0 |
| `python -m pytest tests/ -q -n auto` | all green | 0 |
| `python -m pytest tests/test_architecture.py -q` | 37 passed | 0 |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | 3413 passed, 10 skipped; TOTAL 92.86% (19416 stmts / 1100 miss / 6202 branch / 572 brpart); manager.py 90%, document_flows.py 94%, commands.py 91% | 0 |
| `python -m tools.smoke_test run --jobs 4` | 121/121 scenarios, 1464/1464 checks, 76.95s | 0 |
| `-n 1` recheck (test_lsp + test_document_flows_saveas + test_cmd_enew) | all green, agrees with `-n auto` | 0 |

Uncovered lines in newly added code (`yate/editor_lsp/manager.py`): `364`,
`387-388`, `445`. Line sizes: manager.py 783, commands.py 617,
document_flows.py 533 — all below the §三.7 800-line guard.

## 2. Findings

### [major] 1 — retarget onto a URI owned by another tab

`yate/editor_lsp/manager.py:449-451` in combination with `:366` (`uri in
self._open` early return) and `:450` (`_close_uri`). Reproduced with real
`Document` objects and a fake client: document A (`x.py`) saved as `y.py`
while tab B already holds `y.py` leaves `_open[y.py]` owned by B and no didOpen
for A; if B's URI is closed first, the server sees a didClose with no
following didOpen. Reachability was also reproduced: `EditorSession.is_open`
prevents duplicate `:e` opens but not two tabs sharing a path after
`:saveas`. Suggested direction: compare `state.doc` identity and close the
previous owner's URI entry before re-opening.

### [major] 2 — path spelling vs URI equivalence

`yate/editor_lsp/manager.py:446` compares `Path(previous_path) == doc.path`
lexically, while `protocol.path_to_uri` resolves the path. Reproduced with
`sub/../a.py` vs `a.py`: `Path` equality is False but the URIs are equal, so
the retarget sends a needless `didClose` + `didOpen` and discards server-side
diagnostics — the exact behavior rejected by plan §3 C4. `_drop_uri_cache`
(`:190-194`) can also leave two keys with the same value. Suggested direction:
compare URIs (or drop the stale spelling's cache key); rejecting a
symlink-resolving `resolve()` in the save path is a design decision for the
plan, not this review.

### [minor] 3 — close landing inside an in-flight open

`manager.py:371-403`: `_opening` prevents duplicate didOpen but a
`on_document_closed` completing during `await ensure_client` can be followed
by the opener writing a ghost `_open` entry and sending didOpen. Reproduced;
downgraded from major because the window is narrow, no data is lost and it is
a boundary of the plan-b design rather than a regression.

### [minor] 4 — three uncovered added lines

`manager.py:364` (shown without path), `:387-388` (didOpen notify failure),
`:445` (retarget without path) have no tests. Full-suite coverage still meets
the 75 threshold.

### [minor] 5 — line-count headroom

`manager.py` is at 783/800 lines; any later method addition would trip
`test_source_files_within_size_threshold` unless the file is split or exempted.

### [minor] 6 — missing multi-argument `:enew` case

`tests/test_cmd_enew.py:83-100` covers a filename and a quoted filename, but
not `:enew a.py b.py`. The guard itself is correct (`CommandFunc` takes one
`args: str`), so only a regression case is missing.

## 3. Self-critique registration

| # | Initial | Outcome |
|---|---|---|
| 1 | major | confirmed (re-read lines, two-way runtime proof) |
| 2 | major | confirmed (re-read lines, Path vs URI proof) |
| 3 | draft major | downgraded to minor (narrow await window, no crash/data loss, plan-b design boundary) |
| 4 | minor | confirmed (targeted coverage re-run) |
| 5 | minor | confirmed (measured 783 lines) |
| 6 | minor | confirmed (signature checked) |

Deleted as false positives: "`_close_uri` changed statement order/log text"
(byte-compared with the base version), "`_opening` leaks after
cancel/shutdown" (measured set empty), "`_refresh_ui()` has side effects"
(injected callable, unmounted no-op, same tail as `save_document`),
"`doc_shown_later` races the retarget into duplicate didOpen" (measured one
didOpen), "missing `@override` / NameError in new tests" (pyright 0, tests
green), "manuals out of sync" (four key strings present in both languages),
"`states()`/`configs()` semantics changed" (unchanged).

Reviewer noted a workspace-discipline deviation: three temporary capture
files (`cov.txt`, `old_mgr.txt`, `smoke.txt`) were created during the review
and deleted before the final `git status --short` (empty). No product, test,
document, plan or baseline file was modified by the reviewer.

## 4. Plan-conformance checks

All wave-1/2 implementations match their sub-plans verbatim: `:enew` warning
text and registration description, `state_for_doc` path gate, `_close_uri`
extraction, `on_document_retargeted` signature/branches, `previous_path`
capture and spawn placement, `_refresh_ui()` tail, bilingual manual pairs,
single smoke check and exactly one baseline change. The plan-c test #4
`cast(Any, fx.flows)._submit_save_as(...)` deviation is verified and justified
by pyright strict; the plan-d full `run --jobs 4` deferral was executed by
this review (121/121). All six commits use the `type(scope): subject` format.
The two majors are **plan design gaps** (URI identity / URI ownership were
undefined), not implementation deviations; they were fed back into step 2 as
[`../documents/iksfs7-plans/iksfs7-review-fixes-plan-e.md`](../documents/iksfs7-plans/iksfs7-review-fixes-plan-e.md).
