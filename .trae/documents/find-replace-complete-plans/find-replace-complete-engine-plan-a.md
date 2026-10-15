# plan-a：project_search 引擎（wave-1）

> 总纲见 [overview.md](overview.md)。波次：wave-1（无依赖，可与 plan-b 并行
> ——两者无数据依赖，文件不重叠）。

## 一、输入

- 总纲 F1-F4（SearchEngine 语义）、D4/D4b（位置与 regex 语义决策）；
- [search.py](../../yate/editor_core/search.py) 全文（174 行）：`_compile`
  （L41-51）为唯一编译点；`replace_all` 的逐匹配 `pattern.sub` 语义
  （L158）。

## 二、独占改动文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor_core/project_search.py` | 新建（≤250 行） |
| `yate/editor_core/search.py` | 修改（`_compile` 委托，约 ±6 行） |
| `tests/test_project_search.py` | 新建（测试文件，不计改动判据） |
| `tests/test_editor_core.py` | 追加 2 个用例（测试文件） |

不改动：`yate/editor_core/__init__.py`（§三.5，`project_search` 不进包根，
消费者仅 yate 内部）。

## 三、具体修改

### 3.1 新建 `yate/editor_core/project_search.py`

模块 docstring 声明："Project-wide search primitives over plain line
lists. File traversal, decoding and disk-write policy belong to the
caller (L0 pure text algorithms; no Textual, no Workspace import)."

```python
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from yate.logs import tracing

log = tracing.get_logger(__name__)

#: Called with the number of files scanned so far (worker progress).
type ProgressFn = Callable[[int], None]


@dataclass(frozen=True)
class LineMatch:
    """One hit inside a file: 0-based row plus start/end columns."""

    row: int
    start: int
    end: int


@dataclass(frozen=True)
class FileMatch:
    """All hits in one file, in document order."""

    path: Path
    matches: list[LineMatch]
```

公共函数（全部纯函数，§三.6 能函数不造类）：

1. `def compile_query(query: str, *, case_sensitive: bool = False,
   use_regex: bool = False, whole_word: bool = False) ->
   re.Pattern[str] | None`——从 `SearchEngine._compile`（search.py L41-51）
   **原样下沉**（空 query → None；非 regex 先 `re.escape`；whole_word
   包装 `rf"(?:(?<=\W)|^){pattern}(?=\W|$)"`；flags；`re.error` → None）。
   docstring 注明"single source of compile semantics; SearchEngine
   delegates here"。
2. `def search_lines(lines: Sequence[str], pattern: re.Pattern[str]) ->
   list[LineMatch]`——`finditer` 逐行收集，`start == end` 跳过（对齐
   search.py L63 的空匹配守卫）。
3. `def search_files(paths: Sequence[Path], query: str, *,
   case_sensitive: bool = False, use_regex: bool = False,
   whole_word: bool = False, max_file_bytes: int = 2_000_000,
   max_matches: int = 2000, progress: ProgressFn | None = None) ->
   list[FileMatch]`：
   - `compile_query` 为 None → 返回 `[]`；
   - 逐文件：`read_bytes()`（`OSError` → `log.debug` + 跳过）、
     `len(data) > max_file_bytes` → 跳过、`data.decode("utf-8")`（
     `UnicodeDecodeError` → 跳过——二进制与异编码文件天然被排除）；
   - `splitlines()` 后 `search_lines`；累计匹配数达 `max_matches` 即停
     （`log.debug("project search stopped at %d matches", ...)`）；
   - 每文件处理后 `progress(done)`；只收集非空 `FileMatch`。
4. `def replace_lines(lines: list[str], pattern: re.Pattern[str],
   replacement: str) -> tuple[list[str], int]`——**逐匹配拼接算法**
   （D4b，对齐 `SearchEngine.replace_all` L151-163 的形状）：
   - 每行 `search_lines` 收集非空匹配；无匹配行原样保留；
   - 对每个匹配：`pattern.sub(replacement, line[m.start:m.end])`（
     backreference 相对单匹配文本，与 replace_all L158 一致）；
   - 拼接为 new line；返回 `(new_lines, count)`；**无任何匹配时返回
     `(lines, 0)`——同一对象**（调用方凭 `is` 判定免写盘）。

### 3.2 修改 `yate/editor_core/search.py`

- 顶部加 `from yate.editor_core import project_search`（包内绝对导入，
  §六 #29 禁相对导入）。
- `_compile`（L41-51）整体替换为薄委托：

```python
def _compile(self, query: str) -> re.Pattern[str] | None:
    return project_search.compile_query(
        query,
        case_sensitive=self.case_sensitive,
        use_regex=self.use_regex,
        whole_word=self.whole_word,
    )
```

其余（`Match` / `update` / `next` / `current` / `replace_current` /
`replace_all`）一字不动。

## 四、输出

- L0 引擎可独立测试；`SearchEngine` 行为零变化（委托等价）；
- plan-c 的 `search_files` / `replace_lines` API 就绪。

## 五、测试用例（详细三要素）

新建 `tests/test_project_search.py`：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_compile_query_empty_returns_none` | — | `compile_query("", case_sensitive=False, use_regex=False, whole_word=False)` | 返回 `None` |
| `test_compile_query_invalid_regex_returns_none` | — | `compile_query("(", use_regex=True, ...)` | `None`，不抛 |
| `test_search_lines_finds_all_occurrences` | lines `["foo bar foo"]`，pattern `compile_query("foo")` | `search_lines` | 2 个 `LineMatch`：`(0,0,3)`、`(0,8,11)` |
| `test_search_lines_whole_word_skips_substring` | lines `["category cat"]`，`whole_word=True` | `search_lines` | 仅 `(0,9,12)` |
| `test_search_lines_case_flag` | lines `["FOO foo"]` | 大小写关 → 2 处；大小写开 → 1 处 | — |
| `test_search_lines_skips_empty_matches` | pattern `compile_query("a*", use_regex=True)` | `search_lines(["bab"])` | 无零长匹配（对齐 update 的 L63 守卫） |
| `test_search_files_skips_binary_and_oversize` | tmp_path：`a.txt`（含 needle）、`b.bin`（`b"\x00needle"`）、`c.txt`（4 MB 全 0） | `search_files([a,b,c], "needle")` | 仅 `a.txt` 一组 |
| `test_search_files_unreadable_is_skipped` | tmp_path：一个不存在 Path + 一个正常文件 | `search_files` | 不抛，返回正常文件结果 |
| `test_search_files_stops_at_max_matches` | 3 文件各 100 个 needle | `max_matches=150` | 累计 ≤ 150 |
| `test_search_files_reports_progress` | 2 个文件 | `progress` 回调 | 末次回调值 == 2 |
| `test_replace_lines_replaces_and_counts` | `["foo bar", "x foo"]`，`foo`→`qux` | `replace_lines` | `(["qux bar", "x qux"], 2)` |
| `test_replace_lines_regex_backreference_per_match` | `["a@x b@x"]`，`(\w+)@x`→`\1` | `replace_lines` | `(["a b"], 2)` |
| `test_replace_lines_no_change_returns_same_object` | 无匹配行集 | `replace_lines` | 返回对象 `is` 输入（免写盘依据） |
| `test_replace_lines_matches_engine_replace_all` | 同一 buffer 行集，同一 query/选项 | `replace_lines` vs `SearchEngine.update+replace_all` 后的 `buffer.lines` | 逐行相等（语义对齐的黄金用例） |

追加 `tests/test_editor_core.py` 2 个用例：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_engine_compile_delegates_with_same_options` | `SearchEngine` 四种选项组合 | `engine._compile(q)` vs `project_search.compile_query(q, ...)` | 逐一 `==`（防下沉漂移） |
| `test_engine_next_skips_text_inside_replaced_match` | buffer `"foo foo foo"`，update `foo` | `next()` 选中第 1 个 → `replace_current(buffer, "foofoo")` → `next()` | 选中的是原第 3 个（row 0, start ≥ 7），不落入替换文本内部（总纲 R2 死循环防线；确认循环终止性由 plan-b 的计数保证） |

## 六、验收命令（该波结束应全绿）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_project_search.py tests/test_editor_core.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

通过判定：三条退出码 0（架构守卫对新文件自动生效：体量 / 日志惰性 / R12 / 绝对导入）。

## 七、风险与回滚

- 漂移风险：见总纲 R6（四选项组合等价测试 + 黄金对齐用例双保险）；
- 回滚：`git revert` 单提交——project_search.py 为纯新增文件，revert
  零副作用；search.py 的 `_compile` 还原为原 10 行实现。
