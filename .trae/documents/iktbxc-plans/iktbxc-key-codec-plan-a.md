# Wave-1 sub-plan A: `keyproto/legacy.py` -> `key_codec.py`

Index: [overview.md](overview.md) | main plan: [../iktbxc-plan.md](../iktbxc-plan.md)
Facts: [../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §B.

All paths below are repository-root relative (command basis). Every edit must
be preceded by a `read_file` of the exact region; **no blind global replace**.

## 1. Input / output

Input: `yate/keyproto/legacy.py` (the only active Textual key-name -> raw byte
codec), 9 active references, 1 rule line, 3 architecture-wiki lines.
Output: renamed module `yate/keyproto/key_codec.py` with a docstring that says
"legacy" names the terminal key-name system, not a deprecated layer; all live
references updated; zero runtime behavior change.
Independent commit: `refactor(keyproto): rename legacy key codec to key_codec`.

## 2. Exclusive file list

- `yate/keyproto/legacy.py` -> `yate/keyproto/key_codec.py` (`git mv`)
- `yate/app.py`, `yate/editor_dispatch.py`, `yate/editor_term/keys.py`,
  `yate/keyproto/__init__.py`
- `tests/test_app_textual.py`, `tests/test_term_keys.py`, `tests/test_keyproto.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`

Explicitly NOT touched: `.trae/documents/**` historical plans,
`.trae/reviews/**`, `CHANGELOG*`, `tools/changelog/zh_overrides.json`,
`tests/test_architecture.py` (wave 2 and 3 own it), P2 files.

## 3. Steps

### Step A1 -- baseline (read-only)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py tests/test_term_keys.py tests/test_app_textual.py -q
```

Expected: exit code 0 (37 architecture cases green before any edit).

### Step A2 -- rename

```powershell
git mv yate/keyproto/legacy.py yate/keyproto/key_codec.py
```

Never delete + create. Verify `git status --short` shows a rename (`R`).

### Step A3 -- rewrite the module docstring (first 7 lines of the new file)

Replace the old first line "Legacy key codec: ..." and the "Formerly ..."
paragraph with:

```python
"""Current key codec for legacy terminal key names.

Translates Textual key names into the raw byte sequences yate keymaps use
(control codes / ANSI escape sequences).  "Legacy" here describes the
terminal key-name system those bytes come from, not a deprecated module:
this is the only active codec, shared by the keymaps, the driver layer and
the app from the L0 leaf package.

Formerly ``yate.editor_components.keys``; moved into the L0 leaf package so
keymaps, the driver layer and the app can share one codec without touching
the component package.
"""
```

ASCII-only English (misc-rules.md §四). No code below the docstring changes.

### Step A4 -- exact string edits (read each region first)

| File:line | Old string | New string |
|---|---|---|
| `yate/app.py:30` | `from yate.keyproto.legacy import textual_key_to_raw` | `from yate.keyproto.key_codec import textual_key_to_raw` |
| `yate/editor_dispatch.py:23` | `from yate.keyproto.legacy import event_to_raw` | `from yate.keyproto.key_codec import event_to_raw` |
| `yate/editor_dispatch.py:123` (comment) | `keyproto.legacy maps only single-modifier alt chords` | `keyproto.key_codec maps only single-modifier alt chords` |
| `yate/editor_term/keys.py:4` (docstring) | `:func:\`yate.keyproto.legacy.modified_key_sequence\`` | `:func:\`yate.keyproto.key_codec.modified_key_sequence\`` |
| `yate/editor_term/keys.py:12` | `from yate.keyproto.legacy import modified_key_sequence` | `from yate.keyproto.key_codec import modified_key_sequence` |
| `yate/keyproto/__init__.py:13` | `- :mod:\`yate.keyproto.legacy\` -- Textual key name -> raw byte` | `- :mod:\`yate.keyproto.key_codec\` -- Textual key name -> raw byte` |
| `tests/test_app_textual.py:23` | `from yate.keyproto.legacy import event_to_raw` | `from yate.keyproto.key_codec import event_to_raw` |
| `tests/test_term_keys.py:12` | `from yate.keyproto.legacy import modified_key_sequence` | `from yate.keyproto.key_codec import modified_key_sequence` |
| `tests/test_keyproto.py:30` | `from yate.keyproto.legacy import textual_key_to_raw` | `from yate.keyproto.key_codec import textual_key_to_raw` |
| `.trae/rules/architecture-boundaries.md:47` | `keyproto/legacy.py` | `keyproto/key_codec.py` |
| `.trae/wikis/yate-architecture.md:156` | `` `legacy.py::event_to_raw` `` | `` `key_codec.py::event_to_raw` `` |
| `.trae/wikis/yate-architecture.md:184` | `yate/keyproto/legacy.py` | `yate/keyproto/key_codec.py` |
| `.trae/wikis/yate-architecture.md:194` (Mermaid) | `participant KP as keyproto/legacy<br/>event_to_raw` | `participant KP as keyproto/key_codec<br/>event_to_raw` |

Import order stays alphabetical within its group (`python-coding-style.md`
§1.3); key_codec sorts after keyproto's other modules only where the group
contains them, so re-check each import block.

### Step A5 -- negative drill (naming guard)

1. Append a temporary class `RenameProbeController` to
   `yate/keyproto/key_codec.py` (any trivial body, e.g. `pass`), save, and
   verify on disk.
2. Run `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_banned_identifier_names -q`.
   It MUST fail (exit code != 0) with an assertion naming the new path -- this
   proves the renamed file is still inside the naming guard's scan root.
3. Remove the class, verify on disk, clear
   `yate/keyproto/__pycache__` and `tests/__pycache__`, re-run the same test
   -> exit code 0. `git status --short` must show no extra diff for the codec
   module beyond the intended rename/docstring.

### Step A6 -- acceptance

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py tests/test_term_keys.py tests/test_app_textual.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
git grep -n -E "keyproto\.legacy|keyproto/legacy" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

All commands exit code 0; the last `git grep` must print nothing (exit code 1
for "no match" is the expected signal -- record it explicitly).

### Step A7 -- commit and rename check

```powershell
git add -A
git commit -m "refactor(keyproto): rename legacy key codec to key_codec"
git --no-pager log --follow --oneline -- yate/keyproto/key_codec.py
```

`git log --follow` must show the codec's history before the rename.

## 4. Risks / rollback

- Missed docstring path: residual grep + pyright + full pytest catch it.
- `git mv` tracking: `git status` rename line + `git log --follow` check.
- Rollback: `git revert <wave-1 commit>`; the other waves have not started.

## 5. Backfill (filled during execution)

Real command results, exit codes, negative-drill evidence, and deviations.
