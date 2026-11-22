# Issue IKX5EP brief (source material, no analysis)

Source: https://gitee.com/jermaine/yate/issues/IKX5EP
Created: 2026-11-22 18:08; status: open; labels: feature, enhancement; milestone: P0.

## Title

ENH - 补齐 LSP 导航与交互能力：DEFINITION / HOVER / OUTLINE / REFERENCES / RENAME / CODE ACTIONS / SIGNATURE HELP

## Goal / priority

| Priority | Capability | Target |
|---|---|---|
| P0 | Go to Definition (`gd`) | Jump to symbol definition; cross-file; LocationLink target range |
| P1 | Hover popup (`K`) | Add `K` showing hover, reuse existing hover card; keep `<f7>` |
| P2 | Document Symbols / Outline | List current document symbol tree; select to jump |
| P3 | Find References (`gr`) | List references with file path and position; navigate from list, cross-file |
| P4 | Rename | Rename symbol, apply LSP workspaceEdit |
| P5 | Code Actions | List and apply server code actions (including quickfix) |
| P6 | Signature Help | Show parameter signature popup at call site |

Staged delivery allowed in priority order.

## Acceptance criteria (verbatim intent)

Setup: pyright-langserver; a test project with at least two Python files (A defines function/class, B imports and calls it).

- AC1 (P0, must): at a call site in B press `gd`, jump to definition in A; LocationLink target range accurate when returned; no definition provider -> explicit message, no silent failure, no exception.
- AC2 (P1, must): press `K` on a symbol -> hover popup with same content as `<f7>`; `<f7>` remains usable; vsc and vim keymap tables both bind `K` identically and an architecture guard prevents single-side drift.
- AC3 (P3, must): press `gr` -> reference list showing file path and position; Enter/click navigates, including A<->B cross-file; no references -> explicit state, no crash.
- AC4 (P2): document outline/document symbols list, items jump to location; graceful degradation when unsupported.
- AC5 (P4): rename applies server result; server failure/uneditable location -> message, no half-applied state.
- AC6 (P5/P6): code actions and signature help can be listed/displayed; unsupported server -> no error, no editing blockage.
- AC7 (all): requests are async, waiting never blocks input; Cancel / document close / timeout must not leave dangling callbacks.
- AC8 (engineering): pyright zero diagnostics, full pytest green, architecture tests green; new keys in both vsc/vim tables with shared-constant guard; `yate/docs/lsp.zh.md` and `lsp.en.md` updated bilingually; in-app manual updated if user-visible keys change.

## Boundaries and compatibility

- LSP protocol capabilities only; do not install/package language servers; pyright is only the acceptance server.
- Keep existing completion / diagnostics / `<f7>` hover behavior unchanged; `K`, `gd`, `gr` are new bindings and must not conflict with existing keys.
- `hoverProvider` is a server capability; client only declares `hover.contentFormat`.
- Server capabilities gate each feature; missing capability degrades with a message.
- Known risk: pyright may echo drive letter encoded as `d%3A` in URIs, mismatching local `path_to_uri` (existing publishDiagnostics location issue). Navigation must use one shared URI-to-path mapping; do not fix only one site.
- Architecture: LSP request封装 in `editor_lsp` leaf package, flow orchestration in L3 `flows/*_flows.py`, UI components in `editor_components`; no new `Protocol` / `TYPE_CHECKING`; flow modules hold no App handle; new component ids / themes / scrollbars follow the rules.

## Non-goals

- No tree-sitter/regex local symbol index as the navigation path (existing completion buffer fallback is not extended).
- No multi-root workspace symbol search; outline is current-document only.
- No global rename preview panel, no code-action keybinding customization, no rich-text template system for signature popup.
- No rewrite of LSP connection management, incremental sync, or highlight cache architecture.

## Reference locations

- `yate/editor_lsp/client.py`: initialize capability declaration
- `yate/editor_lsp/manager.py`: request wrappers (`request_completion` / `request_hover` as templates)
- `yate/flows/lsp_sync.py`: LSP event / diagnostics wiring
- `yate/keymaps/keys.py`, `yate/keymaps/vim.py`, `yate/keymaps/vsc.py`: shared key constants and binding tables
- `yate/docs/lsp.zh.md`, `yate/docs/lsp.en.md`: bilingual capability docs
