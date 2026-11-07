# Wave-2 sub-plan B: `editor_components/editor.py` -> `view.py`

Index: [overview.md](overview.md) | main plan: [../iktbxc-plan.md](../iktbxc-plan.md)
Facts: [../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §C.

All paths are repository-root relative (command basis). Read every region
before editing; no blind global replace. `editor_view.py` is FORBIDDEN.

## 1. Input / output

Input: L2 module `yate/editor_components/editor.py` holding `PaneRegistry`
(`:50`) and `EditorView` (`:74`), with 14 product-code references, 1 tcss
comment, 9 test references, 1 smoke scenario, 2 rule lines and 1 review line.
Output: `yate/editor_components/view.py` with identical classes/behavior; all
imports, docstrings, guard sets, tcss comment, tests, smoke scenario, rule text
and the current architecture wiki synced.
Independent commit: `refactor(editor-components): rename editor module to view`.

## 2. Exclusive file list

- `yate/editor_components/editor.py` -> `yate/editor_components/view.py` (`git mv`)
- `yate/editor.py`, `yate/editor_dispatch.py`, `yate/session.py`,
  `yate/editor_components/__init__.py`, `welcome.py`, `highlighting.py`,
  `panes.py`, `terminal.py`, `completion.py`,
  `yate/flows/mouse_flows.py`, `yate/flows/completion_flows.py`
- `yate/resources/editor-view.tcss`
- `tests/test_app_mouse.py`, `tests/test_app_panes.py`,
  `tests/test_dispatch_guards.py`, `tests/test_panes.py`,
  `tests/test_support_mouse.py`, `tests/test_architecture.py`
- `tools/smoke_test/scenarios/multi_cursor.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`

NOT touched: `.trae/reviews/**` (read-only records), `.trae/documents/**`
historical plans, `CHANGELOG*`, `SIZE_EXEMPT_FILES`, any class name, the tcss
file name `editor-view.tcss` (only its comment path string changes).

## 3. Steps

### Step B1 -- baseline

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

Exit code 0, 37 cases.

### Step B2 -- rename

```powershell
git mv yate/editor_components/editor.py yate/editor_components/view.py
```

`git status --short` must show `R`. No `view.py` existed before (verified).

### Step B3 -- exact string edits

Every `yate.editor_components.editor` -> `yate.editor_components.view`, every
`editor_components/editor.py` -> `editor_components/view.py`, and every
`~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView`:

| File:line | Kind | Old -> New |
|---|---|---|
| `yate/editor.py:61` | import | `from yate.editor_components.editor import EditorView` -> `...view import EditorView` |
| `yate/editor_dispatch.py:19` | import | same |
| `yate/session.py:272` | comment | `editor_components/editor.py` -> `editor_components/view.py` |
| `yate/editor_components/__init__.py:5` | docstring ref | `~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView` |
| `yate/editor_components/__init__.py:26` | import example | `from yate.editor_components.editor import EditorView` -> `...view...` |
| `yate/editor_components/welcome.py:3` | docstring | `:mod:\`yate.editor_components.editor\`` -> `:mod:\`yate.editor_components.view\`` |
| `yate/editor_components/highlighting.py:3` | docstring | same |
| `yate/editor_components/panes.py:24` | docstring | same |
| `yate/editor_components/panes.py:40` | import | `from yate.editor_components.editor import LEFT_BUTTON, EditorView` -> `...view...` |
| `yate/editor_components/terminal.py:40` | import | `from yate.editor_components.editor import LEFT_BUTTON` -> `...view...` |
| `yate/editor_components/completion.py:4` | docstring ref | `~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView` |
| `yate/flows/mouse_flows.py:3` | docstring ref | same |
| `yate/flows/mouse_flows.py:19` | import | `from yate.editor_components.editor import LEFT_BUTTON, EditorView` -> `...view...` |
| `yate/flows/completion_flows.py:24` | import | `from yate.editor_components.editor import EditorView` -> `...view...` |
| `yate/resources/editor-view.tcss:2` | CSS comment | `editor_components/editor.py` -> `editor_components/view.py` |
| `tests/test_app_mouse.py:22` | import | `...editor import EditorView` -> `...view import EditorView` |
| `tests/test_app_panes.py:16` | import | same |
| `tests/test_dispatch_guards.py:19` | import | same |
| `tests/test_panes.py:26` | import | same |
| `tests/test_support_mouse.py:31` | import | same |
| `tools/smoke_test/scenarios/multi_cursor.py:18` | import | same |
| `tests/test_architecture.py:130` | `ALLOWED_PROTOCOLS` KEY | `"editor_components/editor.py"` -> `"editor_components/view.py"` |
| `tests/test_architecture.py:213` | `UI_FROZEN_FILES` value | `"yate.editor_components.editor"` -> `"yate.editor_components.view"` |
| `tests/test_architecture.py:225` | `UI_FROZEN_FILES` value | same |
| `tests/test_architecture.py:329` | docstring | `editor_components/editor.py` -> `editor_components/view.py` |
| `.trae/rules/architecture-boundaries.md:113` | R2 whitelist text | `editor_components/editor.py::PaneRegistry` -> `editor_components/view.py::PaneRegistry` |
| `.trae/rules/architecture-boundaries.md:347` | historical split note | `editor_components/editor.py` -> `editor_components/view.py` |
| `.trae/wikis/yate-architecture.md:167` | table file cell | `` `editor.py::EditorView` `` -> `` `view.py::EditorView` `` |

The two `UI_FROZEN_FILES` keys (`flows/completion_flows.py:208`,
`flows/mouse_flows.py:223`) stay unchanged: only their allowed-set values move.
`ALLOWED_PROTOCOLS` value `{"PaneRegistry"}` stays unchanged. No class,
function, constant, widget id or CSS selector is renamed.

### Step B4 -- negative drills (two guards)

Drill B4.1 (R2 path whitelist):
1. In `tests/test_architecture.py`, temporarily change the
   `ALLOWED_PROTOCOLS` key back to `"editor_components/editor.py"`; verify on
   disk.
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_new_protocols -q`
   MUST fail and name `editor_components/view.py` / `PaneRegistry`.
3. Restore the new key, clear `tests/__pycache__`, re-run -> exit code 0.

Drill B4.2 (R11 frozen surface):
1. Temporarily change ONE `UI_FROZEN_FILES` allowed value back to
   `"yate.editor_components.editor"` (e.g. the `flows/completion_flows.py`
   set); verify on disk.
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_collaborators_keep_widget_coupling_frozen -q`
   MUST fail: `flows/completion_flows.py` really imports
   `yate.editor_components.view`, which is then absent from `allowed`.
3. Restore, clear `tests/__pycache__`, re-run -> exit code 0.

Finish both with `git status --short` showing only the intended wave-2 diff.

### Step B5 -- acceptance

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_app_panes.py tests/test_dispatch_guards.py tests/test_panes.py tests/test_support_mouse.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
git grep -n -E "editor_components\.editor|editor_components/editor" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

All exit code 0; the last grep prints nothing (no-match exit code 1 is the
expected signal and must be recorded as such).

### Step B6 -- commit and rename check

```powershell
git add -A
git commit -m "refactor(editor-components): rename editor module to view"
git --no-pager log --follow --oneline -- yate/editor_components/view.py
```

`git log --follow` must show the pre-rename history of the widget module.

## 4. Risks / rollback

- Guard sets keyed by old path are the top risk; drills B4.1/B4.2 prove them
  live, and pyright + full pytest catch any missed import.
- `yate/resources/editor-view.tcss` name is intentionally unchanged (issue
  non-goal: no class/asset renames beyond the module path).
- Rollback: `git revert <wave-2 commit>` after reverting wave 3 if needed.

## 5. Backfill (filled during execution)

Real command results, exit codes, both drill outcomes, deviations.
