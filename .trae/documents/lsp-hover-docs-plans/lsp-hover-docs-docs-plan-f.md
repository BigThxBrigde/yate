# Plan f — bilingual documentation (wave-2, docs)

Parent: [overview.md](overview.md) · Main plan: [../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md), decisions D1 / D7

## Input

- `yate/docs/lsp.en.md:11-23` and `yate/docs/lsp.zh.md:10-19` (client
  capability bullet lists; currently autocomplete + diagnostics only).
- `yate/resources/manual.en.md:354-390` (§5.1 vsc), `:1345-1367` (§16 LSP),
  `:1583-1604` (§18 cheat sheet); the vim subsection of §5 (read it first).
- `yate/resources/manual.zh.md:322-357` (§5.1 vsc), `:1202-1219` (§16 LSP),
  `:1409-1430` (§18 cheat sheet); the vim subsection of §5.
- `FEATURES.md:118-128`, `FEATURES.zh.md:98-104` (§11 LSP bullet lists).
- `doc-conventions.md` §三 (`.en.md` / `.zh.md` pairs must be updated together),
  §五 (relative in-repo paths, no machine-local absolute paths).

## Deviation registered

AC7 names `FEATURES.en.md`; at baseline that file does not exist. The English
feature list is `FEATURES.md`. Update `FEATURES.md` + `FEATURES.zh.md` and note
the deviation in the final report.

## Exclusive files

- `yate/docs/lsp.en.md`, `yate/docs/lsp.zh.md`
- `yate/resources/manual.en.md`, `yate/resources/manual.zh.md`
- `FEATURES.md`, `FEATURES.zh.md`
- `tests/test_hover_docs.py` (new)

No product code, no `.trae/` documents.

## Concrete changes (all six files, same facts)

Facts to state in both languages:

1. One new capability: **LSP hover documentation**. Shortcut **`F7`**
   (`<f7>` in key notation) — the **same key in vsc and vim**, no per-keymap
   default, no chord. It shows the API docs for the symbol at the cursor.
2. Mouse hover: with `support_mouse` enabled, resting the pointer on a symbol
   shows the same card after a short debounce; moving away, moving the cursor,
   typing or `Esc` dismisses it. With `support_mouse` off the path is disabled.
3. **No documentation → absolutely nothing is shown**: no card, no
   "No documentation" placeholder, no message-bar/status-bar hint, no flash.
   This also covers a server that is not started / not ready / has no server
   configured for the language, or a failed/timed-out request.
4. The card shows the signature and docstring returned by the server; it never
   changes focus, never swallows other keys, and never starts a server or
   changes synchronization.
5. Rebinding: extensions can use `bind_key(..., keymap="both")` to change the
   key once for both keymaps; overriding only one keymap is an explicit user
   choice.

Edit points:

- `lsp.en.md` / `lsp.zh.md`: add a third capability bullet next to
  Autocomplete/Diagnostics and one short paragraph under the synchronization
  section explaining "hover is request-only, no didOpen/didChange".
- `manual.en.md` / `manual.zh.md`: add `| \`F7\` | Show API documentation at
  cursor |` (zh: `| \`F7\` | 显示光标处 API 文档 |`) to **both** keymap tables
  (§5.1 vsc and the vim subsection) with the identical key value; add a hover
  bullet in §16; add one row to the §18 four-column cheat sheet writing `F7` in
  **both** key columns with the same action text.
- `FEATURES.md` / `FEATURES.zh.md`: add one bullet to §11 mentioning `F7`,
  mouse hover and the silent-when-empty behavior.
- Never write `Ctrl+K` / `Ctrl+Shift+K` as the hover key anywhere (D1), never
  write a machine-local path, keep the existing table alignment and heading
  numbering.

## Tests (`tests/test_hover_docs.py`)

Path resolution: `ROOT = Path(__file__).resolve().parents[1]`; no hard-coded
home directory. Read each file as UTF-8 text.

| Test | Arrange / Act | Assert |
| --- | --- | --- |
| `test_lsp_docs_both_languages_describe_hover_and_f7` | read `lsp.en.md`, `lsp.zh.md` | each contains `F7` and `hover` (en) / `悬停` or `hover` (zh) |
| `test_lsp_docs_both_languages_describe_silent_empty_behavior` | same texts | en contains "no documentation"/"nothing is shown"; zh contains "无文档"/"不显示" |
| `test_manual_both_languages_put_the_same_key_in_vsc_and_vim_sections` | slice §5 of each manual | `F7` appears at least twice in each §5 slice and no `Ctrl+K`-as-hover row exists |
| `test_manual_cheat_sheet_uses_identical_f7_in_both_key_columns` | read §18 slices | the hover row contains `F7` twice (four-column table) in each language |
| `test_manual_lsp_sections_describe_mouse_hover_and_silence` | §16 slices | en/zh mention mouse hover and the silent-empty rule |
| `test_features_both_languages_mention_hover_and_f7` | `FEATURES.md`, `FEATURES.zh.md` | each contains `F7` and the LSP section index |
| `test_docs_never_present_ctrl_k_as_the_hover_key` | all six texts | no line matches a hover sentence containing `Ctrl+K` / `ctrl-k` |
| `test_docs_contain_no_machine_local_absolute_paths` | all six texts | no `C:\Users\`, `/home/`, `/Users/` prefix in added lines (use a regex on the whole files, matching the architecture guard's pattern) |

## Acceptance commands

```powershell
cd D:/Programming/yate-lsp-hover-docs
.venv\Scripts\python.exe -m pytest tests/test_hover_docs.py -q -n 1
```

Exit code 0. Main-agent wave-2 gate additionally runs full pyright (the new
test file is in `tests/`) and the architecture suite (pure docs are exempt
from the gate under `misc-rules.md` §三, but this wave also contains code).

## Risks and rollback

- Risk: manual table alignment / markdown lint. Keep the existing column
  counts; do not reflow unrelated rows. If `pymarkdownlnt` complains about a
  new line, fix that line only and report it.
- Risk: §5 vim subsection may use a different heading than assumed. Read the
  actual file and insert the row into the real vim table; the test slices §5
  generically, so the exact heading is not hard-coded.
- Rollback: revert this commit; no code depends on the docs, and the
  consistency test is removed with it.
