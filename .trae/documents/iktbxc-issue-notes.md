# IKTBXC issue input notes (verbatim task material, no analysis)

Issue: <https://gitee.com/jermaine/yate/issues/IKTBXC>
Title: `refactor: keyproto/legacy.py、editor_components/editor.py 更名与 cmdline_completions 层级归位 —— 命名自查修复、守卫与规则文档同步`
State: 待办的 / enhancement / created 2026-11-06 10:22 / 0 comments.
Worktree: `yate-iktbxc`, branch `ref/iktbxc`, base `master@3e92532`.

## Stated goal

Critical naming review of modules/subpackages. Two earlier reviews only verified rule
compliance (snake_case, banned suffix guards, 37 architecture tests green) and missed
three classes of debt: name/role mismatch, wrong layer, same word with different
meanings. This issue converges 5 confirmed naming/structure debts, **zero runtime
behavior change**, and explicitly lists the items evaluated but NOT changed, to
prevent scope creep.

## P0-1: `yate/keyproto/legacy.py` name/role mismatch

- Current: docstring first line says "Legacy key codec", "Formerly
  `yate.editor_components.keys`"; easily misread as a deprecated compatibility
  layer awaiting deletion.
- Reality: the repo's **only current** key-name -> raw byte sequence codec, with 9
  active references: `yate/app.py:30`, `yate/editor_dispatch.py:23`,
  `yate/editor_term/keys.py:12`, `yate/keyproto/__init__.py:13`,
  `tests/test_term_keys.py:12`, `tests/test_keyproto.py:30`,
  `tests/test_app_textual.py:23`; plus docstring references at
  `editor_dispatch.py:123`, `editor_term/keys.py:4`.
  `keyproto/__init__.py:13` lists it as one of the three codecs.
- Suggestion: `git mv` to `key_codec.py`; update all imports / docstrings /
  rule-text references. Rewrite the module docstring first line to explain that
  "legacy" refers to the terminal key naming system.

## P0-2: `yate/editor_components/editor.py` cross-layer duplicate name

- Current: module `editor`, main class `EditorView` (:74); top-level
  `yate/editor.py` holds the L3 `Editor`. Two `editor.py` files at L2/L3,
  distinguished only by caller memory.
- Reference surface 22 sites: `yate/editor.py:61`, `yate/editor_dispatch.py:19`,
  `yate/editor_compose.py`, `flows/mouse_flows.py:19`,
  `flows/completion_flows.py:24`, 8 tests,
  `tools/smoke_test/scenarios/multi_cursor.py:18`,
  `tests/test_architecture.py:213/225` (`UI_FROZEN_FILES` keys),
  `editor_components/__init__.py`, `welcome.py`, `highlighting.py`, `panes.py`
  docstrings.
- Suggestion: `git mv` to `view.py` (or `text_view.py`), aligned with `EditorView`.
  **Forbidden**: `editor_view.py` -- that phrase is the old package name changed
  on 2026-11-02; reusing it would regress the rename and confuse docs.
- Sync: `UI_FROZEN_FILES` keys, all docstrings, tests, smoke scenarios.

## P1-3: `yate/flows/cmdline_completions.py` belongs outside L3

- Current: lives in L3 `flows/`, registered in the R11 flows enumeration.
- Reality: docstring self-describes "pure functions" / "owns no state and imports
  no UI"; dependencies only `yate.registries` (L1), `yate.services.workspace` (L0),
  `yate.session` (L1), **zero L3 dependencies**. Actual wiring is
  `editor_compose.py:127-133` injecting a `partial` into the L2 `PromptBar`
  callback; not flow orchestration. Rule §三.6 already classifies
  `cmdline_completions` as "pure computation implemented with functions".
- Layer side effects: L0 `yate/config.py:12` docstring and `:290` comment refer
  back to `:mod:yate.flows.cmdline_completions`;
  `services/extensions/api.py:411` comment and
  `tests/test_cmdline_completions.py` also reference that path.
- Suggestion: `git mv` to `yate/services/cmdline_completions.py` (L0 leaf service,
  same layer as `services/workspace.py`) or `yate/cmdline_completions.py`; sync
  `architecture-boundaries.md` §一 L3 list / R11 enumeration / §三.6,
  `editor_compose.py:33`, `config.py`, `api.py:411`, `tests/test_architecture.py`
  and related tests.

## P2 (explicitly out of this issue's gate batch; separate review)

- P2-4: `editor_sprites/` mixes full word and abbreviation: `characters.py`
  (character registry) and `chars/` (27 bitmap data modules) denote the same
  concept with two spellings (`characters.py:25` imports
  `yate.editor_sprites.chars`, `chars/__init__.py:3` says "Imported by
  `yate.editor_sprites.characters` only"). Suggest `characters.py` -> `registry.py`,
  `chars/` -> `characters/`, sync 27 module imports and
  `python-coding-style.md` §1.2 `_shared` entry.
- P2-5: `palette` has three meanings: `editor_components/palette.py:1`
  (command palette + quick open, `PaletteScreen`), `editor_term/palette.py:1`
  (xterm 256 color table, `palette_color`), `editor_sprites/render.py` (sprite
  `Palette` type). All are domain-standard terms, not a hard defect. If cleaned,
  suggest `editor_components/palette.py` -> `command_palette.py` plus test renames
  following prior rename-wave conventions.

## Explicit non-goals (veto reasons, hard boundaries)

| Item | Veto reason |
|---|---|
| `flows/` -> `editor_flows` | L3 peers `actions/commands/diagnostics` are prefix-free short names; package/file/class naming already aligned; ~90 pure churn sites; R11 / §三.8 / guards all anchored on `flows/` |
| `services/` mixed L0/L3 | `services/__init__.py:15` already self-describes the L3 machinery subpackages; R14 freezes the 14 public names of `yate.services.extensions` (plugin API); moving breaks plugin ecosystem, a registered historical compromise |
| `yate/extensions/` plugin dir vs `services/extensions/` machinery pkg | `loader.py:296` `cwd/"extensions"` and `:310` `yate_home()/"extensions"` are runtime user-facing conventions; changing is breaking |
| Cross-package same-name `diff.py` | Namespace isolation, industry normal |

## Goals / non-goals

Goals: remove name/role mismatches, move pure functions to the correct layer,
unify naming for the same concept.

Non-goals:
- Zero runtime behavior change, zero dependency-direction change; diff only
  `git mv` + import lines / path strings / docstrings / rule docs / test names;
- No class renames (`EditorView` / `PaletteScreen` / `LspSync` stay);
- No plugin public API change, no user-facing directory convention change
  (`./extensions`, `~/.yate/extensions`), no back-edits to CHANGELOG historical
  notes or `tools/changelog/zh_overrides.json`;
- `.trae/documents/` historical plan docs are not back-edited (existing convention);
- No opportunistic file splitting, no size-exemption list changes.

## Implementation and acceptance (verbatim)

Three independent commits by subject (keep `git mv` rename tracking and per-commit
revertability):
- Wave 1: P0-1 `keyproto/legacy.py` -> `key_codec.py` (1 file + 9 references);
- Wave 2: P0-2 `editor_components/editor.py` -> `view.py` (incl.
  `UI_FROZEN_FILES` keys and docstrings);
- Wave 3: P1-3 `cmdline_completions` layer relocation (incl. rule doc §一 / R11 /
  §三.6 sync);
- P2 items are reviewed separately, not part of this issue's gate batch.

Acceptance commands (all exit code 0):
```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

Residual grep expected 0: `keyproto.legacy` / `editor_components.editor` /
`flows.cmdline_completions` (exempt CHANGELOG historical notes and
`.trae/documents/` historical docs). Changed scan-path guards (R11 frozen surface,
layer ranks, naming guards) each require one negative drill: temporarily restore a
violation -> confirm interception -> restore and re-verify green.

## Risks and rollback

| Risk | Mitigation |
|---|---|
| String patch targets / docstring paths missed | residual grep triple + pyright + full pytest; `git grep` manual triage per hit, no blind global replace |
| Guards go deaf (path changed but sets / scan roots not) | negative drill x3, restore after confirming interception |
| `git mv` rename tracking lost | strict `git mv` (never delete+create), spot-check `git log --follow` after commit |
| Plugin / smoke scenarios import old path | full smoke 121 scenarios + `python -m yate --help` baseline |
| Rule doc / code drift | `architecture-boundaries.md` and `tests/test_architecture.py` synced in the same wave, no after-the-fact patch |

Rollback: three independent commits, `git revert` each; isolated worktree sandbox,
main repo unaffected.

## Notes collected by the coordinator (facts only, no analysis)

- Unattended session: user instructed to enter unattended mode, no questions or
  approvals. Plan approval is treated as granted; all subagents spawn with
  `bypassPermissions`; gate execution is NOT exempted.
- Repo state at intake: `master` clean at `3e92532`; existing worktrees are
  `yate-enew-args-lsp-attach`, `yate-filemgr-theme-beautify`,
  `yate-multi-dim-review-r2` (none reused for this new task).
