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
| 3 批准 | waived: the user's standing unattended instruction ("进入无人值守模式，所有问题无须过问") plus this message's "取个有意义的名字" delegate the naming decision; no question/approval is raised (always-applied workspace loader §二.5, unattended bypass — not a `.trae/rules/` clause) |
| 4 执行 | done: §3 (commits `9c90c8d`, `06e6743`; 10 renames detected at 86-96% similarity) |
| 5 审核 | done: round 1 **0 blocker / 4 major / 2 minor** → round 2 **0 blocker / 1 major / 0 minor** (dangling deviation #7) → round 3 **0 blocker / 0 major / 2 minor** (both non-blocking wording/count notes); all three read-only consistency reviews under the `misc-rules.md` §三 pure-document exemption |
| 6 迭代 | done: §6 iteration design (`4ea44fc`), M1/M2/M3 fixes (`1123856`), §4 deviation #7/#8 backfill (`9d3721b`) |
| 7 收尾 | done: §4 measured results backfilled, round-3 verdict recorded, per-step commits, `git status --short` empty, no push |

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
- No commit-message rewrite. The 12 existing subjects are descriptive and all
  follow `type(scope): subject`, but **6 of them still cite the issue id in the
  subject line** (`7011ff2`, `68a1ada`, `2c6989b`, `20e6b9c`, `6ec91ec`,
  `0619086`). This is a known, accepted deviation (see #9 in §4): subjects are
  immutable here (no amend / rebase), so the issue id survives in history while
  every file name, document title, branch and worktree name uses the
  descriptive stem.
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
| C. Delete every `IKSFS7` token, including the issue URL and prose citations | Loses provenance and breaks the repository convention of citing issues by id (`issue IKRZ41`, `issue IKSFMQ`…). Only **names and titles** are renamed; the URL and prose citations stay. Review-index paragraph headings count as **names/titles** and therefore use the task name; the issue id is kept only in the Gitee URL at the top of the issue notes and the main plan. |
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
`doc-conventions.md` §五 requires portable wording, so that **single evidence
line** becomes "the worktree-local `yate` package". The promise is deliberately
scoped to that line: this plan must still name the old/new worktree directories
(rename map, measured output evidence and the executable §6 commands), which
are the migration's own target artifacts rather than references to repository
files. See [the pr-review iteration design](enew-args-lsp-attach-pr-review-plan.md)
for the standing ruling on that distinction.

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
# Lowercase token scan (case-sensitive; exclude this plan's rename map):
Get-ChildItem .trae,tests -Recurse -Include *.md,*.py | Where-Object { $_.Name -ne 'enew-args-lsp-attach-naming-plan.md' } | ForEach-Object { Select-String -Path $_.FullName -Pattern 'iksfs7' -CaseSensitive }
# Scoped link check (11 target docs + README; strip '#Lxx' and scheme URLs):
Get-ChildItem .trae -Recurse -Filter *.md | Where-Object { $_.Name -like 'enew-args-lsp-attach*' -or $_.DirectoryName -like '*enew-args-lsp-attach-plans*' -or $_.Name -eq 'README.md' } | ForEach-Object { $f = $_; Select-String -Path $f.FullName -Pattern '\]\(([^)]+)\)' -AllMatches | ForEach-Object { $_.Matches.Groups[1].Value } | Where-Object { $_ -notmatch '^[a-z]+://' -and $_ -notmatch '^#' } | ForEach-Object { $clean = ($_ -split '#')[0]; if ($clean -and -not (Test-Path (Join-Path $f.DirectoryName $clean))) { "MISSING: $($f.Name) -> $_" } } }
.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"
```

Pass criteria: branch/worktree names match §2; lowercase `iksfs7` count is 0
**excluding this plan's rename map**, which keeps the old names as migration
evidence (see §2); no `MISSING:` link in the scoped check — a full `.trae` sweep
is not a valid check because historical documents contain `file:///` URLs and
`#Lxx` line fragments; `git diff --check` exit 0; sandbox self-proof prints the
new worktree path. Measured results and the exact scoped command are recorded
in §4. Commit: `docs(plan): rename issue-numbered artifacts to descriptive task name`.

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
| `git worktree move` | `fatal: failed to move ...: Permission denied` (Windows); superseded by `Move-Item` + `repair`, see deviation #1/#3 | 1 (failed by design) |
| `git branch -m` | `git branch --show-current` = `fix/enew-args-lsp-attach`; `git worktree list` shows the new path on that branch; no upstream configured | 0 |
| `pip install -e . --no-deps` + sandbox self-proof | `.pth` = `D:\Programming\yate-enew-args-lsp-attach`; `sys.prefix` = that `.venv`; `import yate` = `...\yate-enew-args-lsp-attach\yate\__init__.py`; `pip show yate` editable location matches | 0 |
| lowercase `iksfs7` token count after replacement | **0** in `.trae` + `tests` excluding this plan's rename map (`Get-ChildItem ... -CaseSensitive`); `git grep -n 'iksfs7'` excluding this plan = no match; uppercase `IKSFS7` = exactly 2 Gitee URLs | 0 (grep: 1 = no match) |
| relative-link check | **0 `MISSING`** with the scoped §3 step 3 command (141 links in that口径); round-1's 11-document口径 also 0/40 | 0 |
| `git diff --check` | empty (no whitespace errors / conflict markers) | 0 |
| `git status --short` at close | empty after every per-step commit; re-run in the step-7 final gate | 0 |
| `git diff 0619086..HEAD -M --summary` | **10 renames** at 86%-96% similarity + 1 `create mode` (this plan); code diff = 1 line docstring in `tests/test_document_flows_saveas.py` | 0 |
| worktree metadata / venv probes | `.git` `gitdir:` + admin key both use the new name; `git worktree list` / `rev-parse --git-dir` / `prune --dry-run -v` = 0 with no stale or `locked` entry; `.venv` recursive scan of 8244 text files at the time of measurement = **0** `yate-iksfs7` (a later re-scan counted 8248 due to probe-generated `.pyc` files, still 0 hits); `activate.bat` `VIRTUAL_ENV` path exists | 0 |

Deviations (recorded per §5; all with measured evidence):

1. **Native `git worktree move` failed**: `git worktree move ../yate-iksfs7
   ../yate-enew-args-lsp-attach` printed `fatal: failed to move ...: Permission
   denied` on Windows. The design's step-2 command did not complete.
2. **Three follow-up commands ran in the main repo**: because the `cd` into the
   not-yet-created worktree failed, `git branch -m fix/enew-args-lsp-attach`
   renamed the **main repo's `master`** to that name, and
   `pip install -e . --no-deps` reinstalled the main repo's editable package.
   Recovery evidence: `git branch -m master` restored the main repo
   (`git branch --show-current` = `master`, `git reflog show master` shows a
   matched rename-out/rename-back pair, `git status --short` empty,
   `git worktree list` shows `D:/Programming/yate [master]`); main repo
   `import yate` resolves to `D:\Programming\yate\yate\__init__.py` and its
   editable `.pth` points at `D:\Programming\yate`, so no residual damage.
3. **Worktree move method changed**: `Move-Item -Path yate-iksfs7
   -Destination yate-enew-args-lsp-attach` + `git worktree repair` from the
   moved worktree. `repair` printed `repair: gitdir incorrect: ...` and rewrote
   the `gitdir` pointer; `git worktree list` then showed
   `D:/Programming/yate-enew-args-lsp-attach [fix/iksfs7]` (branch still old at
   that moment). `git branch -m` was then re-run **from inside the worktree**,
   yielding `[fix/enew-args-lsp-attach]`; no upstream is configured.
4. **Editable install refreshed twice**: once accidentally in the main repo
   (see #2), then correctly in the moved worktree with
   `pip install -e . --no-deps`; self-proof `import yate` resolved to
   `D:\Programming\yate-enew-args-lsp-attach\yate\__init__.py` (exit 0).
5. **Portable-wording promise only partially delivered in `06e6743`**: step-2
   design promised "the worktree-local `yate` package" but the first pass
   substituted `../../yate/__init__.py`, a relative path that still assumes the
   worktree sits beside the main repo. Fixed in the §6 iteration wave.
6. **Full-sweep checks were not usable**: the original token/link commands in
   §3 step 3 produce false positives (this plan's rename map; historical
   `file:///` and `#Lxx` links). The scoped, measured commands now written in
   §3 step 3 were used instead (see §4 table and review round 1 item 11).
7. **Iteration wave was environment-only and initially unrecorded**: M1
   renamed the main repo's git admin key `.git/worktrees/yate-iksfs7` to
   `yate-enew-args-lsp-attach` (bracketed by `git worktree lock` / `unlock`),
   and M2 rewrote the four venv text files that carried the token
   (`activate`, `activate.bat`, `activate.fish`, `pyvenv.cfg`) in place out of
   five candidates checked (`Activate.ps1` carried no hit). Neither
   produces a tracked diff or a commit — `.venv` is gitignored and `.git`
   metadata is machine-local — so `git status --short` stayed empty.
   `git worktree repair` **first returned exit 1** with `error: unable to
   locate repository; .git file does not reference a repository` while still
   rewriting the worktree `.git` pointer; a second `repair` returned exit 0.
   Verified: `.git` = `gitdir: .../worktrees/yate-enew-args-lsp-attach`, old
   admin key absent, `git status` / `worktree list` / `rev-parse --git-dir` /
   `prune --dry-run -v` all exit 0 with no stale or `locked` residue, `.venv`
   recursive residual 0, sandbox self-proof still resolves the worktree.
   Round 2 flagged the missing #7 as its single major; this entry closes it.
8. **Self-proof measurement scope**: running `.venv\Scripts\python.exe -c
   "import yate; ..."` from the main repo cwd prints the main repo's
   `yate\__init__.py` because `sys.path[0]` shadows the editable install;
   from the worktree root it prints the worktree package. This is a
   measurement-scope issue, not a sandbox defect, so the §3 step 3 self-proof
   command must be run from the worktree root.
9. **Issue id remains in 6 commit subjects**: the naming migration renamed the
   branch, worktree, 10 documents, review-index headings and one test docstring,
   but did not rewrite history. `git log --format=%s 8e60598..9c90c8d` shows 6 of
   12 subjects still cite `IKSFS7` (`7011ff2`, `68a1ada`, `2c6989b`, `20e6b9c`,
   `6ec91ec`, `0619086`). §1 originally asserted the opposite ("contain no
   issue-number name"); the 2026-11-07 pre-merge PR review confirmed the mismatch
   and §1 is now corrected with the measured hashes. Rationale: subjects are
   immutable under the no-history-rewrite constraint, so the issue id survives
   only in commit history while every name/title/file uses the descriptive stem.

Review round 1 (0 blocker / 4 major / 2 minor) found two environment/metadata
residuals and one wording deviation; all were fixed in the §6 iteration wave
and recorded in #5, #7 and #8. Review round 2 (0 blocker / 1 major / 0 minor)
found the dangling "deviation #7" promise; the backfill added #7/#8. Review
round 3 (0 blocker / 0 major / 2 minor) confirmed the closure; its two minors
were wording/count clarifications and are folded into the closing commit (#7
now states "4 of 5 candidates", and the `.venv` scan count carries a
measurement-time qualifier). Pyright / pytest / architecture / coverage /
smoke were not run at any round (`misc-rules.md` §三 pure-document exemption).
The later [pre-merge PR review](../reviews/2026-11-07-pr-review-fix-enew-args-lsp-attach.md)
of the combined branch (which includes product code) lifted that exemption and
ran the full six gates.

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

## 6. Iteration design (review round 1 → round 2)

Trigger: the step-5 read-only consistency review returned
**0 blocker / 4 major / 2 minor** (M1-M4, m5-m6). Per
`task-orchestration.md` §二.6 the loop goes back to step 2; this section is
that step-2 redesign. Approval is covered by the standing unattended
instruction, so no question or authorization request is raised (always-applied
workspace loader §二.5, unattended bypass — not a `.trae/rules/` clause). No
new worktree/branch, no product code, no history rewrite and no push are
involved.

| ID | Finding | Root cause | Fix design | Acceptance |
|---|---|---|---|---|
| M1 | git admin key `.git/worktrees/yate-iksfs7` and the worktree `.git` `gitdir:` value still carry the old name | native `git worktree move` failed on Windows; `Move-Item` + `git worktree repair` fixed the `gitdir` *contents* but not the registration key name | from the main repo: `git worktree lock`, rename the admin directory to `yate-enew-args-lsp-attach`, `git worktree repair <worktree>`, `git worktree unlock`; rewrite the worktree `.git` pointer only if `repair` does not | no `iksfs7` in `Get-ChildItem .git/worktrees` or in the worktree `.git` file; `git status --short`, `git worktree list`, `git rev-parse --git-dir`, `git worktree prune --dry-run -v` all exit 0 with no stale entry |
| M2 | `.venv/Scripts/activate*`, `.venv/pyvenv.cfg` still contain `yate-iksfs7` | step-2 design only refreshed the editable `.pth` (`pip install -e . --no-deps`) | in-place text replacement `yate-iksfs7` → `yate-enew-args-lsp-attach` in the activation scripts that hit plus `pyvenv.cfg`; no reinstall, no dependency download, no commit (gitignored machine-local data) | recursive `.venv` residual scan = 0; the `VIRTUAL_ENV` path in `activate.bat` exists; sandbox self-proof still resolves the new worktree |
| M3 | `.trae/documents/enew-args-lsp-attach-plan.md:11` self-proof says `../../yate/__init__.py` | first pass substituted a relative path instead of the portable wording promised in §2 | use the §2 wording verbatim: "the worktree-local `yate` package" | `git grep -n '../../yate/__init__.py'` returns no match; the line no longer assumes a sibling-directory layout |
| M4 | §4 `Deviations: none recorded yet.` contradicted known deviations | step-7 backfill had not started when round 1 ran | rewritten in §4 as an 8-item, evidence-backed deviation list (#7/#8 added after round 2); the §4 result table is filled with measured values at step 7 | at close, no `pending` row and no "none recorded" assertion remain |
| m5 | §3 step 3 token/link commands were not executable as written | full-sweep口径 produces false positives (this plan's own rename map, historical `file:///` / `#Lxx` links) | §3 step 3 now has a case-sensitive lowercase scan excluding this plan and a scoped link check; §4 records the measured commands | both commands exit 0 with 0 hits / 0 `MISSING:` |
| m6 | review-index heading ruling boundary was implicit | §2 rejected alternative C covered URL/prose only | §2 C now states review-index paragraph headings are names/titles and the issue id survives only in the two Gitee URLs | round-2 review confirms no repository file uses the issue number as a name/title |

### Iteration-wave commands (step 6)

```powershell
# M1 — main repo metadata (environment-only, not committed)
$main = 'D:/Programming/yate'
$wt = 'D:/Programming/yate-enew-args-lsp-attach'
git -C $main worktree lock $wt
Rename-Item -LiteralPath "$main/.git/worktrees/yate-iksfs7" -NewName 'yate-enew-args-lsp-attach'
git -C $main worktree repair $wt
git -C $main worktree unlock $wt
Get-Content "$wt/.git"
git -C $wt status --short
git -C $wt rev-parse --git-dir
git -C $wt worktree list
git -C $main worktree prune --dry-run -v

# M2 — venv text files (environment-only, not committed)
$root = 'D:/Programming/yate-enew-args-lsp-attach'
$files = @("$root/.venv/Scripts/activate", "$root/.venv/Scripts/activate.bat",
           "$root/.venv/Scripts/activate.fish", "$root/.venv/Scripts/Activate.ps1",
           "$root/.venv/pyvenv.cfg")
foreach ($f in $files) {
    if (Test-Path -LiteralPath $f) {
        $t = [System.IO.File]::ReadAllText($f)
        if ($t.Contains('yate-iksfs7')) {
            [System.IO.File]::WriteAllText($f, $t.Replace('yate-iksfs7', 'yate-enew-args-lsp-attach'))
        }
    }
}

# M3 — tracked document (committed as the step-6 product)
# replace ../../yate/__init__.py with the §2 portable wording in the main plan §0
```

### Decisions and scope

- M1/M2 are **environment-only** fixes. They produce no tracked diff and no
  commit; they are logged as deviations #7/#8 in §4 with the measured evidence.
  The `git` metadata write is the exact operation round 1 asked for; the
  standing unattended instruction supplies the approval that round 1 wanted
  to request.
- Review verdicts for this naming migration are recorded **inline in this
  plan** (§0 process state, §4 execution record, §6), not as new
  `.trae/reviews/` records: records #59/#60 already are this task's review
  records, and this wave changes names only. `doc-conventions.md` §二.1
  governs the naming *if* a record is created; it does not mandate one, and
  the review index therefore needs no new entry.
- Gate: pure document/metadata change, so `misc-rules.md` §三 waives
  pyright / pytest / architecture / coverage / smoke. The executable checks
  in §3 step 3 plus the M1/M2 probes are the gate; round 2 is a read-only
  consistency review whose conclusion carries measured results and exit
  codes. Round 2 is dispatched to `code-review-expert`
  (`.trae/agents/code-review-expert.md`) with the pure-document exemption
  stated in the task book; a failed spawn is handled by the §三 main-agent
  fallback and reported as "子代理零产出".
- Step-7 product: §4 result table backfilled with real numbers, §0 state
  table closed, per-step commits, `git status --short` empty, no push.

### Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Renaming the git admin directory makes the worktree unusable | lock first; keep the old name available; repair before any other git write; verify four git commands before unlocking | rename the admin directory back to `yate-iksfs7`, restore the `.git` `gitdir:` line, run `git worktree repair`, unlock |
| `git worktree repair` rewrites the wrong pointer | read back the `.git` file and `gitdir` contents after repair; only then continue | restore the exact original `.git` line recorded in §4 before iterating |
| In-place venv replacement corrupts encoding / line endings | raw text read+write with `[System.IO.File]`, replace a single ASCII token; verify the residual count and `import yate` afterwards | replace the new token back; the files are regenerable with `python -m venv` + `pip install -e ".[dev]"` |
| Round-2 review returns new majors | stay in the loop (§二.6), extend this section | no rollback needed; design is additive |
