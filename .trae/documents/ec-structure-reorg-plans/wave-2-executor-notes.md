# wave-2 (theme/ subpackage) executor notes — checkpoint

## Completed steps (all edits verified in place)

- b.1 git mv done (3 renames, R status):
  theme.py -> theme/__init__.py; themes.py -> theme/themes.py; theme_files.py -> theme/files.py
- b.2 theme/__init__.py: docstring L9/L13 + imports L43/L49 updated
- b.3 theme/files.py: docstring L5/L11 + import L22 updated
- b.4 theme/themes.py: docstring L30 updated (L26 facade path unchanged)
- b.5 consumers: terminal.py:47, manual.py:59, test_theme_trust.py:15/16/23,
  test_theme_files.py:1/19/20 + CHAIN L48 (`monkeypatch.setattr(files, ...)`
  required by L19 rebinding; report as mechanical followup),
  test_theme_palettes.py:456, tools/smoke_test/scenarios/modules.py:10/21/22
- b.6 whichkey.py:17 docstring updated
- b.7 test_architecture.py SIZE_EXEMPT_FILES comment (append-record style,
  ASCII), architecture-boundaries.md L275 (facade exception ->
  theme/__init__.py) + L371-376 (out-of-list record), wikis/yate-architecture.md
  L26 + L181
- b.8 acceptance so far:
  - pyright yate/ tests/ tools/ -> 0 errors (exit 0)
  - pytest tests/ -q -n auto -> exit 0 (no failures)
  - pytest tests/test_architecture.py -q -> 37 passed, exit 0
  - leftover grep (plan b.8 exact command) -> exit 0, stdout empty (0 hits)
  - smoke test: `python -m tools.smoke_test run --no-color --quiet`
    (plan wrote bare `python -m tools.smoke_test`; tool requires subcommand,
    `run` added) -> 121/121 scenarios, 1463/1463 checks, exit 0
  - pytest tests/ --cov=yate -q -> moved to background (id
    e26cf2d26d776184d54a9cfd742bc377), RESULT NOT YET CONFIRMED - must read
    before commit
- b.9 setup done: R15 guard uses rglob (test_architecture.py:1565) ->
  theme/ subpackage auto-covered; theme/ has NO real R15 carrier (grep:
  no SCROLLABLE_BASES class in theme/), drill = temporary injected class
  `class _R15Drill(ScrollView): pass` at end of theme/themes.py, run
  `pytest tests/test_architecture.py::test_scrollable_widgets_apply_theme_scrollbar_pair -q`
  expect FAIL naming theme/themes.py, then revert, rerun expect PASS
- b.10 done: facade runtime check `import yate.editor_components.theme`
  -> resolves to theme/__init__.py, all facade names present (missing []);
  user-facing examples 11 hits (yaterc.example:218, manual.{en,zh}.md 974/889,
  yaterc.{en,zh}.md 178/161/234/211, themes.{en,zh}.md 50/45/183/166) all
  untouched, still `from yate.editor_components.theme import ...`
  (plan said 8 hits, measured 11 - report); cli.py:423 unchanged
- b.11 NOT DONE: stage explicitly by filename (exclude untracked
  .trae/documents/ec-structure-reorg-plans/), commit
  `refactor(editor-components): subpackage theme/ (hub + themes + files)`
  (English, type=refactor, single commit, no push)

## Remaining

1. Read background coverage run result (expect all pass, exit 0)
2. b.9 negative drill (inject -> fail -> revert -> pass)
3. b.11 commit with explicit paths: git add
   yate/editor_components/theme yate/editor_components/terminal.py
   yate/editor_components/manual.py yate/editor_components/whichkey.py
   (deletions of old theme.py/themes.py/theme_files.py are already staged
   as renames R by git mv) tests/test_theme_trust.py tests/test_theme_files.py
   tests/test_theme_palettes.py tests/test_architecture.py
   tools/smoke_test/scenarios/modules.py .trae/rules/architecture-boundaries.md
   .trae/wikis/yate-architecture.md
   NOTE: git status --porcelain before add; old-file deletions + new files:
   verify renames still detected (git status shows R  theme.py -> theme/__init__.py etc.)
4. Final report: rename list + commands/exit codes + drill conclusion +
   deviations (smoke run subcommand; test_theme_files.py:48 chain; 11-vs-8
   doc examples; drill carrier = injected class in themes.py per task owner
   instruction since plan carrier has no R15 match)
