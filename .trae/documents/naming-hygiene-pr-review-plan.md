# Naming hygiene merge-ready PR review fixes plan

来源评审记录：[2026-11-07-pr-review-naming-hygiene.md](../reviews/2026-11-07-pr-review-naming-hygiene.md)
（合并前 PR 级预评审，`review` 模式，3 只读审查员并行 + 主代理逐条回读复核）。
来源方案：[iktbxc-plan.md](iktbxc-plan.md)、
[iktbxc-review-fixes-plan.md](iktbxc-review-fixes-plan.md)、
[iktbxc-plans/overview.md](iktbxc-plans/overview.md)。
无人值守会话：批准视为已通过，不询问；本计划是迭代波的唯一规范来源。

## 1. Scope and baseline (read-only evidence)

| Item | Measured value |
|---|---|
| merge-base / PR HEAD / master | `3e92532` / `38a918b` / `d53d238` |
| master lead | 47 commits ahead of merge-base |
| PR diff | 48 files changed, 1641 insertions(+), 65 deletions(-) |
| worktree / branch | `yate-naming-hygiene` / `ref/naming-hygiene` |
| sandbox | `.venv/Scripts/python.exe` resolves `yate/__init__.py` inside this worktree |
| overlap with master-modified files | `.trae/reviews/README.md`, `.trae/rules/architecture-boundaries.md` |
| `git merge-tree 3e92532 master HEAD` | exactly 1 conflict marker pair, both in `.trae/reviews/README.md` prose; the layer-rules file auto-merges |
| `git diff --check 3e92532..HEAD` | exit 2: `iktbxc-plan.md:300: new blank line at EOF` |
| untracked probe artefacts | `base_cf.txt`, `base_disp.txt`, `base_ed.txt`, `base_mouse.txt`, `base_term.txt`, `base_to.txt` (6 files, from PR-review reconnaissance) |

Three implementation blobs remain byte-equivalent to their pre-change sources
(reviewer A/C independently confirmed); no runtime behaviour change in the
rename waves.

## 2. Main-agent adjudication (final severity)

| # | Finding | Source | Adjudication | Final | Disposition |
|---|---|---|---|---|---|
| F1 | `.trae/reviews/README.md` index #59 collides with master #59/#60/#61 and the prose insertion is a real 3-way merge conflict | B BLOCKER; C MAJOR; A MINOR | Collision + conflict confirmed by `git merge-tree`. Downgraded from BLOCKER: a Markdown index conflict is neither a security issue, architecture violation, red hard gate nor a crash, so the skill's BLOCKER definition does not apply. It is merge-blocking documentation damage, hence MAJOR. | MAJOR | Renumber branch entries to #62 (first review) and #63 (pr-review); add a numbered-divergence note; relocate the branch prose so the conflict disappears; re-run `git merge-tree` |
| F2 | drive-letter absolute paths in newly added documents (`iktbxc-plan.md:8`, `:275`; review record `:122`) | B/C MAJOR | Confirmed: 3 hits in PR-added lines. `doc-conventions.md` §五/§六 forbids them; the "legacy documents migrate gradually" clause does not excuse new violations. | MAJOR | Replace with worktree-relative / portable wording |
| F3 | review record scope and conclusion distortion (`44 files/+1139/-65` labelled `3e92532..HEAD`, worktree metadata, import-order claim) | B MAJOR | `44/+1139/-65` is exactly `3e92532..f3299a1` (review-time HEAD), while current HEAD is `48/+1641/-65`; the label is wrong, not the number. §三 import-order row is factually overturned by the mechanical recheck in F6. | MAJOR | Pin the scope to `f3299a1`, note the current HEAD, add a dated correction addendum, de-sensitize the environment line |
| F4 | `yate/editor.py:61` import order regression | A MINOR | Confirmed and expanded: 5 files have a `view` import left at the old `editor` position after the rename. Mechanical evidence: `yate/editor.py`, `yate/editor_dispatch.py`, `yate/flows/completion_flows.py`, `tests/test_app_mouse.py`, `tests/test_panes.py`. | MINOR | Fix all 5 (behaviour-neutral; gate-verified) |
| F5 | `tools/smoke_test/scenarios/stress.py` convergence predicate: discarded `wait_until` return, magic `3`, single-key dict instead of `nonlocal` | C MINOR ×3 | All three confirmed. | MINOR | Fix the magic number and the dict; defer the discarded return value (§5) |
| F6 | 6 untracked PR-review probe files | main agent | Confirmed via `git status --short`. Same delivery-hygiene class as iteration-1 M1. | MINOR | Delete after this plan is on disk; list in closing report |
| F7 | `git diff --check` blank line at EOF | main agent | Confirmed. | MINOR | Remove trailing blank line from `iktbxc-plan.md` |
| F8 | master `task-orchestration.md` now mandates `feature/<fix|feat|enh|ref>-<task>` from `develop`; branch is `ref/naming-hygiene` from `master@3e92532` | A/B MINOR | Confirmed drift. The branch predates the master rule change and was explicitly named by the user on 2026-11-07; renaming again would contradict that instruction. | MINOR (deferred) | Register in §5, no code change |
| F9 | `iktbxc-*` document stem conflicts with the semantic-naming direction | B MINOR | Confirmed. User feedback constrained branch/worktree names, not document names; plan documents follow `<task>-plan.md` with the issue id as `task`, and renaming now would break 9 cross-links. | MINOR (deferred) | Register in §5 |

Baseline verdicts: A `APPROVE` (0/0/1), B `BLOCKED` (1/2/4), C `REQUEST_CHANGES` (0/1/3).
After F1-F3 are zeroed, the final PR-review verdict is **APPROVE**.

## 3. Goals / non-goals

Goals: zero the 3 final MAJOR findings; fix or register every MINOR; re-run the
six hard gates in the PR-review phase; archive the PR-review record and index
it; backfill the plans; keep `git merge-tree` free of conflict markers.

Non-goals: no push; no merge of master into the branch; no rewrite of the three
implementation commits or the first review's findings; no new architecture
guards; no new smoke `Check` (the frozen `1463/1463` baseline stays intact).

## 4. Steps and acceptance commands

1. Persist this plan as a standalone commit (`docs(plan): ...`).
2. F1 + F2 + F3 + F7 + F9: edit `.trae/reviews/README.md`,
   `.trae/reviews/2026-11-07-iktbxc-naming-refactor.md`,
   `.trae/documents/iktbxc-plan.md`,
   `.trae/documents/iktbxc-review-fixes-plan.md`; delete the 6 probe files (F6).
   Acceptance: `git merge-tree 3e92532 master HEAD` reports 0 `<<<<<<<`;
   a targeted grep for drive-letter paths in PR-changed files returns 0 hits;
   `git diff --check 3e92532..HEAD` exits 0; `git status --short` has no `??`.
3. F4: reorder the 5 import pairs; F5: `_SETTLED_POLLS` constant + `nonlocal`
   streak. Acceptance: `pyright yate/ tests/ tools/ pack/` 0 errors;
   `pytest tests/test_architecture.py -q` 37 passed;
   `tools.smoke_test run --scenario stress_rapid_toggles --repeat 5 --jobs 4` 12/12.
4. Archive the PR-review record and index it as #63; commit.
5. Main agent personally runs the six hard gates (all exit 0):
   `pyright yate/ tests/ tools/ pack/`, `pytest tests/ -q -n auto`,
   `pytest tests/test_architecture.py -q`,
   `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`,
   `tools.smoke_test run --jobs 4`, `python -m tools.changelog check`;
   plus `python -m yate --help`, `git diff --check`, residual old-path grep and
   `git status --short`.
6. Backfill §7 below, `iktbxc-plan.md` §9.8 and the review record; commit.
   No step may be pushed (§二 提交纪律).

## 5. Deferred items and deviation register

| Item | Reason |
|---|---|
| F5 discarded `wait_until` return | `wait_until` returns `False` only on timeout, and the existing `Check("toggles_back", before, ...)` already asserts the same convergence failure. Adding a second `Check` would inflate the frozen `1463/1463` smoke baseline and duplicate coverage for a timing-only helper. |
| F8 branch naming drift | Branch created from `master@3e92532` before master introduced the `feature/...`-from-`develop` rule; the semantic name `ref/naming-hygiene` was explicitly chosen by the user on 2026-11-07. Re-registering the branch would also rewrite the documented worktree. |
| F9 `iktbxc-*` document stem | Issue ids are the repo's `<task>` token for plan documents; renaming would break 9 in-repo links and contradict the "read-only historical document" convention. |
| `key_codec.py` first-line "legacy" wording, R11 enumeration drift, package-level `--follow` archaeology | Pre-existing observations from the first review; out of PR-review scope. |
| master-side `.trae/rules/architecture-boundaries.md` and `task-orchestration.md` changes | Auto-mergeable / single-sided; not modified by this branch. |

## 6. Risks and rollback

| Risk | Mitigation |
|---|---|
| Import reordering changes module initialisation order | `terminal.py` / `panes.py` already import `view.py` themselves, so no new cycle; pyright + full pytest + smoke re-run after the edit |
| README prose relocation loses the increment log | Both reviews remain in the numbered table plus the new divergence note; `git merge-tree` re-checked |
| Deleting probe files removes evidence | They are transient docstring dumps; all evidence is reproduced in the PR-review record |
| Renumbering leaves stale `#59` references | Targeted grep across `.trae/**` and correction of the 4 known sites |

Rollback: each iteration commit can be `git revert`-ed individually; the three
implementation commits and the first review record remain untouched.

## 7. Backfill (filled at closing)

Pending: real gate numbers, commit list, final `merge-tree` result, final
`git status`, and the APPROVE verdict with residual deferred items.
