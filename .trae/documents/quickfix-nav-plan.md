# Shared Quickfix / Result Navigation Panel Plan (IKY0E8)

Source issue: https://gitee.com/jermaine/yate/issues/IKY0E8
Roadmap context: https://gitee.com/jermaine/yate/issues/IKUCKM
Rules authority: `../rules/` (task orchestration, plan-before-execute, architecture boundaries, Python style, subagent workflow, doc conventions).

## 1. Status and role notes

- New worktree `yate-quickfix-nav`, branch `feature/enh-quickfix-nav`, parent `master` at `b97a695c`; isolated `.venv` self-verified to import from the worktree.
- Unattended mode is explicit for this session; plan approval is bypassed and execution proceeds after planning.
- Planner subagent attempt 1 and retry both failed with `Model "qwen-3.8-plus" not found`; the runtime ignored the replacement frontmatter path/model. Per `../rules/task-orchestration.md` §1.3.5 the main agent executed the planner role and used read-only explorer subagents for evidence. This deviation is recorded here instead of being silently skipped.

## 2. Goals / non-goals

Goals (AC1-AC10): one concrete result model, a persistent bottom-docked panel, globally bound `quickfix_next` / `quickfix_prev`, and three providers (LSP diagnostics, project search, LSP references) feeding the same list. Every panel jump records the pre-jump cursor into the existing jump list. Docs, in-app manual, smoke scenario and full gates are part of the deliverable.

Non-goals: no language-server packaging, no rewrite of search/LSP/diagnostics engines, no code-action quickfix merge, no workspace symbol search, no filtering/sorting UI, no completion/hover/rename interaction changes, no roadmap P1/P2 work. Roadmap checkboxes are external-issue work and can only be prepared in this branch (see §9).

## 3. Evidence (file:line, baseline b97a695c)

- Bottom dock: `yate/editor.py:325-345` yields `terminal_panel` in `#bottom-dock`; `yate/resources/app.tcss:4-14` freezes `#bottom-dock` / `#terminal-dock` ids.
- Widget assembly: `yate/editor_compose.py:140-210` builds the dock widgets; `yate/editor_compose.py:276-358` constructs overlays, navigation, LSP navigation and LspSync with injected capabilities.
- Action/command registration: `yate/actions.py:253-328`; `yate/commands.py:559-581`; key conflict report: `yate/flows/whichkey_flows.py:148-159`, `yate/keymaps/conflicts.py:42-109`.
- Shared-key pattern: constants in `yate/keymaps/keys.py:207-218`, vsc rows in `yate/keymaps/vsc.py:149-155`, vim rows in `yate/keymaps/vim.py:269-289`, vim pre-dispatch set in `yate/keymaps/vim.py:95-102`. Probe result: `<alt-j>`, `<alt-k>`, `<alt-q>` are unused in both tables; `<f7>` and `<alt-r>` are occupied.
- Prompt/modal guard: `yate/editor_dispatch.py:76-77` and `:145-148` return before raw-key conversion, so prompt input must not trigger new global actions.
- Jump list: `yate/session.py:125-189` (`JumpList.push/take_back/take_forward`); `:350-380` (`current_jump_entry`, `push_jump`, `jump_back`, `jump_forward`); existing call sites in `yate/flows/navigation_flows.py:91,99,212` and `yate/flows/prompt_flows.py:300`.
- Diagnostics: `yate/editor_lsp/manager.py:1113-1186` exposes `diagnostics_for`, `counts_for`; `yate/flows/lsp_sync.py:113-129` currently renders a plain `OutputScreen`; `yate/editor_lsp/client.py:154-174` defines `Diagnostic` (0-based positions, 1-4 severity).
- Search: `yate/editor_core/project_search.py:24-41` (`LineMatch`, `FileMatch` include path/row/col/snippet); `yate/editor_components/find_replace.py:160-170,368-408,481-489` keeps results only on the screen and clears them on empty query; `yate/flows/overlay_flows.py:310-318` constructs the screen.
- References: `yate/flows/lsp_navigation_flows.py:153-161,229-248,461-490` writes the chooser then jumps without `push_jump`; `yate/editor_components/lsp_chooser.py:34-142` has `LspRow` and wrap-around selection.
- Legacy TODO: `.trae/reviews/2026-11-16-marks-jumplist.md:72` records T3 "search hits not pushed".
- R15 guard: `tests/test_architecture.py:1665-1673` requires both scrollbar calls in modules defining scrollable widget classes.
- R11 freeze: `tests/test_architecture.py:196-270` (`UI_FROZEN_FILES`); size table: `:344-405,944-997`.
- Smoke: `tools/smoke_test/scenarios/lsp_navigation.py:147-180,257-314` provides a fake LSP server and two-file fixture; `tools/smoke_test/scenarios/__init__.py:53-80` aggregates scenario modules.
- Docs: `yate/docs/README.md:14-18` defines site vs in-app manual authority; `yate/resources/manual.en.md:356,396,869` / `manual.zh.md:324,359,795` hold key/command tables.

## 4. Design and alternatives

Chosen design:

```mermaid
flowchart TD
    D["LSP diagnostics<br/>LspSync"] -->|QuickFixEntry[]| F
    S["project search<br/>FindReplaceScreen"] -->|FileMatch[]| F
    R["references<br/>LspNavigationFlows"] -->|LspRow[]| F
    F["L3 QuickFixFlows<br/>single result list"] -->|rows| P
    P["L2 QuickFixPanel<br/>bottom dock"] -->|pick / close| F
    F -->|session.push_jump + reveal_match| J["existing jump list"]
    A["actions / :commands + vsc/vim keys"] --> F
```

- `QuickFixEntry` is a frozen dataclass in `yate/session.py` (L1 concrete model, not a protocol/central type layer). `QuickFixList` owns `replace(provider, entries, label)`, `clear`, `at(index)`, `next/prev` wrap-around, `selected` and `snapshot`; replacing a provider's result set invalidates the old selection deterministically (first row). No callbacks or documents are stored in the list, so a closed document/server switch cannot leave a stale跳转 target; entries hold path + 0-based row/col + label/detail/provider/severity.
- `QuickFixPanel` is an L2 `VerticalScroll` with `#quickfix-panel`, self-owned theme subscription and R15 scrollbar calls. It renders `provider | severity | label @ path:line:col`, handles up/down/enter/escape with `event.stop()` + `prevent_default()`, and never imports `yate.editor`.
- `QuickFixFlows` is the only L3 result orchestrator. It holds the list + panel reference, exposes `set_*` adapters for the three providers, `open/close/toggle/next/prev/jump_to`, and calls `session.push_jump()` immediately before the injected `reveal(path,row,col)` callback. It does not hold an App handle.
- Diagnostics keep `manager.py` untouched; `LspSync.show_diagnostics` converts its existing query into entries and fills the panel. Empty diagnostics show an explicit panel empty state plus the existing message.
- Project search keeps `FindReplaceScreen` intact; a `results` callback publishes a flat copy after each successful scan. Its own Enter path now calls `session.push_jump()` before reveal (closing T3). Replacing interaction `r`/`a` is unchanged.
- References keep the chooser for immediate selection (backward-compatible migration path) and additionally publish the same list into quickfix, so after closing the chooser the next/prev keys work with no second request. `_jump_to_row` records jump history for chooser/goto-definition; panel jumps use the flow's single push point.

Rejected alternatives:

1. Reuse `OutputScreen` as the result surface: rejected — read-only, no selection/jump, no dock persistence (issue explicitly forbids revival as primary surface).
2. Store result rows on `FindReplaceScreen` / `LspChooserScreen` only: rejected — AC1 requires a shared cross-provider list surviving screen close.
3. New global `Protocol` / service layer with event bus: rejected — R2, R8 and the issue boundary forbid central type layers and string events.
4. Dynamic `App.mount_screen` from the flow: rejected — would require an App handle in L3; the panel is composed by `Editor` and toggled via injected show/hide callbacks.
5. Replace the references chooser outright: rejected — would break IKX5EP interaction; dual publish preserves both paths.

## 5. Waves and exclusive file sets

| Wave | Subplan | Exclusive files (product + tests) | Depends on |
|---|---|---|---|
| 1 | `a` model/panel | `yate/session.py`, `yate/editor_components/quickfix_panel.py`, `tests/test_quickfix_model.py`, `tests/test_quickfix_panel.py` | — |
| 1 | `b` actions/keys/guard | `yate/actions.py`, `yate/commands.py`, `yate/keymaps/keys.py`, `yate/keymaps/vsc.py`, `yate/keymaps/vim.py`, `tests/test_architecture.py`, `tests/test_quickfix_keys.py` | — |
| 2 | `c` flow + dock wiring | `yate/flows/quickfix_flows.py`, `yate/editor.py`, `yate/editor_compose.py`, `yate/resources/app.tcss`, `tests/test_quickfix_flow.py` | a, b |
| 3 | `d` providers | `yate/flows/lsp_sync.py`, `yate/flows/overlay_flows.py`, `yate/editor_components/find_replace.py`, `yate/flows/lsp_navigation_flows.py`, `yate/editor_compose.py`, `tests/test_quickfix_providers.py` | c |
| 4 | `e` docs/smoke/changelog | `yate/docs/lsp.en.md`, `yate/docs/lsp.zh.md`, `yate/resources/manual.en.md`, `yate/resources/manual.zh.md`, `tools/smoke_test/scenarios/lsp_navigation.py`, `CHANGELOG.md`, `CHANGELOG.zh.md`, `yate/resources/changelog.en.md`, `yate/resources/changelog.zh.md` | d |

Wave 1 members are file-disjoint and may run in parallel; waves 2-4 are strictly serial. `tests/test_architecture.py` is touched in wave 1 for the new key guard and in wave 2 only for `UI_FROZEN_FILES` / measured line-count synchronization.

## 6. Risks and rollback

- Risk: vim alt+letter raw keys fall through to motion handling. Mitigation: add all three raw keys to `_NAVIGATION_KEYS`; test each in both modes.
- Risk: double jump-list push when panel and chooser share a target. Mitigation: one push point per path (`QuickFixFlows.jump_to` vs `LspNavigationFlows._jump_to_row`), tested by counting `session.jumps` stack length.
- Risk: stale entries after document close/server switch. Mitigation: entries are pure path/row/col data; providers replace their own slice on new query; `clear` on document close hook is unnecessary because no document reference is retained; test that a removed path produces an explicit message rather than jumping.
- Risk: architecture drift (new upward import, size table). Mitigation: register `UI_FROZEN_FILES` before importing the panel in the flow; add `test_quickfix_keys_are_shared_and_identical`; update rule §六 and measured line counts when `editor.py` changes.
- Rollback: each wave is a separate commit; revert the wave's commit(s) in reverse order. Model/panel alone are inert until wired, so wave 1 rollback has no user-visible behavior change.

## 7. Verification commands

Per-step commands are in each subplan. Final gate (main agent):

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m tools.changelog check
```

## 8. Coverage of AC

| AC | Where |
|---|---|
| AC1 | subplan a (`QuickFixEntry`/`QuickFixList`), subplan d (three providers) |
| AC2 | subplan a (panel), subplan c (dock + flow), subplan e (smoke) |
| AC3 | subplan b (keys/actions/commands/guard), tests + `:check-keys` |
| AC4 | subplan d (`LspSync`), `tests/test_quickfix_providers.py` |
| AC5 | subplan d (`FindReplaceScreen` callback + `push_jump`), T3 closure |
| AC6 | subplan d (`LspNavigationFlows` dual publish + empty message) |
| AC7 | subplan c (single `push_jump` point), tests + smoke jump-back |
| AC8 | subplan c (`UI_FROZEN_FILES`, R13/R15, no new Protocol/TYPE_CHECKING) |
| AC9 | subplan e (bilingual docs/manual, smoke, full gates) |
| AC10 | external roadmap update after merge; branch prepares the exact checkbox text and TODO wording |

## 9. AC10 handoff (external issue cannot be edited from this branch)

After merge, tick the `IKUCKM` item:

`- [x] **quickfix / 结果导航面板** 诊断列表、项目内搜索结果、LSP references 共用的底部可导航结果面板（cnext/cprev 式遍历）。是上述 LSP 功能与项目搜索的公共基础设施，宜早落地。`

and mark `.trae/reviews/2026-11-16-marks-jumplist.md:72` T3 ("search hits not pushed") as closed in the post-merge review ledger. No external write is attempted by this branch.

## 10. Execution record and final gates

Completed waves and commits (all local, no push/merge):

| Commit | Wave / purpose |
|---|---|
| `751b5829` | plan documents |
| `7d6a9b1c` | wave 1 — model, panel, actions/keys, key guard |
| `58b47bdb` | wave 2 — L3 flow, dock wiring, architecture registration |
| `ed7c32c7` | wave 3 — three providers |
| `69016a84` | fix — silent empty-batch clearing |
| `1fa21773` | wave 4 — bilingual docs/manual, smoke, changelog |
| `6808e062` | review fixes — 3 blockers and 6 majors closed |
| `19d55e05` | review record, index and execution-result backfill |
| `983b1e77` | follow-up minor — failed reveals no longer pollute the jump list |

Review record: [`../reviews/2026-11-26-quickfix-nav.md`](../reviews/2026-11-26-quickfix-nav.md) — APPROVE after iteration.

Final gate results (main agent, all exit 0, rerun after `983b1e77`): `pyright` 0 diagnostics; `pytest -n auto` 4084 passed / 10 skipped; architecture 48 passed; branch coverage 92.83% (`fail_under=75`); smoke 129/129 scenarios · 1575/1575 checks; `tools.changelog check` 0.

Additional deviations from the original subplans, all evidence-backed:

- `QuickFixList.replace` uses in-place slice replacement (new batch occupies the discarded batch's display position), matching the written test expectations.
- `QuickFixFlows` receives a shared `QuickFixList` via `entries=` because the panel is constructed before the flow; `Editor.quickfix` holds the same instance.
- `QuickFixPanel.repaint()` is public so L3 can repaint without private access or `pyright` ignores.
- Empty search batches clear the previous search slice but emit no generic message, so a search/replace report on the message line is not overwritten; provider-owned empty messages remain for diagnostics and references.
- Project-search `FileMatch → QuickFixEntry` conversion lives in `QuickFixFlows.set_search_results`, not the assembly module, preserving the six-factory contract.
- `set_quickfix` is a required keyword-only injection in both LSP flows; test harnesses inject recording stubs explicitly.
- Smoke next/prev landing order follows the actual references entry order (definition first, call site second), verified by observable state.

The jump-list edge case is closed: `QuickFixFlows.jump_to` captures the origin before `reveal` and calls `push_jump(origin, row=..., col=...)` only after a successful reveal, so an `OSError` leaves both jump stacks untouched. The negative test was verified red against the old implementation and green after the fix; no `session.py` API expansion was needed.
