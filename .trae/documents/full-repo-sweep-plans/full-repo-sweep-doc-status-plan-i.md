# D2: unify status blocks and remove a local path (plan i)

> **实施状态**：✅ 已实施 —— 2026-11-20（`e6723300`，四份文档状态块统一）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

- `../toggle-comment-plan.md:7-10` exposes a local worktree path (violates `../../rules/doc-conventions.md` §五) and has no unified status block.
- `../macro-record-replay-unified-plans/overview.md:3-4` says repo references use paths relative to the repository root, contradicting `../../rules/doc-conventions.md` §五.
- `../which-key-auto-trigger-plan.md:7`, `../soft-wrap-plans/overview.md:3`, `../macro-record-replay-unified-plan.md:6`, `../extension-trust-hardening-plan.md:3` use ad-hoc `状态：` / `流程状态：` lines.

## Exclusive files

- `../toggle-comment-plan.md`
- `../macro-record-replay-unified-plans/overview.md`
- `../which-key-auto-trigger-plan.md`
- `../soft-wrap-plans/overview.md`

Only these four files are in scope; the other ad-hoc examples are observation only and are not edited in this wave.

## Design

1. In `toggle-comment-plan.md`, replace the local worktree path line with a portable statement (branch name and parent commit are enough; no drive letter or user directory). Add one unified status block directly below the title: `> **实施状态**：✅ 已实施 —— 2026-11-20（merged as !143 / ebe8fee6）` and leave the body otherwise untouched.
2. In `macro-record-replay-unified-plans/overview.md`, delete only the repository-root-relative-path sentence; keep the "relative to this directory" rule and add the unified status block with the status supported by the document's own history.
3. In `which-key-auto-trigger-plan.md` and `soft-wrap-plans/overview.md`, replace the ad-hoc status line with the unified block, preserving the factual status and date in the block text. Do not rewrite surrounding prose.

## Verification

- Document-only change: no test run required.
- Re-read each edited head and confirm: (a) exactly one `**实施状态**` block; (b) no drive letter or user directory in `toggle-comment-plan.md`; (c) no repository-root-relative-path claim in the macro overview.

## Risk / rollback

Risk: losing historical status detail when collapsing ad-hoc lines; keep the original wording inside the block. Rollback: revert the four files individually.
