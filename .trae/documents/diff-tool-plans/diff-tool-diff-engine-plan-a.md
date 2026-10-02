# diff-tool-diff-engine-plan-a（wave-1：L0 diff 引擎）

主计划：[../diff-tool-plan.md](../diff-tool-plan.md) · 总纲：[overview.md](overview.md)

## 输入

- 设计决策 D1/D3/D4（算法选型 difflib、数据模型、复制语义的纯计算部分）。
- 事实 F6（`TextBuffer.replace_range(start, end, text)` 签名，buffer.py:384——`hunk_replacement` 的返回值必须与其直接对齐）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor_core/diff.py` | 新增 |
| `tests/test_editor_core_diff.py` | 新增 |

## 具体修改

### `yate/editor_core/diff.py`（新增，~200 行）

- 模块 docstring：纯 stdlib 行级/字符级 diff 与 3way merge 区域计算；不 import Textual、不 import 上层（R4/R12；`from __future__ import annotations` 首行可执行语句）。
- 依赖仅：`difflib`、`dataclasses`、`collections.abc.Sequence`、`typing.Literal`、`yate.editor_core.buffer.Pos`（同包叶子类型，避免重复定义）。
- 数据类型（全部 `@dataclass(frozen=True)`）：

```python
@dataclass(frozen=True)
class DiffHunk:
    kind: str            # "replace" | "insert" | "delete"
    a_start: int; a_end: int   # 左侧行区间，0 基半开
    b_start: int; b_end: int   # 右侧行区间，0 基半开

@dataclass(frozen=True)
class DiffResult:
    hunks: list[DiffHunk]
    a_lines: int
    b_lines: int
    def align(self, row: int) -> int:
        """左侧行号 → 右侧锚点行号（等值区线性映射；差异区映射到该 hunk 的 b_start）。"""

@dataclass(frozen=True)
class MergeRegion:
    kind: str   # "same" | "local" | "remote" | "both" | "conflict"
    base_start: int; base_end: int
    local_start: int; local_end: int
    remote_start: int; remote_end: int
```

- 函数（能函数不造类，§三.6）：

```python
def diff_lines(a: Sequence[str], b: Sequence[str]) -> DiffResult
def diff_words(a: str, b: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]
def diff3_regions(base: Sequence[str], local: Sequence[str],
                  remote: Sequence[str]) -> list[MergeRegion]
def hunk_replacement(target: Sequence[str], hunk: DiffHunk, source: Sequence[str],
                     copy_into: Literal["a", "b"]) -> tuple[Pos, Pos, str]
```

实现要点：
1. `diff_lines`：`difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()`，tag `equal` 跳过、`replace`/`delete`/`insert` 直接映射为 `DiffHunk`（opcodes 的 `(tag,i1,i2,j1,j2)` 与字段一一对应）。
2. `align`：遍历 opcodes 时同步构建行映射（等值区 `row -> row + delta`，差异区两侧都映射到 hunk 起始）——在构造 `DiffResult` 时预计算成不可变映射存入私有字段，`align` 为 O(1) 查询（pyright strict 需字段注解）。
3. `diff_words`：单行字符级 `SequenceMatcher(None, a, b, autojunk=False)`，返回两侧非 equal 的 `(start, end)` 列表（字符下标，半开）。
4. `diff3_regions`：先取 base↔local 与 base↔remote 两份 opcodes，把 base 行上"被任一侧改动"的区间合并成连续 region（区间重叠/相邻即合并），再逐 region 分类：仅 local 改 → `local`；仅 remote 改 → `remote`；两侧都改且两侧新文本逐行相等 → `both`；否则 `conflict`；base 上两侧都没动的区间为 `same`（same 区是否入列表由调用方过滤——保留在输出里，kind 可过滤）。
5. `hunk_replacement`：`copy_into="b"` 时目标区间为 `(hunk.b_start, 0)` 到 `(hunk.b_end, 0)`（`b_end == b_lines` 时终点取 `(b_end - 1, len(line))`，即文件末尾无换行的半开处理），替换文本 = `"\n".join(source[hunk.a_start:hunk.a_end])`；`copy_into="a"` 对称。**不触碰 buffer**——由 L2 调用方执行 `replace_range`，保持本模块可单测。

### 不修改的文件

`yate/editor_core/__init__.py` 保持惰性不 re-export（§三.5），调用方一律 `from yate.editor_core.diff import ...`。

## 新增测试（`tests/test_editor_core_diff.py`）

命名 `test_<behavior>_<condition>_<expected>`；全部纯函数调用，无 fixture 需求（tmp 路径都不需要）。

| 用例 | 前置/操作（arrange/act） | 断言（assert） |
|---|---|---|
| `test_diff_lines_identical_inputs_yields_no_hunks` | `diff_lines(["a","b"],["a","b"])` | `result.hunks == []`；`a_lines == 2` |
| `test_diff_lines_replace_hunk_bounds_are_half_open` | `diff_lines(["a","x","c"],["a","y","c"])` | 恰 1 个 hunk：`kind=="replace"`、`(a_start,a_end)==(1,2)`、`(b_start,b_end)==(1,2)` |
| `test_diff_lines_insert_yields_b_side_only_hunk` | `diff_lines(["a"],["a","new"])` | 1 个 hunk：`kind=="insert"`、`a_start==a_end==1`、`(b_start,b_end)==(1,2)` |
| `test_diff_lines_delete_yields_a_side_only_hunk` | `diff_lines(["a","gone"],["a"])` | 1 个 hunk：`kind=="delete"`、`(a_start,a_end)==(1,2)`、`b_start==b_end==1` |
| `test_diff_lines_autojunk_disabled_on_long_inputs` | 300 行相同 + 第 300 行处 1 行修改，两侧调用 | `len(result.hunks) == 1`（锁死 autojunk=False；默认 autojunk 在此场景会产出错误 hunk 数） |
| `test_align_maps_equal_rows_and_changed_rows` | 上条 replace 场景的 `DiffResult` | `align(0)==0`、`align(2)==2`、`align(1)==1`（差异区锚到 b_start） |
| `test_diff_words_returns_char_ranges_for_changed_spans` | `diff_words("foo bar", "foo baz")` | 左侧含 `(4,7)`、右侧含 `(4,7)`；所有区间半开且落在 `len(text)` 内 |
| `test_diff_words_identical_lines_yield_empty_ranges` | `diff_words("same", "same")` | 两侧均为 `[]` |
| `test_diff3_regions_classifies_conflict_on_overlapping_edits` | base=`["1","2","3"]`，local 改第 2 行为 `2L`，remote 改为 `2R` | 存在 1 个 `kind=="conflict"` region，且其 base 区间为 `(1,2)` |
| `test_diff3_regions_classifies_disjoint_changes_independent` | local 改第 1 行、remote 改第 3 行 | 恰两个 region：一个 `local`、一个 `remote`，无 `conflict` |
| `test_diff3_regions_identical_changes_are_both_kind` | local 与 remote 对第 2 行做相同修改 | 存在 `kind=="both"` region，且无 `conflict` |
| `test_hunk_replacement_b_side_spans_target_range` | target=`["a","x","c"]`、source=`["a","y1","y2","c"]`、hunk 为 replace `(1,2)/(1,3)`、`copy_into="b"` | 返回 `(Pos(1,0), Pos(2,0), "y1\ny2")`（起点列 0、终点为被替换区间终点行首、文本为源块行连接） |
| `test_hunk_replacement_at_end_of_buffer_handles_last_line` | 目标区间 `b_end == b_lines` 的 insert 型 hunk | 终点 `Pos` 落在末行行尾（非越界行首），文本以 `"\n"` 开头（行插入语义）——精确期望值以实现定义为准，用例锁定之 |

## 验证方案

- 目标：证明 L0 引擎的 hunk 边界正确性（半开区间）、autojunk 陷阱免疫、3way 分类规则、`hunk_replacement` 与 `replace_range` 参数形状对齐。
- 命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_core_diff.py -q
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py -q   # 同包回归
python -m pyright yate/editor_core/diff.py tests/test_editor_core_diff.py
```

- 通过判定：退出码 0、零诊断。
- 边界条款：本步不改 `tests/test_architecture.py`（`editor_core` 纳入 R4 扫描面由 plan-c 落表；执行 plan-c 前本模块已天然满足 UI-free）。

## 风险与回滚

- 风险：`hunk_replacement` 末行半开区间 off-by-one —— 由最后两条用例锁定；`Pos` 为 tuple 别名，pyright 下注意按 `tuple[int, int]` 形状比较。
- 回滚：纯新增文件，`git revert` 该提交即可，无共享文件触碰。
