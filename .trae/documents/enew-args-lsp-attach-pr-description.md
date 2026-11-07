# PR: Reject `:enew` arguments and attach LSP to unnamed buffers on first `:saveas`

**Branch**: `fix/enew-args-lsp-attach` -> `master`
**Status**: ready for merge review; not pushed, no upstream configured, working tree clean
**Range**: `master...HEAD` from merge-base `8e60598`. At `33430c5` this is 22 commits
(11 functional, 6 descriptive-naming migration, 5 pre-merge review) touching
26 files, +3511/-44, including the plan and review records produced by the
pre-merge review. This description itself is the 23rd commit.
**Issue**: [gitee.com/jermaine/yate/issues/IKSFS7](https://gitee.com/jermaine/yate/issues/IKSFS7)

## Summary

Three related defects made unnamed buffers behave inconsistently: `:enew FILE`
silently discarded its argument, the status bar could advertise an LSP server for
a buffer that could never start one, and the first `:saveas FILE` emitted
`didSave` without `didOpen`, so the server never adopted the newly named
document. This PR makes all three paths explicit, pins them with unit and smoke
tests, updates the bilingual manuals and LSP documentation, and renames the
branch, worktree and task documents to a descriptive stem.

## Problem / Motivation

| # | Before | After |
|---|---|---|
| 1 | `:enew FILE` created an unnamed buffer and dropped `FILE` with no feedback | A usage warning is shown and no buffer is created; bare `:enew` is unchanged. |
| 2 | `state_for_doc`, `supports` and `ensure_client` disagreed about pathless buffers; the status bar could show a configured server although no client could start | All three gates require `doc.path is not None`; a pathless buffer reports no LSP server. |
| 3 | The first `:saveas FILE` on an unnamed buffer sent only `didSave`; LSP never attached | The previous path is captured before saving and `on_document_retargeted(doc, previous_path)` is spawned on success, completing `didOpen`. |

## Changes

### Command handling

- `yate/commands.py`: `_enew` rejects any non-whitespace argument with a usage
  warning pointing at `:e FILE` and `:saveas FILE`, and returns without creating
  a buffer.
- `tests/test_cmd_enew.py`: 6 regression tests covering a bare `:enew`,
  whitespace-only arguments, a plain filename, a quoted filename, multiple
  arguments, and the command registration description.

### LSP state and lifecycle

- `yate/editor_lsp/manager.py`: `state_for_doc`, `supports`, `ensure_client` and
  `on_document_shown` now share a single path gate. Added `_close_uri`, an
  `_opening` in-flight set cleared in `finally`, and
  `on_document_retargeted(doc, previous_path)`.
- URI-level identity (`protocol.path_to_uri`) replaces `Path` equality, so
  `a.py` and `sub/../a.py` no longer trigger a redundant `didClose`/`didOpen`
  cycle or split `_uri_cache` keys. If the target URI is owned by another tab,
  the previous owner is closed before the new one is opened. A close arriving
  during an in-flight open wins, leaving no stale `_open` state.
- `manager.py` stays at 797 lines, below the 800-line architecture guard; no new
  module was introduced.
- `tests/test_lsp.py`: pathless-state, concurrent `didOpen`, URI retarget, owner
  conflict and close-during-open cases, including 4 negative drills that fail on
  the old implementation.

### Save-as attach

- `yate/flows/document_flows.py`: `_submit_save_as` captures `previous_path`
  before `doc.save(path)` and spawns the retarget only on the success path. The
  trailing `_refresh_ui()` still covers the normal UI flow, and the read-only
  lock is restored in `finally`.
- `tests/test_document_flows_saveas.py`: success, failure, prompt, same-name and
  repeated-save-as cases.

### Documentation and smoke coverage

- Bilingual manuals and LSP docs (`yate/resources/manual.en.md`,
  `manual.zh.md`, `yate/docs/lsp.en.md`, `lsp.zh.md`) now describe the argument
  guard, the LSP state of pathless buffers and the post-save-as attach behavior.
- `tools/smoke_test/scenarios/aliases.py` adds the `enew_rejects_args` check;
  `tools/smoke_test/smoke_baselines/command_alias_roundup.json` is the only
  regenerated baseline. No other baseline or SVG output changed.

### Descriptive naming

The branch, worktree, 10 plan/review documents, the review-index headings and one
test docstring were renamed from the issue number to `enew-args-lsp-attach`
(10 git-detected renames at 86-96% similarity). The issue id survives only in
the Gitee URL and in six immutable commit subjects; see the
[naming migration plan](enew-args-lsp-attach-naming-plan.md) section 4,
deviation #9. No history rewrite was performed.

## Verification

All six hard gates were run by the main agent on the worktree after the fix
wave. This is a mixed change containing product code, so the pure-document gate
exemption does not apply.

| Gate | Result | Exit |
|---|---|---|
| `python -m pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings (four paths, including `pack/`) | 0 |
| `python -m pytest tests/ -q -n auto` | 3422 passed, 10 skipped | 0 |
| `python -m pytest tests/test_architecture.py -q` | 37 passed | 0 |
| `python -m pytest tests/ --cov=yate --cov-branch -n auto` | 92.90% total; `TOTAL 19425/1093/6206/570 = 93%`; threshold 75% | 0 |
| `python -m tools.smoke_test run --jobs 4` | 121/121 scenarios, 1464/1464 checks | 0 |
| `python -m tools.changelog check` | released sections up to date | 0 |
| `git diff --check master...HEAD` | clean | 0 |

Notes: `pytest -q -n auto` prints no summary line under xdist, so the exit code
is authoritative and the exact counts were recovered with `--junitxml`. The
coverage threshold is single-sourced from `[tool.coverage.report] fail_under`.

## Review history

| Round | Verdict | Outcome |
|---|---|---|
| [#59 first review](../reviews/2026-11-06-enew-args-lsp-attach-review.md) | 0 blocker / 2 major / 4 minor | URI ownership and URI-level equivalence redesigned in wave 3. |
| [#60 iteration review](../reviews/2026-11-06-enew-args-lsp-attach-iteration-review.md) | 0 blocker / 0 major / 2 minor | Both majors closed; 2 minors registered as backlog. |
| [#61 pre-merge PR review](../reviews/2026-11-07-pr-review-fix-enew-args-lsp-attach.md) | 0 blocker / 1 major / 4 minor, then **APPROVE** | One documentation-accuracy major fixed; 2 false positives removed by counter-evidence; remaining items registered as deferred. |

The iteration design and the full counter-evidence table are in the
[pre-merge PR review plan](enew-args-lsp-attach-pr-review-plan.md).

## Known limitations and follow-ups

- Two tabs bound to one path after `:saveas` still share a single LSP URI, so the
  non-owner tab can send `didChange` against the other tab's `OpenDocState`.
  `EditorSession` permits duplicate paths today; forbidding save-as onto an
  already-open path is a product-behavior change for a separate issue.
- When `previous_uri == new_uri` and that URI was never in `_open`, the retarget
  takes the `didSave` branch and stays closed. The normal UI path is covered by
  `_refresh_ui()` leading to `didOpen`; a future fix should fall back to
  `on_document_shown(doc)` and pin it with a test.
- Smoke coverage asserts the buffer count for the `:enew` guard; the exact
  warning text is pinned by unit tests.
- Deferred design trade-offs: single stale `_uri_cache` key cleanup, redundant
  `didClose`/`didOpen` within one client, and worktree target paths retained in
  the migration plan (three consistency-review rulings).

## Merge notes

- No conflict surface: `master` has one commit beyond the merge-base
  (`3e92532`, a plan-document backfill) that touches no file in this PR, and
  `git merge-tree` exits 0.
- No push, no upstream, no rebase/amend/force; the branch is clean at HEAD.
- `CHANGELOG.md` and its translations are refreshed at release time by the
  changelog tool; `changelog check` passes with the expected unreleased lag, and
  no changelog file is part of this diff.
- Internal links in this document resolve from `.trae/documents/`. When pasting
  the body into Gitee, replace them with blob URLs or drop them.

## References

- Issue: [Gitee IKSFS7](https://gitee.com/jermaine/yate/issues/IKSFS7)
- [Main plan](enew-args-lsp-attach-plan.md),
  [sub-plan overview](enew-args-lsp-attach-plans/overview.md),
  [naming migration plan](enew-args-lsp-attach-naming-plan.md),
  [pre-merge PR review plan](enew-args-lsp-attach-pr-review-plan.md)
- Reviews: [#59](../reviews/2026-11-06-enew-args-lsp-attach-review.md),
  [#60](../reviews/2026-11-06-enew-args-lsp-attach-iteration-review.md),
  [#61](../reviews/2026-11-07-pr-review-fix-enew-args-lsp-attach.md)
