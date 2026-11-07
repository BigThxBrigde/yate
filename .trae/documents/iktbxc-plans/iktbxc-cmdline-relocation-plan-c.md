# Wave-3 sub-plan C: relocate `cmdline_completions` out of L3 `flows/`

Index: [overview.md](overview.md) | main plan: [../iktbxc-plan.md](../iktbxc-plan.md)
Facts: [../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §D/§E/§G.

All paths are repository-root relative (command basis). Read every region
before editing; no blind global replace.

## 1. Design decision (deviation recorded in main plan §3/C4)

`git mv yate/flows/cmdline_completions.py yate/cmdline_completions.py`, plus a
new `_LAYER_RANKS` entry `("cmdline_completions.py", 1)`.

Why rank 1: the module imports `yate.registries` (L1), `yate.session` (L1) and
`yate.services.workspace` (L0) at `:12-14`. `_layer_rank()` defaults unlisted
paths to 0, `UPWARD_EDGES_FROZEN` is empty, and
`test_no_unregistered_upward_imports` rejects any import whose target rank is
higher than the source rank. With rank 1 the two L1 imports are same-layer and
the L0 import is downward: zero new upward edges, zero import-line changes
inside the moved module. From its only consumer `yate/editor_compose.py`
(rank 3) the new import is downward. This is the issue's second suggested
target; the first (`services/` L0) is vetoed in main plan §3/C2-C3.

## 2. Input / output / exclusive file list

Output: root-level L1 pure-function module; rule text, guard ranks, wiki,
comments and test imports synced; zero runtime behavior change.
Independent commit: `refactor(architecture): relocate cmdline_completions out of flows`.

Files:
- `yate/flows/cmdline_completions.py` -> `yate/cmdline_completions.py` (`git mv`)
- `yate/editor_compose.py`, `yate/config.py`,
  `yate/services/extensions/api.py`
- `tests/test_app_find.py`, `tests/test_cmdline_completions.py`,
  `tests/test_workspace_filter.py`, `tests/test_architecture.py`
- `tools/smoke_test/scenarios/guards.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`
- `README.md`, `README.zh.md`: **verified zero change needed** -- both already
  list the bare filename in the root `yate/` tree (`:272` / `:290`), which the
  move makes accurate; bilingual sync is therefore not triggered.

NOT touched: `yate/flows/__init__.py` (no re-exports, 0 references),
`yate/services/__init__.py`, `tests/test_set_options.py:45` (test name already
uses the bare function name), `.trae/documents/**` historical plans,
`.trae/reviews/**`, `CHANGELOG*`, `tools/changelog/zh_overrides.json`,
`UI_FROZEN_FILES` (it has no `flows/cmdline_completions.py` key), P2 files.

## 3. Steps

### Step C1 -- baseline

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmdline_completions.py tests/test_app_find.py -q
```

Exit code 0.

### Step C2 -- rename

```powershell
git mv yate/flows/cmdline_completions.py yate/cmdline_completions.py
```

`git status --short` shows `R`. The module body (53 lines) is unchanged; no
import rewrite inside it.

### Step C3 -- exact string edits

| File:line | Kind | Old -> New |
|---|---|---|
| `yate/editor_compose.py:33` | import | `from yate.flows.cmdline_completions import cmdline_completions` -> `from yate.cmdline_completions import cmdline_completions` (re-sort into alphabetical position among the `from yate.*` group) |
| `yate/config.py:12` | module docstring | `:mod:\`yate.flows.cmdline_completions\`` -> `:mod:\`yate.cmdline_completions\`` |
| `yate/config.py:290` | `#:` comment | `` ``flows/cmdline_completions`` `` -> `` ``cmdline_completions`` `` |
| `yate/services/extensions/api.py:411` | comment | `` ``flows/cmdline_completions.py`` `` -> `` ``cmdline_completions.py`` `` |
| `tests/test_app_find.py:18` | import | `from yate.flows.cmdline_completions import cmdline_completions` -> `from yate.cmdline_completions import cmdline_completions` (re-sort) |
| `tests/test_cmdline_completions.py:28` | import | same |
| `tests/test_workspace_filter.py:887` | comment | `migrated from flows/cmdline_completions, 2026-10-30` -> `migrated from cmdline_completions, 2026-10-30` (keeps the historical date, drops the stale path) |
| `tools/smoke_test/scenarios/guards.py:200` | docstring | `yate/flows/cmdline_completions.py` -> `yate/cmdline_completions.py` |
| `tests/test_architecture.py:25` | module docstring | remove `` ``flows/cmdline_completions.py`` `` from the R11 collaborator list (it no longer lives in `flows/`) |
| `tests/test_architecture.py:141-158` | `_LAYER_RANKS` | add `("cmdline_completions.py", 1)` in the L1 group, with a `#:` comment explaining the two L1 imports and the no-upward-edge invariant |

Rule text (`.trae/rules/architecture-boundaries.md`):

| Line | Section | Edit |
|---|---|---|
| `:25` | §一 L3 `flows/` inventory | remove `cmdline_completions.py` from the L3 list |
| `:31-37` | §一 L1 inventory | add `cmdline_completions.py` with a note: pure prompt-completion computation consuming `registries` / `session` (L1) and `services/workspace` (L0); rank registered as L1 in `tests/test_architecture.py` |
| `:133` | R11 flows enumeration | remove `cmdline_completions.py` |
| `:139-142` | R11 note about the removed `UI_FROZEN_FILES` entry | rewrite to state the module left `flows/` via IKTBXC and now sits at L1 root; the whitelist entry remains absent |
| `:268` | §二 responsibility table | replace the `flows/cmdline_completions.py` example with root-level `cmdline_completions.py` (or drop the example, keeping the pure-function classification) |
| `:297` | §三.6 pure-computation list | keep `cmdline_completions` and annotate its new root-level L1 home |
| `:457` | §六 R11 guard list | remove `flows/cmdline_completions.py` |
| §六 37-case table | unchanged (no new architecture case in this task) |

Architecture wiki (`.trae/wikis/yate-architecture.md`):

| Line | Edit |
|---|---|
| `:23` | Mermaid FLOWS node: drop `+ lsp_sync/cmdline_completions` -> `+ lsp_sync` |
| `:151` | table row `flows/completion_flows.py / flows/cmdline_completions.py` -> `flows/completion_flows.py` + `cmdline_completions.py` (root L1) with the same "prompt completion" description |
| `:159` | flows inventory: remove `cmdline_completions.py::cmdline_completions` from the `flows/*` row and add a separate root-level L1 row |

No Mermaid node in the rule file's hard dependency graph needs a new edge: the
root module is an L1 consumer, drawn by the rank annotation rather than a new
cross-layer arrow.

### Step C4 -- negative drill (layer-rank guard)

1. In `tests/test_architecture.py`, temporarily remove the newly added
   `("cmdline_completions.py", 1)` entry; verify on disk.
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_unregistered_upward_imports -q`
   MUST fail with an `unregistered upward import(s)` message containing
   `cmdline_completions.py -> yate.registries` and
   `cmdline_completions.py -> yate.session`.
3. Restore the entry, verify on disk, clear `tests/__pycache__` and
   `yate/__pycache__`, re-run -> exit code 0.
4. `git status --short` shows only the intended wave-3 diff.

### Step C5 -- acceptance

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmdline_completions.py tests/test_app_find.py tests/test_set_options.py tests/test_workspace_filter.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m yate --help
git grep -n -E "flows\.cmdline_completions|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

All exit code 0; the last grep prints nothing (no-match exit code 1 expected).

### Step C6 -- commit and rename check

```powershell
git add -A
git commit -m "refactor(architecture): relocate cmdline_completions out of flows"
git --no-pager log --follow --oneline -- yate/cmdline_completions.py
```

## 4. Risks / rollback

- Guard rank omission is the top risk; drill C4 proves the entry is load-bearing.
- Rule text drift: all six rule locations land in this same commit.
- Stale comments/README: residual grep + manual `git grep` triage.
- Rollback: `git revert <wave-3 commit>` (then waves 2/1 if needed).

## 5. Backfill (filled during execution)

Real command results, exit codes, C4 drill evidence, deviations.
