# Plan e — Bilingual docs, manual, smoke scenario and changelog

Parent: [`../quickfix-nav-plan.md`](../quickfix-nav-plan.md). Rules: [`../../rules/doc-conventions.md`](../../rules/doc-conventions.md), [`../../rules/git-commit-message.md`](../../rules/git-commit-message.md).

## Input / output

Input: waves a-d landed and green. Output: AC9 evidence and AC10 preparation.

## Exclusive files

- `yate/docs/lsp.en.md`, `yate/docs/lsp.zh.md`
- `yate/resources/manual.en.md`, `yate/resources/manual.zh.md`
- `tools/smoke_test/scenarios/lsp_navigation.py`
- `CHANGELOG.md`, `CHANGELOG.zh.md`, `yate/resources/changelog.en.md`, `yate/resources/changelog.zh.md`

## Concrete changes

1. `yate/docs/lsp.{en,zh}.md`: add a paired "Result navigation" subsection describing `:diagnostics` filling the bottom quickfix panel, `gr` dual-publishing references, `alt+j`/`alt+k` (vsc/vim), `:quickfix`, `:cnext`, `:cprev`, and jump-list back/forward (`alt+left`/`alt+right`). Keep existing lsp sections unchanged.
2. `yate/resources/manual.{en,zh}.md`: add the three keys to both keymap tables (§5.1/5.2), the three commands to §8 command table, and the cheat-sheet rows in §18; phrase with existing bilingual conventions. These are user-visible key changes, so both languages must land in the same commit.
3. `tools/smoke_test/scenarios/lsp_navigation.py`: add `_quickfix_panel_next_prev_and_jump_back(tmp)` reusing `_two_file_project`, `_install_nav_server`, `_open_call_site`:
   - press `alt+r` (gr in vsc), wait until `app.editor.quickfix_flows.active_entries` has 2 references;
   - press `escape` to dismiss chooser, run `:quickfix`, assert panel `display` is true and SVG text contains `references` and at least one file name;
   - press `alt+j`, wait until cursor is on the definition row in the other file; press `alt+k`, wait until cursor returns to call-site row; assert the panel is still displayed after both jumps;
   - press `alt+left` (jump back), wait until the document is back at the pre-jump position; assert `back stack` length decreased by one;
   - append `Scenario("quickfix_panel_next_prev_and_jump_back", ..., ("lsp-navigation",))` to `SCENARIOS`.
4. Changelog: regenerate with `python -m tools.changelog` after all commits in this branch exist, then verify `python -m tools.changelog check`; do not hand-edit generated headers. If generation is unavailable before merge, record the exact `[Unreleased]` bullet in both languages in the plan doc and leave generated files unchanged rather than fabricating links.

## Acceptance commands

```powershell
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m tools.changelog check
.venv\Scripts\python.exe -m pytest tests/test_gate_config.py -q
```

## Risks / rollback

- Risk: smoke flake from chooser dismissal timing; use `wait_until` on observable flow state, never fixed sleeps, and re-run with `--jobs 1` to distinguish load flake.
- Risk: manual tables drift between languages; the acceptance step checks both files changed together in one commit.
- Rollback: revert docs/smoke/changelog; code behavior stays intact.
