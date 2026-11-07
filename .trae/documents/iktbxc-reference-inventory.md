# IKTBXC reference-surface inventory (facts only, no design)

Collected by a read-only `code-explorer` sweep over worktree `yate-iktbxc`
(master `3e92532`), plus coordinator spot-checks. Intended as the single factual
input for the plan designer. No analysis, no proposed design.

## A. Counts of lines containing each old path string

| Old path string | yate code | tests | tools | rules | wikis | reviews | documents | README | tcss | total |
|---|---|---|---|---|---|---|---|---|---|---|
| `keyproto.legacy` / `keyproto/legacy` / `legacy.py` | 6 | 3 | 0 | 1 | 3 | 4 | 101 | 0 | 0 | 118 |
| `editor_components.editor` / `editor_components/editor` | 14 | 9 | 1 | 2 | 0 | 1 | 8 | 0 | 1 | 36 |
| `flows.cmdline_completions` / `flows/cmdline_completions` / bare `cmdline_completions` | 6 | 11 | 1 | 6 | 3 | 0 | 62 | 2 | 0 | 91 |

- Bare import forms `from yate.editor_components import editor`,
  `from yate.keyproto import legacy`, `from yate.flows import cmdline_completions`
  occur **0 times**.
- `CHANGELOG*.md`, `yate/resources/changelog.*.md`,
  `tools/changelog/zh_overrides.json`: **0** old-path hits.
- `.trae/documents/**` historical plans: 101 + 8 + 62 = 171 lines. Issue §六
  explicitly exempts them from the residual grep.
- `.trae/reviews/**` are read-only fact records per `doc-conventions.md` §2.1.
- `pack/` (7 files incl. two `.spec`), `pyproject.toml`, all `*.json` under
  `yate/` + `tools/`, all `*.scm`, all `yate/docs/**`, `yate/resources/manual*.md`:
  **0** old-path hits.

## B. Old path 1 -- `yate.keyproto.legacy`

Product code (6): `yate/app.py:30`, `yate/editor_dispatch.py:23`,
`yate/editor_dispatch.py:123` (comment), `yate/editor_term/keys.py:4` (docstring),
`yate/editor_term/keys.py:12`, `yate/keyproto/__init__.py:13`.
Tests (3): `tests/test_app_textual.py:23`, `tests/test_term_keys.py:12`,
`tests/test_keyproto.py:30`.
Rule text (1): `.trae/rules/architecture-boundaries.md:47`.
Wiki (3): `.trae/wikis/yate-architecture.md:156`, `:184`, `:194` (Mermaid
participant).
Reviews (4) / historical plans (101): exempt from back-edit.

`yate/keyproto/legacy.py:1-7` docstring literally starts "Legacy key codec:
translation from Textual key names to the raw byte sequences..." and continues
"Formerly ``yate.editor_components.keys``; moved into the L0 leaf package...".
The module imports only `from yate.keymaps.keys import SPECIAL_KEYS` (`:11`).
No `key_codec.py` exists in `yate/keyproto/` (directory: `__init__.py`,
`aliases.py`, `chords.py`, `driver_windows.py`, `frames.py`, `legacy.py`,
`textual_internals.py`).

## C. Old path 2 -- `yate.editor_components.editor`

Product code (14): `yate/editor.py:61`, `yate/editor_dispatch.py:19`,
`yate/session.py:272` (comment), `yate/editor_components/__init__.py:5` and `:26`,
`yate/editor_components/welcome.py:3`, `highlighting.py:3`, `panes.py:24` and
`:40`, `terminal.py:40`, `completion.py:4`, `yate/flows/mouse_flows.py:3` and
`:19`, `yate/flows/completion_flows.py:24`.
Style resource (1): `yate/resources/editor-view.tcss:2` (CSS comment).
Tests (9): `tests/test_app_mouse.py:22`, `test_app_panes.py:16`,
`test_dispatch_guards.py:19`, `test_panes.py:26`, `test_support_mouse.py:31`,
`tests/test_architecture.py:130` (`ALLOWED_PROTOCOLS` **key**), `:213` and `:225`
(`UI_FROZEN_FILES` **allowed-set values**, not keys), `:329` (docstring).
Tools (1): `tools/smoke_test/scenarios/multi_cursor.py:18`.
Rules (2): `.trae/rules/architecture-boundaries.md:113`, `:347`.
Reviews (1) / historical plans (8): exempt from back-edit.

`yate/editor_components/editor.py` holds `PaneRegistry(Protocol)` at `:50` and
`EditorView` at `:74`; `DEFAULT_CSS = load_tcss("editor-view.tcss")` at `:90`.
No `view.py` / `text_view.py` exists in `yate/editor_components/`
(directory listing confirmed). `yate/editor_compose.py` contains **no**
`editor_components.editor` reference (issue's "22 sites" list is stale there).

Guard facts in `tests/test_architecture.py`:
- `ALLOWED_PROTOCOLS:129-133` maps `"editor_components/editor.py": {"PaneRegistry"}`
  and is consumed by `test_no_new_protocols:592-598` via
  `ALLOWED_PROTOCOLS.get(key, set())` where `key` is the `yate/`-relative path.
- `UI_FROZEN_FILES:195-257` has 10 `flows/*.py` keys; `:213` and `:225` are
  elements of the `flows/completion_flows.py` and `flows/mouse_flows.py` allowed
  sets respectively. `test_collaborators_keep_widget_coupling_frozen:827-837`
  asserts every `yate.editor_components*` import is in that file's allowed set.
- `SIZE_EXEMPT_FILES:357-362` does not contain `editor_components/editor.py`.
- `_python_files():480-486` scans `yate/` + `tests/` + `tools/` rglob `*.py`;
  `_yate_files():499-504` scans `yate/` rglob `*.py`; both skip `__pycache__`.

## D. Old path 3 -- `yate.flows.cmdline_completions`

Product code (6): `yate/editor_compose.py:33` (import), `:129` (call),
`yate/flows/cmdline_completions.py:17` (function name, not a path),
`yate/config.py:12` (module docstring), `:290` (`#:` comment),
`yate/services/extensions/api.py:411` (comment).
Tests (11): `tests/test_app_find.py:18`, `:337`, `:475`;
`tests/test_cmdline_completions.py:3`, `:28`, `:72`, `:142`, `:153`;
`tests/test_architecture.py:25` (module docstring), `tests/test_set_options.py:45`
(test name), `tests/test_workspace_filter.py:887` (comment).
Tools (1): `tools/smoke_test/scenarios/guards.py:200` (docstring path string).
Root docs (2): `README.md:272`, `README.zh.md:290` -- both already list the plain
filename `cmdline_completions.py` in the root `yate/` tree (no `flows/` prefix).
Rules (6): `.trae/rules/architecture-boundaries.md:25`, `:133`, `:139`, `:268`,
`:297`, `:457`.
Wikis (3): `.trae/wikis/yate-architecture.md:23`, `:151`, `:159`.
Reviews (0) / historical plans (62): exempt from back-edit.

`yate/flows/cmdline_completions.py` (53 lines) imports exactly:
- `:12 from yate.registries import CommandRegistry`
- `:13 from yate.services.workspace import Workspace, path_matches`
- `:14 from yate.session import EditorSession`

Layer-rank facts (`tests/test_architecture.py`):
- `_LAYER_RANKS:141-158` lists `("flows/", 3)`, `("services/extensions/", 3)`,
  `("editor_components/", 2)`, `("session.py", 1)`, `("registries.py", 1)`,
  `("keymaps/keys.py", 0)`, `("keymaps/", 1)`; unlisted paths default to **0**
  (`_layer_rank:520-525`, docstring at `:135-140` says "anything unlisted ranks
  as L0, which makes a new leaf module reaching upward fail the guard").
- `test_no_unregistered_upward_imports:765-793` collects
  `f"{source} -> {module}"` whenever `_layer_rank(target) > source_rank`, then
  asserts `sorted(set(offenders) - UPWARD_EDGES_FROZEN)` is empty.
- `UPWARD_EDGES_FROZEN:165` = `frozenset()` (empty since 2026-10-20).
- `_ranked_target:528-538` resolves `yate.x.y` to `x/y.py` or `x/y/__init__.py`.

Consequence recorded as a fact (no design): a relocated module whose `yate/`-
relative path is not registered in `_LAYER_RANKS` ranks 0, while
`yate.registries` / `yate.session` rank 1; those two existing imports would then
be reported by `test_no_unregistered_upward_imports` as unregistered upward
edges. The current `flows/` prefix gives the module rank 3, so those imports are
downward today.

Other guard facts:
- `test_flow_modules_hold_no_app_handle` scans `(YATE / "flows").glob("*.py")`
  at `:1315` (plus the `yate/*.py` top-level AST scan); `test_flow_modules...`
  is part of the capability-injection pair.
- `test_source_files_within_size_threshold:896-918` uses `SIZE_EXEMPT_FILES`
  and `_source_files()` (yate + tools, no tests); no exemption mentions any of
  the three old paths.
- `test_no_banned_identifier_names:869-878` is the real name; there is **no**
  `test_banned_identifier_names` (issue text is stale on this).
- `NON_ASCII_COMMENT_EXEMPT:388-405`, `PRINT_EXEMPT_SITES:471-475`,
  `SCROLLABLE_BASES:433-441` do not reference any of the three old paths.

## E. Package `__init__.py` facts

- `yate/editor_components/__init__.py`: no re-exports; `:5` and `:26` mention
  `yate.editor_components.editor.EditorView` / the import example.
- `yate/keyproto/__init__.py`: no re-exports; `:13` lists
  `:mod:yate.keyproto.legacy` as one of three codecs.
- `yate/flows/__init__.py`: only 5 PEP 695 `type` aliases, no re-exports,
  0 `cmdline_completions` references.
- `yate/services/__init__.py`: no re-exports, 0 old-path references.

## F. Smoke baseline

`tools/smoke_test/scenarios/` has 26 `.py` files (24 scenario modules + `_base.py`
+ `__init__.py`); `Scenario(` count = **121**, matching the issue's "121
scenarios". Only 2 files reference old paths (one real import, one docstring).

## G. Issue-claim vs. repository fact discrepancies

| Issue claim | Verified fact |
|---|---|
| `tests/test_architecture.py:213/225` are `UI_FROZEN_FILES` **keys** | They are **allowed-set values**; keys at `:208` / `:223` |
| P0-2 has 22 reference sites incl. `editor_compose.py` | 36 lines total; `editor_compose.py` has 0 such references |
| P0-1 "9 active references" | 9 product/test lines correct; 109 more lines in `.trae` (exempt historical docs / reviews / wikis / rules) |
| P1-3 says `yate/docs` manuals reference the path | 0 hits in `yate/docs/**` and `yate/resources/manual*.md` |
| `tests/test_architecture.py` has "flows enumeration constants" | No `FLOWS` constant; enumerations live in docstring `:24-28`, `UI_FROZEN_FILES` keys, `_LAYER_RANKS:151`, `glob:1315` |
| `test_banned_identifier_names` | Actual name: `test_no_banned_identifier_names` |
| `editor_compose.py:127-133` partial wiring | `PromptBar(` starts `:127`, `partial(` `:128`, `cmdline_completions` `:129`, call ends `:137`; import at `:33` |
