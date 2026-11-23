# 2026-11-23 pr-review — feature/enh-lsp-navigation (IKX5EP)

Scope: merge-base `c6d6e89a7d5866ee98577a633211b0abf6ea2098` → HEAD
`9b6f6471`; 12 commits / 38 files +5011 −21 (branch and master unforked).
Mode: `review` (full six dimensions + hard gates). Two read-only
`code-review-expert` reviewers (functionality/security/performance and
architecture/maintainability/docs/merge-readiness) + main-agent evidence
re-check of every finding. `python-code-review` skill is not registered in
this environment, so reviewers fell back to their role-file checklist.

## Overall: REQUEST_CHANGES (baseline) → APPROVE (post-fix)

Baseline: 6 MAJOR / 8 MINOR, 0 BLOCKER. All MAJOR closed this round; 1 MINOR
(`positionEncoding` not negotiated in the pre-existing `client.py`, outside
this PR's diff) registered as a follow-up; the remaining MINORs were fixed or
explicitly registered. No hard gate was red at baseline.

## Findings and disposition

### MAJOR — fixed

1. `yate/flows/lsp_navigation_flows.py:517-528` — rename on a locked
   (chunked) or read-only buffer reported false success. `TextBuffer.
   replace_range` silently no-ops when `locked=True`, but `applied += len(edits)`
   ran regardless, producing `Renamed N occurrence(s)` although nothing changed.
   **Fix**: `_check_edit_range` now rejects `buf.locked` / `buf.read_only` /
   inverted ranges; `_apply_workspace_edit` split into two phases — a
   side-effect-free pre-validation pass (rejection warns and returns, no
   rollback needed) followed by apply + rollback. This also avoids a second
   `BufferReadOnlyError` from rolling back a read-only buffer, which had
   masked the original message. Regression: `test_rename_locked_buffer_...`,
   `test_rename_read_only_buffer_...` (red before fix, green after).

2. `yate/editor_lsp/navigation.py:247-249` — `parse_locations` accepted a
   dict with a `uri` but no `range`/`targetRange`; `_range_from(None)` returned
   `(0,0,0,0)`, which the flow treated as a real definition and jumped to the
   file's first line. **Fix**: skip entries whose range is not a dict.
   Regression: `test_parse_locations_skips_entries_without_a_range`.

3. `yate/docs/lsp.en.md:38` / `lsp.zh.md:29` — documented `K` as vim-only,
   but runtime probe shows both `VscKeymap` and `VimKeymap` resolve
   `<shift-k>` to `show_hover_docs` (`HOVER_POPUP_KEY`). `manual.{en,zh}.md`
   §16 key tables listed `F7` only in the vsc column. **Fix**: all four docs
   now state `K` (vsc `Shift+K`) works in both keymaps.

4. `.trae/rules/architecture-boundaries.md:23-28` — §一 L3 flows enumeration
   omitted `lsp_navigation_flows.py` although §三.8 step 6 requires syncing it
   (the module appears only in R11 / §六). **Fix**: added to §一 L3 list.

5. `.trae/documents/lsp-navigation-plans/lsp-navigation-guards-docs-plan-e.md:100-111`
   — R11 says the wave-4 registration was "recorded in the plan", but the
   execution record only logged the smoke-tag deviation. **Fix**: added a
   deviation entry documenting the import-before-registration sequencing and
   the final `UI_FROZEN_FILES` four-module surface.

6. `.trae/reviews/2026-11-22-lsp-navigation.md:3-4` — scope line stated 33
   files / +4375 −19 while the post-fix terminal state is 38 / +5011 −21.
   **Fix**: scope line now labels review-time vs post-fix numbers with the
   re-measure commit.

### MINOR — fixed

- `yate/editor_lsp/navigation.py:485` — `activeParameter` was read only from
  the `SignatureHelp` envelope; servers reporting it per-`SignatureInformation`
  highlighted the wrong argument. Now prefers the selected signature's value
  and clamps negatives to 0. Two regression tests added.
- `.trae/documents/lsp-navigation-plan.md:4`,
  `lsp-navigation-request-layer-plan-a.md:109`, `2026-11-22-lsp-navigation.md:3`
  — machine-local worktree paths replaced with relative placeholders.
- `.trae/reviews/README.md` — registered this review as #80 (branch-local).
- `yate/resources/manual.{en,zh}.md` §16 key tables — vsc `K` column fixed.

### MINOR — registered (not blocking)

- `yate/editor_lsp/client.py:602-641` (pre-existing, outside this diff) does
  not declare `general.positionEncodings: ["utf-16"]`; the whole UTF-16 column
  conversion chain assumes the LSP 3.17 default. A server returning `utf-8`
  would silently misalign non-ASCII columns. Follow-up issue: negotiate the
  encoding explicitly or degrade navigation to unsupported on mismatch.
- `yate/flows/lsp_navigation_flows.py` — 7 repeated `has_modal_screen()` guards
  (extract a predicate in a later cleanup); `buf.anchor = None` could use
  `clear_selection()`; LSP jumps do not push to the jumplist;
  `navigation.request(client: Any)` keeps an explicit duck-typing `noqa`.
- Untracked root file named `'` remains from a pre-review PowerShell quoting
  accident; it is not staged and should be deleted before merge.

### Withdrawn after evidence

- Reviewer B's "vsc binds only `F7`, not `K`" was itself the defect (docs were
  wrong); the runtime probe settled the direction.
- Reviewer A's `_check_edit_range` inverted-range claim was initially doubted,
  then confirmed by reading `_delete_range` (raises after earlier edits) —
  folded into the MAJOR-1 fix.
- Reviewer B's "R15 scrollbar missing in `lsp_chooser`" and "R10 duplicate
  binding" were withdrawn: base-class wiring and distinct raw keys confirmed.

## Hard gates (main agent, post-fix, real exit codes)

| Gate | Result | Exit |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors | 0 |
| `pytest tests/ -q -n auto` (4046 tests, 4036 passed, 10 skipped) | all green | 0 |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 92.74% (≥75), 4036 passed / 10 skipped; 1 earlier parallel flake in `test_app_find_replace.py` re-run `-n 1` → pass | 0 |
| `tools.smoke_test run --jobs 4` | 128/128 scenarios, 1554/1554 checks | 0 |
| `tools.changelog check` | released up to date; unreleased lag is generator mechanism | 0 |
| `git diff --check c6d6e89a...HEAD` | no whitespace errors | 0 |

Note: `pytest tests/test_architecture.py` reported exit 1 in one invocation
because the machine's safe-delete hook intercepted `%TEMP%` bulk cleanup at
test teardown (all 47 tests printed `PASSED`); not a test failure. Coverage's
single parallel failure (`test_app_find_replace.py`) was likewise a timing
flake and passed on serial re-run. The first smoke run reported 127/128 with
one failing check; an immediate re-run gave 128/128 / 1554 checks exit 0.
All three are load-sensitive environment artifacts, recorded per repo rules;
the authoritative post-fix results above are the passing runs.

## Second-round pr-review (2026-11-23, `e018cb1c..f1c4e8b4`)

A second reviewer re-audited the two fix commits. Baseline: REQUEST_CHANGES
with 2 MAJOR / 4 MINOR. A negative drill (porting the new tests onto the
pre-fix `9b6f6471` in a throwaway worktree) turned all five behavior cases
red, confirming the tests are not tautological.

- MAJOR (fixed) — `navigation.py:249-253`: the first-round guard only checked
  that `range` was a dict; a partial range (`{"start": ...}` or `{"end": ...}`)
  still made `_pos_from(None)` fabricate `(0,0)`, restoring the ghost jump.
  Guard now requires both `start` and `end` to be dicts; regression
  `test_parse_locations_skips_ranges_missing_an_endpoint` added.
- MAJOR (fixed) — this report and `.trae/reviews/README.md` #80 quoted
  pre-fix gate numbers (4029 passed / 92.81%). Updated to final-state
  measurements (incl. the two new second-round cases): 4046 tests /
  4036 passed / 10 skipped, 92.74%.
- MINOR (fixed) — `lsp_navigation_flows.py:521-529`: pre-validation failures
  omitted the offending filename while other branches include `path.name`;
  the Phase-1 wrapper now appends `(<file>)`. Added
  `test_rename_multi_doc_prevalidation_is_atomic` locking in the zero-side-
  effect contract for a multi-document edit with an unwritable target.
- MINOR (registered, not in this PR) — rollback via `replace_range` leaves one
  undo entry; present before this PR, harmless (content matches original),
  clarified by the Phase-1/PHASE-2 docstring split.
- MINOR (registered, master baseline) — smoke `stress_rapid_toggles` is load-
  sensitive at `--jobs 4` (127/128) and green at `--jobs 1`; unrelated to this
  diff and already on the master baseline flake list.

## Strengths

- Capability degradation distinguishes `no-ready-server` from `unsupported`,
  with explicit user messages and unchanged buffers.
- WorkspaceEdit pre-validation + snapshot rollback, now hardened against
  locked/read-only/inverted ranges; newly opened files disclosed as unsaved.
- URI caching with invalidation, O(1) diagnostics lookup, async request
  cancellation keyed on doc identity/path/cursor — no hot-path regressions.
- 47 architecture guards (up from 46) cover the new flows module and both
  keymaps' shared navigation keys; bilingual docs and smoke tag in sync.
