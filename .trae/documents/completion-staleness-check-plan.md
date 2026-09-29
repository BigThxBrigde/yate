# Completion Staleness Check Fix Plan

> **实施状态（2026-09-22 核对）：✅ 已实现（包含 Change 1–4）。**
>
> - `yate/app_features/completion.py` 已有 `_current_prefix()` 辅助；两条路径
>   （buffer-based 与 LSP）的陈旧守卫同时比较 `buf.row`、当前列与前缀文本
>   （`buf.col != cur_col or cur_prefix != prefix`），不再只看 row。
> - `accept()` 已改为按行列范围判定（等价于 `row < r0 or row > r1`），
>   评审指出的 `row != r0 or row != r1` 逻辑错误不存在。
> - 本文档保留为设计记录（含根因分析与备选方案）。

## Summary

The completion popup staleness check in `yate/app_features/completion.py` only compares the row (`buf.row != row`) after an LSP `await` returns, but ignores the column position. If the user keeps typing on the same row while the LSP request is in flight, the stale completions are still displayed. When the user accepts one of these stale items, `replace_range` uses outdated coordinates, potentially corrupting text by replacing the wrong span. This plan strengthens the staleness guard by also checking the column and the prefix text.

## Current State Analysis

### File: `yate/app_features/completion.py`

#### 1. Staleness check — Buffer-based path (lines 117–123)
```python
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or not popup.is_mounted
):
    return
```
Only row is compared. Column changes on the same row pass through.

#### 2. Staleness check — LSP path (lines 156–163)
```python
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or not popup.is_mounted
):
    return
```
Same deficiency — only row compared after `await app.lsp.request_completion(...)`.

#### 3. Capture at start of `_worker` (lines 98–104)
```python
row, col = buf.row, buf.col
line = buf.lines[row] if row < buf.line_count else ""
col = min(col, len(line))
i = col
while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
    i -= 1
prefix = line[i:col]
```
Both `col` and `prefix` are captured and available for comparison — they just aren't used in the stale checks.

#### 4. Accept method — existing guards (lines 202–219)
```python
row, col = buf.row, buf.col
if item.has_range():
    r0 = item.range_start_row or 0
    c0 = item.range_start_col or 0
    r1 = item.range_end_row or 0
    c1 = item.range_end_col or 0
    if row == r1 and col >= c1:
        c1 = col   # extend range forward if cursor moved right
    if (row, col) < (r0, c0) or (r0, c0) > (r1, c1):
        return     # discard if cursor moved away
    start, end = (r0, c0), (r1, c1)
else:
    i = col
    line = buf.lines[row]
    while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
        i -= 1
    start, end = (row, i), (row, col)
buf.replace_range(start, end, item.insert_text)
```
The `accept` method already has a defensive range check, but it still permits replacement when the cursor is *forward* of the original range (`if row == r1 and col >= c1: c1 = col` extends the replacement forward). This is safe for buffer-based completions but not sufficient to prevent a stale item from corrupting text when the row hasn't changed but the column has moved past what the completion was for.

### Root Cause

The `_worker` coroutine captures `row` and `col` (line 98) and `prefix` (line 104) before awaiting LSP. The stale checks at lines 120 and 160 only re-check `row`. `col` and `prefix` are never re-compared. So:
- User types `"pr"` → debounce → `_worker` starts, captures `row=5, col=7, prefix="pr"`
- User continues typing `"pri"` (3 chars) → debounce timer reschedules; but the first `_worker` is still `await`ing LSP
- LSP responds; `buf.row` is still 5 (check passes), `buf.col` is now 8 or 9 (NOT checked)
- Stale completions shown; accepting one replaces range `(5, 4)-(5, 7)` (outdated) with the completion text

## Proposed Changes

### Change 1: Strengthen staleness check in buffer-based completion path
**File:** `yate/app_features/completion.py`  
**Location:** lines 117–123  
**What:** Add `buf.col != col` to the guard and also verify the current prefix still matches the originally captured prefix.  
**How:** Replace the existing condition with:
```python
# Recompute prefix at current cursor position
cur_line = buf.lines[row] if row < buf.line_count else ""
cur_col = min(buf.col, len(cur_line))
j = cur_col
while j > 0 and (cur_line[j - 1].isalnum() or cur_line[j - 1] == "_"):
    j -= 1
cur_prefix = cur_line[j:cur_col]

if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or buf.col != col
    or cur_prefix != prefix
    or not popup.is_mounted
):
    return
```
**Why:** Comparing `col` is a cheap and direct guard. Comparing the prefix text is more robust — it catches cases where the user *deletes* characters, moves the cursor within the same prefix, or pastes something. It also guards against silent buffer edits that shift the row length without changing the row number.

### Change 2: Strengthen staleness check in LSP completion path
**File:** `yate/app_features/completion.py`  
**Location:** lines 156–163  
**What:** Same change as above — add column comparison and prefix text comparison.  
**How:** Replace the existing condition with the same logic as Change 1.  
**Why:** Identical rationale to Change 1. This is the primary location referenced in the issue.

### Change 3: Factor out helper (optional but recommended)
**File:** `yate/app_features/completion.py`  
**What:** Extract the "compute prefix at position" logic into a small helper method to avoid duplicating it at both check sites.  
**How:** Add a private helper on `CompletionController`:
```python
def _current_prefix(self, buf: "TextBuffer", row: int) -> tuple[str, int]:
    line = buf.lines[row] if row < buf.line_count else ""
    col = min(buf.col, len(line))
    i = col
    while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
        i -= 1
    return line[i:col], col
```
Then both check sites become:
```python
cur_prefix, cur_col = self._current_prefix(buf, row)
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or buf.col != cur_col
    or cur_prefix != prefix
    or not popup.is_mounted
):
    return
```
**Why:** DRY — the prefix-recomputation logic mirrors what `_worker` already does at lines 99–104 and what `accept` does at lines 216–218. A single helper reduces drift risk.

### Change 4: Make `accept` refuse clearly stale completions
**File:** `yate/app_features/completion.py`  
**Location:** `accept()` method, after `popup.close()` and before `buf.replace_range(...)`  
**What:** After closing the popup, capture the current row/col *again* (they may have moved between popup accept and the replace) and verify they are still on the expected row before doing the range replace.  
**How:** Insert a guard:
```python
# Popup-close may have been followed by another keystroke; re-capture.
cur_row, cur_col = buf.row, buf.col
if item.has_range():
    r0 = item.range_start_row or 0
    ...
    if cur_row != r1:
        return  # cursor left the row the completion was for
    ...
```
**Why:** Closing the popup consumes a keystroke (Enter/Tab), but the editor might have processed additional keys between the popup being selected and `accept()` being called. A final row check prevents cross-row corruption.

## Assumptions & Decisions

1. **Row is the primary guard, column is secondary.** If the row changes, the completion is obviously stale. The column/prefix checks catch the same-row case.

2. **Prefix text comparison is more robust than column comparison alone.** If a user types past the original prefix (`"pr"` → `"priority"`), the current prefix grows; comparing the full prefix catches this. If the user deletes back past the original prefix, the prefix shrinks; this is also caught. Column comparison alone would not catch deletion or paste scenarios reliably.

3. **`_current_prefix` helper mirrors the worker's prefix definition.** The worker uses `isalnum() or "_"` for prefix boundary. The helper must use the same definition, not `buffer_completions._ident_prefix` (which also includes `/`, `\`, `~` for path completions — a subtly broader definition used only for filesystem path detection, not general LSP/popup guarding).

4. **No changes to the debounce / worker exclusivity model.** The existing `exclusive=True` on `run_worker` serializes LSP completion workers; the stale check is defense-in-depth for the case where one worker finishes while the next is waiting to run.

5. **No changes to `buffer_completions` in `editor_view/completion.py`.** The completion items there already carry precise `range_start_row/col/end_row/end_col` values. The issue is not in how ranges are computed but in when they are accepted.

## Verification Steps

### Unit / integration tests
1. Run existing completion tests:
   - `pytest tests/test_app_textual.py -k completion -v`
   - `pytest tests/test_lsp.py -k completion -v`
2. Add a targeted test for the staleness scenario:
   - Start a document, mock an LSP completion response that takes >200 ms
   - Type `"pr"` → trigger completion request
   - Immediately type more characters on the same row before the LSP responds
   - Assert the popup does NOT appear (or closes immediately)
3. Add a targeted test for the accept-path guard:
   - Mock a completion, show popup, move cursor to a different row, accept
   - Assert `replace_range` is NOT called (no text corruption)

### Manual (Textual pilot) verification
1. Open a Python file, trigger a slow LSP completion (e.g., typing `"im"` in a large project with `pylsp`)
2. While waiting for popup, quickly type more characters
3. Wait — verify popup does not appear, or if it briefly shows, it shows updated completions
4. Test deletion: type `"import o"` → complete → delete back to `"import"` → verify popup updates

### Edge cases to confirm
- User moves cursor **left** (deletes characters) on the same row while awaiting → stale guard should close the popup
- User moves cursor **right** (adds characters) on the same row while awaiting → stale guard should close the popup
- User switches to another tab while awaiting → existing `app.doc is not doc` check already covers this
- User moves to a different row while awaiting → existing `buf.row != row` check already covers this

---

## Practical Suggestions for Optimizing Task Execution

1. **Implement Change 3 (helper) first**, then use it in Changes 1 and 2 — this avoids copy-paste errors and keeps the two guard sites in sync.
2. **Write the tests before the fix** (TDD-lite): the stale-popup scenario is easier to verify with a failing test that becomes passing.
3. **Run `pytest tests/test_app_textual.py -k "wq or completion" -v`** after each change — these two areas were recently modified and the isolation fixture (`YateApp` per test) is the same one used for completion tests.

## Potential Risks and Mitigation Strategies

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Overly aggressive stale check closes popup on valid cases (e.g., cursor jitter) | Low — prefix comparison is deterministic; typing *always* changes prefix | Medium (annoying UX) | The check only fires after an `await`; the debounce already gates requests. Compare full prefix, not just a single column delta. |
| Helper introduces drift from `accept()`'s own prefix logic | Medium — three sites compute prefix (`_worker`, `accept`, new helper) | Low (minor inconsistency) | The new helper uses the same `isalnum() or "_"` rule as `_worker` and `accept`. Add a comment noting they must stay in sync. |
| Regression: `buffer_completions` path includes path prefix chars (`/`, `\`, `~`) but the helper doesn't | Low — buffer-based path completions already carry explicit ranges | Low | Confirmed via code read: `buffer_completions` always emits items with `range_start_row/col/end_row/end_col`, so `accept()` uses the range, not re-computed prefix. The stale guard only needs to decide *whether to show the popup*, not how to replace. |
| `accept()` guard (Change 4) breaks Tab-accept when user typed past the range | Low — the existing `if row == r1 and col >= c1: c1 = col` line already extends the end column | Low | Change 4 only adds a row check; column is handled by existing extension logic. |

## Feasible Extension Directions

1. **Content-version based staleness.** `TextBuffer.content_version` is bumped on every text mutation. Capturing it at the start of `_worker` and re-checking after `await` would be a single integer comparison that covers *all* mutation cases (typing, deletion, paste, undo), not just row/col changes. This would be a cleaner, more general guard than prefix text comparison. Requires no API changes to `TextBuffer` — `content_version` is already public.

2. **Cancel in-flight workers explicitly.** `CompletionController._timer` already cancels the debounce timer. The controller could also track the current `_worker` task and cancel it when `schedule()` is called. Combined with `exclusive=True`, this would make stale checks purely defensive rather than necessary.

3. **Pop-up auto-close on any buffer mutation.** Instead of checking staleness after awaiting, the popup could listen to buffer `content_version` changes and close itself whenever the buffer is modified. This would eliminate the need for per-worker stale checks entirely, at the cost of a more reactive (but simpler) popup lifecycle.

---

## Follow-up fix (2026-09-23): the popup no longer swallows every key

The staleness guard above only covers what happens *after* a query returns.
A second, older defect sat in the key path: while the popup was open the
dispatcher consumed **every** key (`if popup.is_open: ... return True`), so
typing could not extend the prefix and the guarded re-query in
`after_editor_key()` was unreachable (see `../issues/review.md`, "completion
popup intercepts all keys").

* **Source fix** — `yate/editor.py::handle_key` now consumes only
  `tab` / `enter` / `up` / `down` / `escape`; every other key falls through to
  the normal dispatch (`event_to_raw` → `handle_raw_key` →
  `CompletionController.after_editor_key`), which re-queries with the new
  prefix.  Global chords (`Ctrl+S`, `Ctrl+Z`, `Ctrl+P`, ...) work again while
  the popup is up.
* **Guards** — `tests/test_app_textual.py::test_completion_popup_keeps_typing_and_filters`
  (typing `p` / `h` after `Ctrl+Space` extends the buffer and keeps filtering)
  plus the smoke scenario `regress_completion_staleness`, which now asserts the
  popup really opened (`popup_was_open`) instead of passing vacuously.
* **Attribution** (re-verified 2026-09-23) — the `return True` came in with
  `e70dd15` (2026-09-12), but back then `EditorView.on_key` did **not**
  `stop()` unrecognised keys, so they bubbled up to `YateApp.on_key`'s
  fallback routing and still reached the buffer: running the same probe on
  master (`673b077`) typed `p` / `h` fine and `Ctrl+Z` still undid, with the
  popup open.  The layering refactor (`9fa5ac8`) made `EditorView.on_key` stop
  every key unconditionally and moved the popup branch into
  `Editor.handle_key`, so the stale `return True` finally swallowed input.
