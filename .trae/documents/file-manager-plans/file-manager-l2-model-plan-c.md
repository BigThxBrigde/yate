# plan-c：L2 纯函数模型 filemgr_model.py（wave-2）

## 输入
总纲 §三/§四/§六（键位定稿、Q2 排序语义）。依赖 plan-a 的
`Entry` / `EntryStat` / `human_size`（`yate/services/workspace.py`）。
事实基线：`list_dir` 返回按 `(not is_dir, name.lower())` 排序的 `list[Entry]`；
`icon_for_path(name, is_dir, expanded)` / `icon_color(name, is_dir, dir_color)`
（`editor_view/icons.py:92-96,170-179`，目录色由调用方传主题 accent）；
`theme.active()` 提供主题色（explorer.py:218-226 消费先例）。

## 目标
file manager 的**无 UI 数据层**：目录列表组装（过滤/排序/过滤查询）、行渲染
数据（图标+着色+大小右对齐+目录徽标）、状态栏文本、盘符虚拟层整合。
纯函数 + 不可变数据，pyright strict 全注解，单测覆盖 ≠ 0 逻辑分支。

## 独占文件清单
- `yate/editor_view/filemgr_model.py`（新建）
- `tests/test_filemgr_model.py`（新建）

## 具体修改

### 1. 排序枚举与循环
```python
type SortKey = Literal["name", "size", "mtime"]  # PEP 695 type 语句
SORT_CYCLE: tuple[SortKey, ...] = ("name", "size", "mtime")

def next_sort(current: SortKey) -> SortKey: ...        # 循环下一个
def sort_entries(
    entries: list[Entry], stats: dict[Path, EntryStat], key: SortKey,
    *, descending: bool = False,
) -> list[Entry]:
    """Directories first (name asc), then files by key; stable."""
```
目录永远在前（目录组内恒按 name 升序）；文件组内按 key，`descending` 翻转。
稳定排序（`sorted` 稳定性保序同 key 相对次序）。

### 2. 过滤
```python
def filter_entries(entries: list[Entry], query: str) -> list[Entry]:
    """Case-insensitive substring filter (empty query = no-op)."""
```
P0 用**子串**包含（lf 语义；不引 fuzzy_match——palette 的 fuzzy 面向文件路径
打分，目录浏览用子串更直觉；`from yate.editor_view.palette import fuzzy_match`
会拉 711 行模块入栈，否决）。

### 3. 行渲染数据
```python
@dataclass(frozen=True)
class RowSpec:
    text: str        # 无色富文本串由调用方经 build_row_text 着色
    path: Path
    is_dir: bool
    is_marked: bool
    size_text: str   # human_size 结果或 ""（目录）

def build_row_text(
    entry: Entry, stat: EntryStat | None, accent: str, marked: bool,
    *, dir_child_count: int | None, sort_key: SortKey,
) -> Text:
```
格式：`[icon][space][name][padding][badge][size]`——icon 经 `icon_for_path`
着 `icon_color(name, is_dir, accent)`；目录名 accent、文件名 fg（对齐
explorer.py:222-225 同源语义）；marked 前缀 `* `（或行首标记列）；
目录徽标 `(N)`（`dir_child_count`，None 则省略；>999 显 `999+`）；
size 列右对齐固定宽 6（`human_size`，目录空串）；返回 `rich.text.Text`
（span 着色， ListView item 直接可用）。
目录徽标计数器：
```python
def count_children(path: Path) -> int:
    """Number of direct children (any visibility), cheap scandir pass."""
```
`os.scandir` 迭代计数（迭代器关闭），>999 提前退出返回 1000 哨兵；
`OSError` → -1（显示层省略徽标）。P0 性能：仅对**目录行**调用，中栏一次构建。

### 4. 状态栏文本
```python
def format_status(
    stat: EntryStat | None, index: int, total: int, sort_key: SortKey,
    descending: bool, filter_active: str | None, marked_count: int,
) -> str:
```
形态（对齐 lf 参考视觉）：
`-rw-rw-r-- 1 alice devteam 72B Fri Feb 28 14:02:01 2025 · 2/8 · name asc`
——mode 经 `stat.filemode(st_mode)`；owner/group None 时以 `-` 占位
（Windows：`-rw-rw-r-- 1 - - 72B ...`）；size 用 `human_size`；
mtime `%a %b %d %H:%M:%S %Y`（`time.strftime` 本地时区——lf 同款）；
尾部 `n/total` 位置 + 排序提示 + 过滤态（`filter: <query>`）+ 标记数
（`marked: 3`，0 时省略）。单行 ≤ 终端宽的截断由显示层（Static）处理。

### 5. 盘符整合
```python
def parent_and_siblings(
    current: Path, workspace: Workspace,
) -> tuple[Path | None, list[Entry]]:
    """Left-pane model: parent dir entries; None parent at root."""
```
根层（`current.parent == current`）时：win32 → `(None, workspace.list_drives())`
盘符虚拟层（Q4）；POSIX → `(None, [])`。非根 → `(current.parent,
workspace.list_dir(current.parent))`。

### 6. dir 光标记忆键
纯数据契约：`_dir_memory` 由 Screen 维护，model 只提供
`def memory_key(entry_path: Path) -> Path`（恒等；留名锚定语义防漂移）。
若实现中发现无必要可省略（回填偏离记录）。

## 新增测试（tests/test_filemgr_model.py）
前置：tmp_path 目录树 + plan-a 的 EntryStat 真实数据（或手造 frozen dataclass）。

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_sort_entries_dirs_first_and_key_cycle` | name/size/mtime 各排 + `next_sort` | 目录恒在前且组内 name 升序；文件组按 key；`next_sort("name")=="size"` 循环回绕 |
| `test_sort_entries_descending_flips_files_only` | descending=True | 目录组仍 name 升序，文件组倒序 |
| `test_filter_entries_substring_case_insensitive` | query "PY" | 匹配 `a.py` 不匹配 `b.txt`；空 query 恒等返回同序 |
| `test_build_row_text_marks_icon_and_size_columns` | 目录/文件/标记行 | icon 字符与 Seti 色对齐 icons.py；`* ` 前缀；size 列右对齐宽 6；目录无 size |
| `test_build_row_text_dir_badge_counts_children` | 真实子目录 3 项 | 含 `(3)`；`count_children` 对 >999 截断为 1000 |
| `test_count_children_missing_dir_returns_minus_one` | 不存在路径 | `-1` 且不抛 |
| `test_format_status_matches_lf_layout` | 构造 stat + index 1/8 | 精确字符串比对（filemode + nlink + owner + size + mtime 格式 + `2/8`……以 index=1 断言 `2/8` 对齐 lf 1-based）；过滤/标记段按态出现/省略 |
| `test_parent_and_siblings_root_behaviors` | tmp 根目录（POSIX 形态）+ monkeypatch win32 | 非根返回 parent+list_dir；根层 win32 走 list_drives、POSIX 空列表 |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/filemgr_model.py tests/test_filemgr_model.py
.venv\Scripts\python.exe -m pytest tests/test_filemgr_model.py tests/test_architecture.py -q
```

## 风险与回滚
- `Literal` 需 `from typing import Literal`（3.12 正常）；SortKey 用 type 语句
  （架构守卫 test_callable_aliases_use_type_statements 的 PEP 695 要求）；
- 与 plan-a 的契约（EntryStat 字段名）若漂移，本计划测试先红——按 plan-a 文档
  为准修正本侧；
- 回滚：独立成笔，纯新增文件。
