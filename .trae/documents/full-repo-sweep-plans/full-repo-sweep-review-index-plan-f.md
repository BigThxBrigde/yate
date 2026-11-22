# D4: adjudicate the review index numbering gap (plan f)

> **实施状态**：✅ 已实施 —— 2026-11-20（`19ecb116`，速览表补口径说明）

Parent: [../full-repo-sweep-plan.md](../full-repo-sweep-plan.md).

## Input

`../../../.trae/reviews/README.md:16` says the quick table holds 44 entries; the table at `:322-389` runs #1–#75 but omits #59–#61 and #67–#72, which appear only in prose (`:78,86,97,215,224,233,246,256,264`). Numbering disagreement is already registered at `:181-183,198,308-318`, including the rule that each branch numbers sequentially and rows are reordered by date at merge time.

## Exclusive files

- `../../../.trae/reviews/README.md`

## Decision

Add a table-header note (option 2 from the issue) rather than nine rows: the quick table lists master-line sequence numbers only; branch-local numbers are recorded in prose and reconciled by date at merge time, with a pointer to the existing disagreement section. Wording must not say "only master sequence numbers are listed" in a way that contradicts the branch-local registration at `:314-318`; phrase it as "the table follows the master-line sequence; branch-local numbers stay in the prose entries and are reconciled at merge time (see the disagreement notes above)".

## Verification

- Document-only change. Re-read `:14-20` and `:308-322` together to confirm the new sentence and the existing disagreement note do not conflict.

## Risk / rollback

Risk: readers still cannot find a missing number from the table alone; the pointer to the prose entries addresses it. Rollback: revert the added sentence.
