# IKSFS7 plan-d — bilingual manuals + smoke regression (wave-2)

Main plan: [`../iksfs7-plan.md`](../iksfs7-plan.md) · wave table:
[`overview.md`](overview.md). Run from the `../yate-iksfs7` worktree root.
**Depends on plan-a**: the smoke assertion only passes once `:enew FILE` stops
creating a buffer (wave-1 gate).

## 1. Input

- Issue notes [`../iksfs7-issue-notes.md`](../iksfs7-issue-notes.md) §3 expected behavior.
- Main plan §2 facts F16/F19, §3 decision D, §6 risk table.
- `.trae/rules/doc-conventions.md` §三 (bilingual manual pairs must be updated
  together), §五 (relative paths inside `.trae/` markdown), root-level
  `CHANGELOG*.md` are generated — do not touch them.

## 2. Exclusive files

- `yate/resources/manual.en.md`
- `yate/resources/manual.zh.md`
- `yate/docs/lsp.en.md`
- `yate/docs/lsp.zh.md`
- `tools/smoke_test/scenarios/aliases.py`
- `tools/smoke_test/smoke_baselines/command_alias_roundup.json`

No product Python source, no other scenario files, no other baselines, no
`.trae/**` edits.

## 3. Manual updates (English and Chinese pairs, same content)

### 3.1 `:enew` command row

- `yate/resources/manual.en.md:774` (`:enew` row) — replace the description
  with: `New empty buffer (no arguments; also dismisses the welcome page for this session). `:enew FILE` is rejected with a usage warning — use `:e FILE` to open/create a named buffer or `:saveas FILE` to name this one`.
- `yate/resources/manual.zh.md:708` — replace with the Chinese equivalent:
  `新建空 buffer（不接受参数，同时关闭欢迎页，本会话不再自动出现）。`:enew FILE` 会给出 usage 警告并被拒绝；要打开/新建带名字的 buffer 请用 `:e FILE`，要给当前 buffer 命名请用 `:saveas FILE``.

Do not change the command cheat-sheet lines (`manual.en.md:1598`,
`manual.zh.md:1433`): `:enew` is still a command and is still listed.

### 3.2 LSP section — unnamed buffers and save-as attach

- `yate/resources/manual.en.md:1417-1418` (after "Merely configuring servers
  spawns nothing; unnamed buffers and non-matching files are completely
  unaffected.") — add: `An unnamed buffer has no file URI, so no server starts and no LSP state is shown for it, even after `:set filetype=`. Once `:saveas FILE` (or the `Save as: ` prompt from `:w`) gives it a path, yate opens it on the matching server automatically.`
- `yate/resources/manual.zh.md:1269` — add the Chinese equivalent after the
  "仅仅配置不会启动任何进程；未命名 buffer 或不匹配的文件完全不受影响。" line:
  `未命名 buffer 没有文件 URI，故不会启动服务器，状态栏也不显示 LSP 状态（即使执行了 `:set filetype=`）。一旦通过 `:saveas FILE`（或从 `:w` 弹出的 `Save as: ` 输入行）补齐路径，yate 会自动把该文档在匹配的服务器上打开。`
- `yate/docs/lsp.en.md:25-28` — after the synchronization/startup paragraph add:
  `A buffer without a path has no document URI: no server starts for it and the status bar shows no LSP state, even when `:set filetype=` selects a configured language. Saving it with `:saveas FILE` (or the unnamed-buffer `Save as: ` prompt) counts as the first open and sends `didOpen`; saving an already-named buffer to a different path closes the old URI and opens the new one.`
- `yate/docs/lsp.zh.md:21-23` — Chinese equivalent:
  `没有路径的 buffer 没有文档 URI：不会为它启动服务器，状态栏也不显示 LSP 状态（即便用 `:set filetype=` 选了已配置的语言）。用 `:saveas FILE`（或未命名 buffer 保存时的 `Save as: ` 输入行）补齐路径后，视为首次打开并发送 `didOpen`；把已命名 buffer 另存到另一路径时，会先关闭旧 URI 再打开新 URI。`
- `yate/docs/lsp.en.md:94-95` and `yate/docs/lsp.zh.md:82-83` — extend the
  existing "unnamed buffers ... unaffected" bullet in both languages with a
  short pointer to the new rule (`see the synchronization section above` /
  `见上文「文档同步」段`), without duplicating the whole paragraph.

Manual prose is user-facing, so Chinese in `*.zh.md` and English in `*.en.md`
are both allowed (misc-rules §四 only constrains code comments/docstrings).
Keep relative links unchanged; do not add absolute machine paths.

### 3.3 Smoke scenario `tools/smoke_test/scenarios/aliases.py:60-67`

In `_command_alias_roundup`, immediately after the existing bare `:enew`
check, add:

```python
await run_command(pilot, "enew test.py")
checks.append(Check("enew_rejects_args", 2, len(app.editor.session.docs)))
```

The existing `await run_command(pilot, "bd")` then drops the count back to 1,
so an accidentally accepted argument would also break the following
`bd` check — the two assertions together pin "no buffer created". Update the
scenario docstring's command list to mention the rejected-argument case in
English. `Check` and `run_command` are already imported in this module; no new
imports, no new scenario registration.

### 3.4 Baseline `tools/smoke_test/smoke_baselines/command_alias_roundup.json`

Regenerate **only** this baseline with `snapshot --scenario
command_alias_roundup` (the CLI's `--scenario` filter is repeatable and
`write_baselines` only writes the produced results, so other baselines stay
untouched). The JSON must gain exactly one check object:

```json
{
  "label": "enew_rejects_args",
  "expected": 2,
  "actual": 2,
  "ok": true
}
```

Verify with `git diff -- tools/smoke_test/smoke_baselines/` that no other
baseline file changed and that no SVG rows were added (`--with-svg` is off by
default).

## 4. Acceptance commands (copy-paste, from worktree root)

```powershell
.venv\Scripts\python.exe -m tools.smoke_test snapshot --scenario command_alias_roundup
.venv\Scripts\python.exe -m tools.smoke_test compare --scenario command_alias_roundup
.venv\Scripts\python.exe -m tools.smoke_test run --scenario command_alias_roundup --jobs 1
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
git diff --check
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; en=Path('yate/resources/manual.en.md').read_text(encoding='utf-8'); zh=Path('yate/resources/manual.zh.md').read_text(encoding='utf-8'); assert 'no arguments' in en and '不接受参数' in zh; print('bilingual :enew rows synced')"
```

Pass criteria: `snapshot`/`compare`/`run` exit 0, `compare` prints no DRIFT,
`run --jobs 4` reports no failed scenarios, `git diff --check` exits 0,
architecture suite 37 passed, and the bilingual assertion prints
`bilingual :enew rows synced`. Note `run --jobs 4` is also the step-7 gate
command; running it here does not replace the main agent's final gate.

## 5. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| `snapshot --scenario command_alias_roundup` | one baseline regenerated (`enew_rejects_args` added) | 0 |
| `compare --scenario command_alias_roundup` | `MATCH 18/18` (main-agent independent rerun) | 0 |
| `run --scenario command_alias_roundup --jobs 1` | passed | 0 |
| `run --jobs 4` | **deferred** to step 7 (see deviations); main agent executed it there: `121/121 scenarios`, `1464/1464 checks`, exit 0 | 0 (step 7) |
| `git diff --check` | clean | 0 |
| `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| bilingual check | `bilingual :enew rows synced` | 0 |

Deviations (one, evidence-backed): the full `run --jobs 4` was deferred from
wave-2 because a parallel wave-2 member was running Textual pilots at the same
time (`subagent-workflow.md` §三.3 concurrency interference). It was executed
by review round 1 (`121/121`) and again by the main agent in the step-7 gate
(`121/121`, `1464/1464 checks`), so no gate was skipped — only its timing moved.
No other baseline file or SVG row changed.

## 6. Risks and rollback

- Risk: regenerating the baseline silently changes unrelated checks. Mitigated
  by the single-scenario filter and the `git diff` review in §3.4/§4; if any
  other check value changes, stop and report instead of accepting the drift.
- Risk: the new `:enew test.py` smoke step leaves a warning on the message line
  that changes later SVG snapshots. The baseline stores checks only (SVG rows
  are off by default), and the scenario exits the command line after each
  `run_command`; `compare` and full `run` verify this.
- Risk: English/Chinese manuals drift. Mitigated by the paired edits in §3 and
  the bilingual assertion.
- Rollback: revert this wave's commit (source scenario + the one baseline +
  four manuals); plan-a/b/c behavior is unaffected.
