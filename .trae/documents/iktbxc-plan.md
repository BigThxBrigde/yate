# IKTBXC naming hygiene plan

Status: **approved** -- unattended session (user instruction 2026-11-07: no
questions, no approvals). Per workspace rule §二.5, approvals are treated as
granted while rule loading and the closing gate remain mandatory.
Base: `master@3e92532`; worktree `yate-iktbxc`; branch `ref/iktbxc`; independent
`.venv` verified at `D:\Programming\yate-iktbxc\yate\__init__.py`.

## 1. Inputs (single source of truth)

- [iktbxc-issue-notes.md](iktbxc-issue-notes.md) -- verbatim issue material.
- [iktbxc-reference-inventory.md](iktbxc-reference-inventory.md) -- file:line
  read-only inventory of all three old path surfaces, guard constants, and the
  discrepancies between issue claims and repository facts.
- Rules: [architecture-boundaries.md](../rules/architecture-boundaries.md),
  [python-coding-style.md](../rules/python-coding-style.md),
  [subagent-workflow.md](../rules/subagent-workflow.md),
  [doc-conventions.md](../rules/doc-conventions.md),
  [task-orchestration.md](../rules/task-orchestration.md).
- Sub-plan index: [iktbxc-plans/overview.md](iktbxc-plans/overview.md).

## 2. Goals and non-goals

Goals: remove name/role mismatches, move the pure completion function out of
the L3 flows layer, and keep naming consistent for the same concept.

Hard non-goals (issue §五, no scope creep):

- zero runtime behavior change, zero new dependency direction; diff = `git mv`
  + import lines / path strings / docstrings / rule docs / test names only;
- no class renames (`EditorView`, `PaneRegistry`, `PaletteScreen`, `LspSync`);
- no plugin public API change, no user-facing directory convention change;
- no back-edits to `CHANGELOG*`, `tools/changelog/zh_overrides.json`,
  `.trae/documents/**` historical plans, or `.trae/reviews/**` read-only records;
- no opportunistic file splitting, no `SIZE_EXEMPT_FILES` changes;
- P2 items (editor_sprites characters/chars, palette tri-homonym) are out of
  this issue's gate batch;
- `editor_view.py` is explicitly forbidden as the new L2 module name (it is the
  old package name retired on 2026-11-02).

## 3. Alternatives and veto reasons

| # | Option | Decision / reason |
|---|---|---|
| A1 | Keep `keyproto/legacy.py`, only edit the docstring | Vetoed: issue P0-1 requires the module name to match its role; the word `legacy` is read as "awaiting deletion" while this is the only active codec. |
| A2 | `git mv` to `yate/keyproto/key_codec.py`, rewrite first docstring line | **Chosen**: 1 file + 9 active references + 1 rule line + 3 wiki lines; name states the role. |
| B1 | Rename L2 module to `editor_view.py` / `text_view.py` | `editor_view.py` vetoed by issue (old package name regression); `text_view.py` vetoed as longer without adding information -- the class is `EditorView`, so `view.py` is the shortest non-ambiguous name. |
| B2 | `git mv` to `yate/editor_components/view.py` | **Chosen**: removes the L2/L3 `editor.py` duplicate, aligns with `EditorView`, no existing `view.py` in that package (verified by directory listing). |
| C1 | Keep `yate/flows/cmdline_completions.py`, only fix docs | Vetoed: P1-3 explicitly requires layer relocation; the module owns no state, imports no UI and does no flow orchestration (wiring is `editor_compose.py:127-137` injecting a `partial` into `PromptBar`). |
| C2 | `yate/services/cmdline_completions.py` with no rank registration | Vetoed by measurement: `cmdline_completions.py:12-14` imports `yate.registries` and `yate.session` (rank 1) plus `yate.services.workspace` (rank 0). `_layer_rank()` defaults unregistered paths to 0 and `UPWARD_EDGES_FROZEN` is empty, so `test_no_unregistered_upward_imports` would report two unregistered upward edges. |
| C3 | `yate/services/cmdline_completions.py` + `_LAYER_RANKS` rank 1 | Vetoed: puts an L1 single file inside the L0 `services/*` leaf package, widening the exact L0/L3 historical compromise the issue lists under "explicitly not changed"; also collides with R4's UI-free package wording. |
| C4 | `yate/cmdline_completions.py` + `_LAYER_RANKS` entry `("cmdline_completions.py", 1)` | **Chosen**: one of the issue's two suggested targets; root-level single file like `config.py` / `diagnostics.py`; rank 1 matches its two L1 imports, so all existing edges stay downward or same-layer; no upward edge, no new package exception. Both `README.md:272` and `README.zh.md:290` already list the bare filename in the root `yate/` tree, so the docs become accurate without edits. |
| C5 | Drop the L1 imports by injecting callables instead of `CommandRegistry` / `EditorSession` | Vetoed: changes signatures and runtime wiring, violating the zero-behavior-change non-goal. |
| C6 | Register the two edges in `UPWARD_EDGES_FROZEN` instead of a rank entry | Vetoed: the rule text and the guard both state the exception set is empty (zero upward edges since 2026-10-20); re-opening it contradicts "zero dependency-direction change". |

Deviation to record: issue §一.3 suggests `services/` **L0 leaf** as the first
choice. Chosen C4 is its second suggested target with an explicit L1 rank
registration. Evidence: `tests/test_architecture.py:520-525` (`_layer_rank`
defaults to 0), `:765-793` (guard), `:165` (empty exception set), and
`yate/flows/cmdline_completions.py:12-14` (the three imports). The rank entry is
verified by the wave-3 negative drill.

## 4. Architecture impact

- R2 / `ALLOWED_PROTOCOLS`: the `PaneRegistry` whitelist key is path-based
  (`tests/test_architecture.py:130`), so wave 2 must move the key from
  `editor_components/editor.py` to `editor_components/view.py` or
  `test_no_new_protocols` turns red.
- R11 / `UI_FROZEN_FILES`: the two allowed-set values at
  `tests/test_architecture.py:213` and `:225` are old module strings; wave 2
  must change them to `yate.editor_components.view`, or
  `test_collaborators_keep_widget_coupling_frozen` turns red.
- Layer ranks: `_LAYER_RANKS` (`:141-158`) is prefix based; wave 3 adds one L1
  entry. `test_no_unregistered_upward_imports`, `test_flow_modules_hold_no_app_handle`
  (`:1306-1320`, top-level `yate/*.py` is already scanned) and
  `test_no_relative_imports` cover the relocated root module automatically.
- R4 (UI-free packages/files): no change; the new root module imports no
  `editor_components`.
- Naming guard (`test_no_banned_identifier_names:869-878`): scans the whole
  tree; wave 1's negative drill proves new paths are still covered.
- Rule text wave-3 sync points: `architecture-boundaries.md` §一 L3 inventory
  (`:25`), L1 inventory (`:31-37`), R11 enumeration (`:133`, `:139-142`),
  §二 responsibility table (`:268`), §三.6 pure-computation list (`:297`),
  §六 R11 guard list (`:457`); plus `tests/test_architecture.py:25` docstring.
- No new `Protocol`, `TYPE_CHECKING`, `Any`, `# type: ignore`, logging change,
  theme change, scrollable widget, or new widget id.

## 5. Waves

Three strictly serial waves (see [overview.md](iktbxc-plans/overview.md)):
wave-1 [plan-a](iktbxc-plans/iktbxc-key-codec-plan-a.md),
wave-2 [plan-b](iktbxc-plans/iktbxc-view-plan-b.md),
wave-3 [plan-c](iktbxc-plans/iktbxc-cmdline-relocation-plan-c.md).
They overlap on `tests/test_architecture.py` and
`.trae/rules/architecture-boundaries.md`, therefore they CANNOT be parallelized;
each wave ends with one independent commit preserving `git mv` rename tracking.

## 6. Acceptance

Per-wave commands are in each sub-plan. Closing gate (main agent only):

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m yate --help
```

Residual grep (expect 0 hits) over the source face `yate/ tests/ tools/ pack/
pyproject.toml .trae/rules/ .trae/wikis/ README.md README.zh.md`:

```powershell
git grep -n -E "keyproto\.legacy|editor_components\.editor|flows\.cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
git grep -n -E "keyproto/legacy|editor_components/editor|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

Exempt: `.trae/documents/**` (historical plans + this task's notes/plan),
`.trae/reviews/**` (read-only fact records), `CHANGELOG*`,
`tools/changelog/zh_overrides.json`. Both README files contain only the bare
filename `cmdline_completions.py` in the root tree, which is accurate after the
move, so bilingual sync is not triggered.

Negative drills (one per changed scan-path guard, plus one extra):

1. wave-1 naming guard: temporarily add a `class RenameProbeController` to the
   new codec module -> `test_no_banned_identifier_names` must fail -> restore ->
   green.
2. wave-2 R2 path guard: temporarily restore the old `ALLOWED_PROTOCOLS` key ->
   `test_no_new_protocols` must fail -> restore -> green.
3. wave-2 R11 frozen surface: temporarily restore one old allowed-set value ->
   `test_collaborators_keep_widget_coupling_frozen` must fail -> restore -> green.
4. wave-3 layer rank: temporarily remove the new `_LAYER_RANKS` entry ->
   `test_no_unregistered_upward_imports` must fail with the two upward edges ->
   restore -> green.

Each drill: verify the file content on disk after every edit, clear
`__pycache__` of the touched package/test directory before re-running (pyc
timing artifact observed in prior sessions), and finish with
`git status --short` clean for that file.

## 7. Risks and rollback

| Risk | Mitigation |
|---|---|
| Missed path string / docstring | two residual greps + `git grep` manual triage (no blind global replace) + pyright + full pytest |
| Guard goes deaf after path change | four negative drills with restore-and-green |
| `git mv` rename tracking lost | strict `git mv`, `git log --follow -- <new path>` spot-check after each commit |
| Plugin / smoke scenario imports old path | 121-scenario smoke + `python -m yate --help` |
| Rule/code drift | `architecture-boundaries.md`, `tests/test_architecture.py`, `.trae/wikis/yate-architecture.md` and root docs synced in the same wave as the code |

Rollback: three independent commits, `git revert` per commit; worktree sandbox
isolates the main repo.

## 8. Execution contract and deviations

- Unattended: approval bypass, subagents spawn with `bypassPermissions`; closing
  gate is NOT exempt.
- `subagent-workflow.md` §一.3 forbids subagents editing product source
  (`yate/`). All three waves are executed by the MAIN AGENT under the
  `plan-executor` script with this plan as the single spec. The review step is
  delegated to `code-review-expert` (bypassPermissions, full window before any
  death judgment per prior feedback).
- `plan-architect-designer` was spawned twice (both with `bypassPermissions`,
  model `Hy4 preview` per `task-orchestration.md` §一.3) and failed both times
  with `Model "qwen-3.7-plus" not found` (the definition file's static model is
  not registered in this runtime). Per `task-orchestration.md` §一.3.5 / §三,
  the main agent produced this plan itself -- **subagent zero output for the
  planning role**, recorded here as a fact.
- Issue-claim discrepancies (measured, see inventory §G): `:213/:225` are
  allowed-set values not keys; P0-2 has 36 lines not 22 and `editor_compose.py`
  has no such reference; P0-1's "9 active references" excludes 109 `.trae`
  lines; `yate/docs` has 0 hits; there is no `FLOWS` constant and no
  `test_banned_identifier_names`. Execution follows the measured inventory, not
  the stale claims.
- No new behavior tests: the task changes no runtime behavior; guard coverage is
  proven by the four negative drills plus the full 37-case architecture suite.

## 9. Closing backfill (filled by the main agent at the end)

To be filled with real numbers, command exit codes, deviations, review outcome,
and the final commit list.
