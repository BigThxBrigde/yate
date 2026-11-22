# LSP navigation and interaction implementation plan (IKX5EP)

Source brief: [lsp-navigation-issue-brief.md](lsp-navigation-issue-brief.md).
Worktree: `<repo-parent>/yate-lsp-navigation` (relative to the main checkout);
branch `feature/enh-lsp-navigation`; parent `master` at `c6d6e89a`
(synced with `origin/master`).

## 1. Goal and non-goals

Goal: implement P0-P6 in value order with acceptance AC1-AC8 from the issue:
`gd` definition (cross-file, LocationLink), `K` hover (keep `<f7>`), document
symbols/outline, `gr` references with navigable list, rename via workspaceEdit,
code actions, signature help; all async with explicit capability degradation.

Non-goals: installing/packaging language servers, tree-sitter/regex navigation
backend, multi-root workspace search, rename preview panel, code-action key
customization, rich signature templates, LSP connection/incremental-sync rewrite.

## 2. Key facts from code survey (evidence)

- `yate/editor_lsp/client.py:211,249-255`: server capabilities from `initialize`
  live only in `LspClient.server_capabilities`; no manager-level provider check.
- `client.py:417-441,453-460,512-556`: `start_request` / `send_cancel` /
  `settle_request` already support async request lifecycle; `request_hover`
  (`manager.py:656-704`) is the passive-request template.
- `manager.py:893` lines (SIZE_EXEMPT_FILES); `_ready_client_for` (`:259-284`),
  `_uri` (`:881-889`), `handle_notification` (`:718-749`) are the shared seams.
- `protocol.py:137-185`: `uri_to_path` already decodes `%3A`; the real mismatch
  is that pyright echoes a drive-escaped URI while manager keys diagnostics by
  the raw `params["uri"]` (`tests/test_lsp_real_server.py:182-184`).
- `keymaps/keys.py:57-86`: shared L0 key constants; `parse_key("<shift-k>")`
  normalizes to `K` (`keys.py:124-183`). Vim normal-mode `g` prefix resolution
  is at `vim.py:861-916`, extension-binding fallback at `vim.py:1095-1097`.
- `tests/test_architecture.py:1666-1701`: exact AST+runtime guard pattern for
  shared keys; `:199-260` `UI_FROZEN_FILES`; `:391-399` line-count table.
- `editor_components/marks_palette.py:59-119`: overlay chooser pattern to reuse;
  `hover_popup.py:72-79` is the existing hover card API.
- `actions.py:267-268`: action registration; `editor_compose.py:250-257,304-311`
  is the flow-injection point.

## 3. Design decisions and rejected alternatives

- **New L0 `editor_lsp/navigation.py` for all new request/parse logic** instead
  of growing `manager.py`: manager stays a thin delegator; navigation helpers
  are pure functions over `LspClient`, uri and position, testable without UI.
  Rejected: adding 6 request methods plus parsers directly to `manager.py`
  would push an already-exempt 893-line module past 1000 lines and mix protocol
  parsing with state orchestration.
- **Canonical URI at the boundary** (`protocol.canonical_uri`): normalize every
  incoming/outgoing URI through `uri_to_path` + `path_to_uri`. Rejected: patching
  only diagnostics or only definition would leave the same mismatch elsewhere.
- **Vim chords `gd`/`gr`; vsc single keys `<alt-g>` / `<alt-r>`**; all four plus
  `<shift-k>` are shared constants in `keymaps/keys.py`. Rejected: F12 for
  definition (already bound to macro replay, `keys.py:66`) and multi-key chords
  in vsc (keymap table only handles single raw keys).
- **One generic L2 chooser screen** (`editor_components/lsp_chooser.py`) for
  definition-multi / references / outline / code-actions, driven by pure rows +
  callbacks. Rejected: four bespoke screens would duplicate R13/R15 wiring.
- **Signature help reuses `HoverPopup`** with formatted markdown. Rejected: a
  new popup widget would add a second id/theme/scrollbar surface for no benefit.
- **WorkspaceEdit application in the L3 flow**, with pre-validation and buffer
  snapshots for rollback. Rejected: applying from L0 would violate layering;
  skipping rollback would break AC5.

```mermaid
flowchart TD
    K["keymaps: gd/gr/K"] --> A["actions.py: action names"]
    A --> F["L3 flows/lsp_navigation_flows.py"]
    F --> M["L0 editor_lsp/manager.py (thin wrappers)"]
    M --> N["L0 editor_lsp/navigation.py (requests + parsing)"]
    N --> C["LspClient: start_request/settle/cancel"]
    F --> U["L2 editor_components/lsp_chooser.py"]
    F --> H["L2 hover_popup.py (signature help)"]
    F --> D["DocumentFlows: open_path/activate_doc"]
    U --> O["OverlayFlows.push"]
```

## 4. Sub-plans and waves

| Wave | Sub-plan | Files (exclusive) | Depends on |
|---|---|---|---|
| 1 | [a: LSP request layer](lsp-navigation-plans/lsp-navigation-request-layer-plan-a.md) | `editor_lsp/navigation.py` (new), `editor_lsp/protocol.py`, `editor_lsp/manager.py`, `tests/test_lsp_navigation.py` (new) | — |
| 1 | [b: keys and actions](lsp-navigation-plans/lsp-navigation-keys-plan-b.md) | `keymaps/keys.py`, `keymaps/vim.py`, `keymaps/vsc.py`, `actions.py`, `tests/test_lsp_navigation_keys.py` (new) | — |
| 2 | [c: chooser component](lsp-navigation-plans/lsp-navigation-chooser-plan-c.md) | `editor_components/lsp_chooser.py` (new), `tests/test_lsp_chooser.py` (new) | a? no; b? no |
| 3 | [d: flow and wiring](lsp-navigation-plans/lsp-navigation-flow-plan-d.md) | `flows/lsp_navigation_flows.py` (new), `editor_compose.py`, `editor.py`, `tests/test_lsp_navigation_flows.py` (new) | a, b, c |
| 4 | [e: guards, docs, smoke, real-server AC](lsp-navigation-plans/lsp-navigation-guards-docs-plan-e.md) | `tests/test_architecture.py`, `.trae/rules/architecture-boundaries.md`, `docs/lsp.{zh,en}.md`, `resources/manual.{zh,en}.md`, `tools/smoke_test/scenarios/lsp_navigation.py` (new), `scenarios/__init__.py`, `tests/test_lsp_real_server.py` | a-d |

Wave 1 runs a ∥ b (file-disjoint); wave 2 runs c alone; wave 3 runs d alone;
wave 4 runs e alone. Waves are serial: each wave's acceptance commands must
exit 0 before the next starts. Wave reordering is forbidden without a recorded
measured reason in this document.

## 5. Risks and rollback

- **Capability semantics**: `renameProvider` / `codeActionProvider` may be
  objects, not booleans. `supports_feature` must treat `False`/`None`/missing as
  unavailable, everything else as available; negative tests cover each shape.
- **Stale results / doc identity**: every flow worker snapshots token + doc path
  + cursor before spawning, following `HoverFlows._stale` (`hover_flows.py:190`).
- **WorkspaceEdit failure**: pre-validate all target files first, snapshot each
  buffer, apply edits bottom-up; on exception restore snapshots. Never write to
  disk automatically; unopened targets are opened as new buffers.
- **File-size guards**: editing `keymaps/vim.py`, `editor.py` and
  `editor_lsp/manager.py` changes measured `splitlines()` counts; plan e measures
  and syncs `.trae/rules/architecture-boundaries.md` §三.7 table and
  `tests/test_architecture.py::SIZE_EXEMPT_LINE_COUNTS` in both places.
- **Rollback**: each wave is one or more commits on the feature branch; revert
  the wave's commits if acceptance fails and redesign. No force push, no merge
  to master until review and gates pass.

## 6. Approval and gates

User instruction on 2026-11-22 puts the session in unattended mode with no
questions; the plan-approval step is therefore auto-approved (recorded here),
with all review and gate requirements unchanged. Final gates are run by the
main agent: pyright, `pytest -n auto`, architecture tests, coverage >= 75,
smoke `--jobs 4`, plus a documented real-pyright two-file navigation check.
