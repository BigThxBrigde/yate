# 2026-11-22 LSP navigation review (IKX5EP)

Scope: worktree `d:/Programming/yate-lsp-navigation`, branch
`feature/enh-lsp-navigation`, base `master c6d6e89a`; 33 files / +4375 -19.
Reviewer: code-review-expert (DeepSeek-V4.1-Flash). Skill `python-code-review`
was unavailable in this environment; the agent fell back to its role-file
checklist as its instructions permit.

## Gate results reported by reviewer

| Gate | Result | Exit |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 4 errors, all `tools/smoke_test/scenarios/lsp_navigation.py:191,193` (`pilot: object`) | 1 |
| `pytest tests/ -q -n auto` | 2 failed (`test_action_table.py`, `test_vim_keymap.py`); `-n 1` same -> real regressions | non-zero |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| coverage (`--cov-fail-under=75`, `-n auto`) | 92.48% total; same 2 test failures | non-zero |
| `tools.smoke_test run --jobs 4` | 128/128 scenarios, 1554/1554 checks | 0 |

Real `pyright-langserver` two-file test ran (not skipped); coverage of new
modules: `editor_lsp/navigation.py` 72%, `flows/lsp_navigation_flows.py` 73%,
five new manager request methods effectively 0%.

## Findings (reviewer's severity labels preserved here)

- B1 (reviewer blocker): claimed `:check-keys` reports new vim `gd`/`gr` help
  rows as reserved and conflicts grow 8 -> 10.
- B2 (reviewer blocker): vim `K` row comment says help-only while the row
  actually dispatches; architecture guard does not assert F7+K coexistence.
- M1 (major): `pilot: object` fails pyright; use `Any` with the repo's
  documented reason comment.
- M2 (major): `test_action_table.py` missing `lsp_navigation` namespace/hooks;
  `test_vim_keymap.py` chord-hint expectation missing `gd`/`gr`.
- M3 (major): four docs advertise a nonexistent `:lsp outline` command.
- M4 (major): five new manager request methods have no direct tests; cross-file
  rename column conversion untested.
- M5 (major): rename opens new buffers for unopened targets; rollback restores
  text but leaves newly opened tabs; success message omits "unsaved".
- M6 (major): `LspFeatureUnavailable` conflates "no ready server" with
  "server lacks capability".
- m1-m13 (minor): symbol range, cross-file clamp, cancel error masking, sparse
  exception logs, execute_command silence, documentChanges precedence,
  chooser pick exception, rename prompt prefix, dead timeout branch, stub-key
  R10 test, smoke K/F7 only in vim, rule self-disclosure, stale real-server
  comment.

## Main-agent fact check on B1 (rejected)

Direct probe in the worktree:

```text
find_key_conflicts(VimKeymap(), RESERVED_KEYS) -> 8 conflicts
format_conflicts("vim", ...) -> 8 reserved rows (<alt-c>, <ctrl-b>, ...)
"gd" in RESERVED_KEYS -> False; "gr" in RESERVED_KEYS -> False
```

No conflict-count regression and no reserved classification for `gd`/`gr`;
B1 is rejected with evidence. The remaining B2/M1-M6 are accepted; minors
m3/m7/m8/m9/m13 are folded into the fix round, the rest are registered as
follow-ups in the fix plan.

Reviewer conclusion at time of review: REQUEST_CHANGES. After fixes the main
agent must rerun all gates itself.
