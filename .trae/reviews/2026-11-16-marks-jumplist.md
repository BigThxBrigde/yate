# Review Record: marks & jump list (issue IKUOCI)

- Date: 2026-11-16
- Branch: feature/feat-marks-jumplist (based on master 9c304548)
- Reviewer: code-review-expert (python-code-review skill); fix round by general-purpose executor
- Verdict: 0 blocker / 0 major / 6 minor; all fixed or registered as v2 TODO

## Measured gates at review time (worktree venv)

- `pytest tests/ -q -n auto` -> green, exit 0
- `pytest tests/test_architecture.py -q` -> 42 passed, exit 0
- `pyright yate/ tests/ tools/` -> 0 errors / 0 warnings / 0 informations, exit 0
- `pytest --cov=yate --cov-branch --cov-fail-under=75 -n auto` -> 92.69%, exit 0
- `python -m tools.smoke_test run --jobs 4` -> 124/124 scenarios, 1511/1511 checks, exit 0

## Findings (issue-by-issue)

| # | Severity | Location | Disposition |
|---|---|---|---|
| 1 | minor | marks_palette.py JumpsScreen header misaligned by 1 column vs rows | Fixed: `STACK:<10` compensation, mirrors MarksScreen pattern |
| 2 | minor | marks_palette.py LINE 1-based vs COL 0-based mixed | Fixed: COL rendered 1-based |
| 3 | minor | `_current_entry` duplicated in session.py and navigation_flows.py | Fixed: public `EditorSession.current_jump_entry`, flow copy removed |
| 4 | minor | navigation_flows.py module-level `log` unused | Fixed: removed (minimal change form) |
| 5 | minor | marks_palette.py carried the repo's first `# pyright: ignore[reportPrivateUsage]` | Fixed: public aliases `OverlayScreen`/`OverlayScroll` added in modals.py; ignore removed; zero new suppressions repo-wide |
| 6 | minor | Panel jump into a back-stack entry does not pop it; second alt-left is a no-op press | Registered TODO v2 (documented D7 contract; optional improvement: `take_*` dedup against current position) |
| s1 | suggestion | MarksScreen/JumpsScreen on_key interaction lacks runtime tests | Registered TODO v2 (textual-pilot or smoke scenario) |

## Post-fix re-verification

- Feature test files: 31 passed
- Full suite `-n auto`: green (7 pre-existing platform skips)
- pyright: 0 diagnostics; `pyright: ignore` count in marks_palette.py = 0; no new suppressions introduced

## Notes

- Review findings written back into `.trae/documents/marks-jumplist-plans/overview.md` (deviation register, review table, TODO list).
- Reviewer self-critique recorded: 2 candidate issues retracted after reachability analysis (chord-clear ordering unreachable; modal single-threaded delete path has no reachable failure).

## Round 2: pr-review skill final pass (2026-11-16)

- Verdict: APPROVE. Gates re-measured: pyright 0 diagnostics (exit 0); pytest full green (exit 0); coverage `--cov-fail-under=75` -> 92.70% (exit 0); architecture tests 42 green; editor.py 811 lines consistent with exemption.
- Round-1 fix quality re-verified item by item (current_jump_entry public accessor, COL 1-based, header alignment, dead log removed, OverlayScreen/OverlayScroll public aliases, zero new suppressions).
- Findings:
  - [minor] marks_palette.py coverage 44%, panel interaction untested -> Fixed: added tests/test_marks_palette.py (6 pilot tests), coverage now 100% (navigation_flows 89% -> 91%).
  - [minor] vim VISUAL mode retains VISUAL after nav-key dispatch (anchor cleared, no highlight) -> Registered TODO T4 (consistent with F-key all-mode precedent; not changed in v1).
  - [minor] JumpsScreen cursor can rest on the current row; Enter is a silent no-op -> Registered TODO T5 (semantic documented in docstring).
