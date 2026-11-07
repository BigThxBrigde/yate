# Descriptive naming migration plan — `enew-args-lsp-attach`

Issue: <https://gitee.com/jermaine/yate/issues/IKSFS7> (kept as the provenance
link; the issue number is **not** used as a name any more).
Worktree before: `../yate-iksfs7` · branch before: `fix/iksfs7`.

## 0. Classification and process state

Continuation task (no new worktree/branch per `task-orchestration.md` §二.1:
`git worktree list` shows the existing worktree and its `.venv` is reused).
It is non-trivial (≥3 files, `plan-before-execute.md` §一.1) so the closed loop
applies; it is a **pure document/rename change**, so `misc-rules.md` §三 waives
the test gate (pyright / pytest / coverage / smoke) — but not the rule loading,
naming, relative-path, commit-format and honest-reporting requirements.

| Step | State |
|---|---|
| 1 领会 | done: 8 rules reloaded, `git worktree list` / branch / status probed, all `iksfs7` tokens collected |
| 2 方案 | done: this document |
| 3 批准 | waived: the user's standing unattended instruction ("进入无人值守模式，所有问题无须过问") plus this message's "取个有意义的名字" delegate the naming decision; no question/approval is raised (workspace rule §二.5) |
| 4 执行 | pending: §3 |
| 5 审核 | pending: read-only consistency review (§3.4) |
| 6 迭代 | pending: blocker/major → back to §2 |
| 7 收尾 | pending: backfill §4, per-step commits, no push |

Sub-agents: not dispatched for the mechanical rename because the files are
**not independently verifiable** — every document's links depend on the other
documents' new names, so the `subagent-workflow.md` §一.1 "disjoint files and
independent verification" split criterion is not met. The main agent executes
atomically (§三 fallback).

## 1. Goals / non-goals

Goals:

1. Rename the branch to `fix/enew-args-lsp-attach` and the worktree directory to
   `../yate-enew-args-lsp-attach`, so the local sandbox path is descriptive too.
2. Rename all plan / issue-notes / sub-plan / review documents to
   `doc-conventions.md` §一/§二 compliant descriptive names built on the same
   task stem `enew-args-lsp-attach`.
3. Rewrite every in-repo reference (relative links, branch/worktree mentions,
   review index entries, the one test docstring) so no dangling link remains.
4. Keep the sandbox self-proving after the worktree move, and keep git history
   intact (12 commits, no amend / rebase / force).

Non-goals:

- No product code, test, manual, baseline or rule change other than the single
  docstring token in `tests/test_document_flows_saveas.py`.
- No commit-message rewrite (the 12 existing subjects are already descriptive
  and contain no issue-number name).
- No `git push`, no merge.
- No removal of the Gitee issue URL or the `IKSFS7` issue number where it is
  used **as a source citation** inside prose (see §2 rejected alternative C).

## 2. Naming decision, alternatives and rejection reasons

Chosen stem: `enew-args-lsp-attach` — it names both user-visible fixes of the
issue (`:enew` argument guard and LSP attach for unnamed buffers after
`:saveas`) in lowercase hyphenated ASCII (`doc-conventions.md` §一, §六).

| Rejected | Reason |
|---|---|
| A. `unnamed-buffer-lsp` / `enew-arg-guard` (single-symptom names) | Each covers only half of the delivered change; the branch and documents must describe the whole task. |
| B. `issue-IKSFS7` / `iksfs7-*` with a descriptive subtitle | The user explicitly rejects the issue number as a name; a subtitle does not fix the file/branch name. |
| C. Delete every `IKSFS7` token, including the issue URL and prose citations | Loses provenance and breaks the repository convention of citing issues by id (`issue IKRZ41`, `issue IKSFMQ`…). Only **names and titles** are renamed; the URL and prose citations stay. |
| D. Keep `../yate-iksfs7` as the sandbox directory | Leaves a meaningless local name and makes the worktree path in the documents inconsistent with the branch name; `git worktree move` is a native, reversible operation. |
| E. `git push` the renamed branch | Closed loop forbids pushing (§二 提交纪律); the user did not ask for it. |

### Exact rename map

| Old | New |
|---|---|
| `fix/iksfs7` | `fix/enew-args-lsp-attach` |
| `../yate-iksfs7` | `../yate-enew-args-lsp-attach` |
| `iksfs7-issue-notes.md` | `enew-args-lsp-attach-issue-notes.md` |
| `iksfs7-plan.md` | `enew-args-lsp-attach-plan.md` |
| `iksfs7-plans/` | `enew-args-lsp-attach-plans/` |
| `iksfs7-enew-args-plan-a.md` | `enew-args-lsp-attach-guard-plan-a.md` |
| `iksfs7-lsp-state-plan-b.md` | `enew-args-lsp-attach-state-plan-b.md` |
| `iksfs7-saveas-attach-plan-c.md` | `enew-args-lsp-attach-saveas-plan-c.md` |
| `iksfs7-docs-smoke-plan-d.md` | `enew-args-lsp-attach-docs-plan-d.md` |
| `iksfs7-review-fixes-plan-e.md` | `enew-args-lsp-attach-review-plan-e.md` |
| `2026-11-06-iksfs7-review-round1.md` | `2026-11-06-enew-args-lsp-attach-review.md` |
| `2026-11-06-iksfs7-review-round2.md` | `2026-11-06-enew-args-lsp-attach-iteration-review.md` |

Review-record names follow `doc-conventions.md` §二.1 (`YYYY-MM-DD-<topic>.md`,
same-day reviews distinguished by topic, not `-2`/`-v2` suffixes). Sub-plan
names keep `<task>-<subtask>-plan-<letter>.md`; the directory remains
`<task>-plans/` with `overview.md`.

Document titles become descriptive: `Unnamed-buffer LSP attach fix plan — …`,
`Issue source notes — …`, `… sub-plan overview — …`, `plan-a — …` etc., and the
review records / review-index paragraphs use the descriptive task phrase. The
machine-local memory file `project_iksfs7_status.md` is renamed to
`project_enew_args_lsp_attach_status.md` and its `MEMORY.md` index line is
updated (machine-local data, not a repository commit).

One environment leak is removed while the line is touched: the sandbox
self-proof in the main plan currently embeds `D:\Programming\yate-iksfs7\...`;
`doc-conventions.md` §五 requires portable wording, so it becomes
"the worktree-local `yate` package".

## 3. Implementation steps

### Step 1 — plan (this document)

Input: rule set + token inventory. Output: this file. Acceptance:
`git status --short` shows only this new untracked file; commit
`docs(plan): add naming migration plan for unnamed-buffer LSP attach`.

### Step 2 — branch and worktree

Input: clean worktree. Commands (main repo / worktree):

```powershell
# From the main repository root:
git worktree move ../yate-iksfs7 ../yate-enew-args-lsp-attach
# From the moved worktree root:
git branch -m fix/enew-args-lsp-attach
.venv\Scripts\python.exe -m pip install -e . --no-deps
.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"
```

Output: branch `fix/enew-args-lsp-attach`, worktree
`D:/Programming/yate-enew-args-lsp-attach`, sandbox import pointing at the new
path. Acceptance: `git branch --show-current`, `git worktree list`, and the
self-proof output all match. `pip install -e . --no-deps` refreshes the
editable `.pth` that still points at the old directory; no dependency download.

### Step 3 — documents and references (one atomic commit)

Input: the rename map in §2. Files: 10 `git mv` operations, all `.md` under
`.trae/documents/` and `.trae/reviews/`, `.trae/reviews/README.md`, and
`tests/test_document_flows_saveas.py` (docstring token only).
Implementation: `git mv` + a one-shot Python replacement over the affected
Markdown files (URL protected with a placeholder first, restored last), then
targeted `replace_in_file` edits for titles, index paragraphs, the sandbox
self-proof line and the test docstring.

Acceptance commands (from the new worktree root):

```powershell
git branch --show-current
git worktree list
git status --short
git diff --check
Get-ChildItem .trae -Recurse -Filter *.md | Select-String -Pattern 'iksfs7' | Measure-Object
Get-ChildItem .trae -Recurse -Filter *.md | ForEach-Object { $f = $_; Select-String -Path $f.FullName -Pattern '\]\(([^)]+)\)' -AllMatches | ForEach-Object { $_.Matches.Groups[1].Value } | Where-Object { $_ -notmatch '^https?://' -and $_ -notmatch '^#' } | ForEach-Object { if (-not (Test-Path (Join-Path $f.DirectoryName $_))) { "MISSING: $($f.Name) -> $_" } } }
.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"
```

Pass criteria: branch/worktree names match §2; lowercase `iksfs7` count is 0;
no `MISSING:` link; `git diff --check` exit 0; sandbox self-proof prints the new
worktree path. Commit: `docs(plan): rename issue-numbered artifacts to descriptive task name`.

### Step 4 — review, backfill, close

Input: step-3 diff. Read-only consistency review (naming convention, relative
links, review index #59/#60 entries, git rename detection, no code change).
Pure-document exemption (`misc-rules.md` §三) means no pytest/pyright/coverage/
smoke run; the sandbox self-proof and link/token checks above are the gate.
Backfill §4 with measured results, commit
`docs(plan): backfill naming migration results`, final `git status --short`
empty, no push.

## 4. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| `git worktree move` | pending | — |
| `git branch -m` | pending | — |
| `pip install -e . --no-deps` + sandbox self-proof | pending | — |
| lowercase `iksfs7` token count after replacement | pending | — |
| relative-link check | pending | — |
| `git diff --check` | pending | — |
| `git status --short` at close | pending | — |

Deviations: none recorded yet.

## 5. Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| `git worktree move` fails on Windows file locks | run from the main repo with a clean tree; no process holds the worktree | keep the old directory, revert the two worktree-path lines in the documents, record the deviation |
| Editable install `.pth` still points at the old path | `pip install -e . --no-deps` + self-proof | re-run the install; if it fails, `git worktree move` back and keep the old path lines |
| Branch rename breaks the worktree HEAD or a configured upstream | rename from inside the worktree (`git branch -m`), branch has no upstream (never pushed), verify with `git branch --show-current` | `git branch -m fix/iksfs7` from the worktree |
| A link or index entry is missed | the link-check and token-count commands in §3 step 3 | revert the step-3 commit (git keeps the rename detection), re-apply the missing replacement |
| Over-replacing the issue URL / provenance citations | URL placeholder guard in the replacement script; only lowercase names and titles are rewritten | revert and re-run with the corrected map |
| Memory index drift (machine-local) | rename the memory file and its `MEMORY.md` line in the same step | restore the old file name/index line |

General rollback: `git revert` the two document commits, then
`git branch -m fix/iksfs7` and `git worktree move` back. No history rewrite.
