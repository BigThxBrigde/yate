# IKSFS7 plan-a — `:enew` must reject arguments (wave-1)

Main plan: [`../iksfs7-plan.md`](../iksfs7-plan.md) · wave table:
[`overview.md`](overview.md). Run from the `../yate-iksfs7` worktree root.

## 1. Input

- Issue notes [`../iksfs7-issue-notes.md`](../iksfs7-issue-notes.md) §1 problem 1, §3 expected behavior.
- Main plan §2 facts F1/F2/F3/F17, §3 decision A, §6 risk table.
- Rules: `.trae/rules/python-coding-style.md`, `.trae/rules/architecture-boundaries.md`
  §五 checklist (R5/R7: `commands.py` is the L3 built-in table),
  `.trae/rules/misc-rules.md` §四 (English comments/docstrings).

## 2. Exclusive files

- `yate/commands.py` (write)
- `tests/test_cmd_enew.py` (new file)

All other files are read-only. No `yate/resources/**`, no `tests/test_architecture.py`,
no `tools/**`, no `.trae/**` edits.

## 3. Concrete changes

### 3.1 `yate/commands.py:344-345` — `_enew`

Current:

```python
def _enew(args: str) -> None:
    editor.document_flows.new_buffer()
```

Replace with (exact wording, it is asserted by the tests):

```python
def _enew(args: str) -> None:
    if args.strip():
        editor.message(
            "usage: :enew takes no arguments; use :e FILE to open/create a "
            "named buffer or :saveas FILE to name this buffer",
            kind="warn",
        )
        return
    editor.document_flows.new_buffer()
```

Rationale: `editor.message(..., kind="warn")` is the command table's usage-error
channel (F2); no exception, no new buffer, no state change. Do **not** call
`_strip_quotes` here — a quoted `"test.py"` is still an argument and must be
rejected. Keyword import/type changes: none; `args` stays `str`, return stays
`None`.

### 3.2 `yate/commands.py:383` — registration description

Current:

```python
reg("enew", _enew, "open a new empty buffer")
```

Replace with:

```python
reg("enew", _enew, "open a new empty buffer (no arguments)")
```

No `arg_completer` is added: there is nothing to complete for a zero-argument
command. Do not add a new command or alias.

### 3.3 `tests/test_cmd_enew.py` — new headless test module

Follow the headless pattern of `tests/test_cmd_cd.py:61-115`: a stub editor with
`document_flows` and `message(text, kind)`, a real `CommandRegistry`, and
`register_commands(registry, cast(Any, editor))`. Use `from __future__ import
annotations`, full annotations, module/class/function docstrings in English,
absolute imports, no relative imports, no `TYPE_CHECKING`, no bare `except`.

Fixture shape (implementation detail, names may be adapted but behavior is
fixed):

- `_RecordingFlows.new_buffer()` appends one marker to `self.new_buffer_calls`;
- `_EnrewEditor.message(text: str, kind: str = "info")` appends `(text, kind)`
  to `notes`;
- `_fixture()` returns the registry entry for `"enew"` plus both recorders.

Exact test cases (`test_<behavior>_<condition>_<expected>`):

| # | Test name | Arrange / Act | Assert (concrete values) |
|---|---|---|---|
| 1 | `test_enew_without_arguments_creates_one_unnamed_buffer` | fresh fixture; `entry.fn("")` | `new_buffer_calls == 1`; `notes == []` |
| 2 | `test_enew_with_whitespace_only_arguments_creates_one_unnamed_buffer` | fresh fixture; `entry.fn("   \t ")` | `new_buffer_calls == 1`; `notes == []` |
| 3 | `test_enew_with_filename_warns_and_creates_no_buffer` | fresh fixture; `entry.fn("test.py")` | `new_buffer_calls == 0`; `notes == [("usage: :enew takes no arguments; use :e FILE to open/create a named buffer or :saveas FILE to name this buffer", "warn")]` |
| 4 | `test_enew_with_quoted_filename_warns_and_creates_no_buffer` | fresh fixture; `entry.fn('"test.py"')` | `new_buffer_calls == 0`; same single warn note as #3 |
| 5 | `test_enew_registration_description_states_no_arguments` | fresh fixture; `entry.description` | `"no arguments" in entry.description` and `"open a new empty buffer" in entry.description` |

Negative drill (required for the guard semantics): before editing the product
code, temporarily run case #3 against the current `_enew` and confirm it fails
(`new_buffer_calls == 1`, `notes == []`); then apply the edit and confirm green.
Record both results in §6.

## 4. Output

- No silently dropped `:enew` argument; zero-argument `:enew` behavior unchanged.
- 5 headless tests pinning the guard, the exact warning text and the
  registration description.
- No new import edge, no changed architecture guard surface.

## 5. Acceptance commands (copy-paste, from worktree root)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cmd_enew.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py tests/test_set_options.py tests/test_action_table.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/commands.py').read_text(encoding='utf-8').splitlines()))"
```

Pass criteria: all pytest/pyright commands exit 0; pyright reports 0 errors;
architecture suite still 37 passed; `yate/commands.py` stays below 800 lines
(§三.7). If `-n auto` reports a failure, re-run that test with `-n 1` and fix a
real timing assumption before declaring success.

## 6. Execution record (fill in with real numbers)

| Command | Result | Exit code |
|---|---|---|
| negative drill (case #3 before edit) | pending | — |
| `pytest tests/test_cmd_enew.py -q` | pending | — |
| `pytest ... -n auto` | pending | — |
| `pyright ...` | pending | — |
| `pytest tests/test_architecture.py -q` | pending | — |
| line count `yate/commands.py` | pending | — |

Deviations: none recorded yet — any change to the warning text, the file list
or the test list must be written here with evidence.

## 7. Risks and rollback

- Risk: an external keymap/extension invokes `:enew something` and now sees a
  warning instead of a new buffer. Mitigation: no shipped binding does so
  (F16/F17); the warning is non-destructive and points at `:e FILE` /
  `:saveas FILE`.
- Risk: exact-string assertion couples tests to wording. Accepted: the wording
  is the user-visible contract of this fix; a deliberate wording change must
  update both the code and the table in §3.3.
- Rollback: `git revert` of this wave's commit restores `yate/commands.py` and
  deletes `tests/test_cmd_enew.py`; no other plan depends on the new file.
