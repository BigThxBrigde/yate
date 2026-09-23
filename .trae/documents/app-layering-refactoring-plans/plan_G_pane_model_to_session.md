# Plan G — 窗格模型下沉：`pane_types.py` 并入 `session.py`（L1）

> 状态：✅ **已完成**（2026-09-23 落地）· 前置：[Plan A](plan_A_leaf_models.md)–[Plan F](plan_F_gate_docs.md) 全部完成
> 归属：**总纲** [README.md](README.md) 的后续子计划（§5 索引已登记），同时直接受
> [architecture-boundaries.md](../../rules/architecture-boundaries.md) §三.1 / §三.6 / §五 约束。
> 类型：**代码搬运 + 删除**（不重写任何算法、不改任何行为）
> 门禁：`python -m pyright yate/ tests/ tools/` 0 诊断 · `python -m pytest tests/ -q` 全绿 ·
> `python -m pytest tests/test_architecture.py -q` 12 passed

---

## G.1 背景（问题陈述）

`yate/editor_view/pane_types.py`（155 行）位于 **L2 组件层**，但它承载的内容不是"类型定义"，而是
**窗格模型与状态**：

| 内容 | 性质 |
|---|---|
| `Leaf(id, doc, states)` | 布局状态：一个文档槽位 + 该槽位的每文档视口状态 |
| `ViewState(cursor, anchor, scroll_col, scroll_row)` | 每视口状态（无 Textual 依赖） |
| `Split(axis, children, sizes)` / `Node` / `Axis` | 布局树 |
| `leaves` / `find_leaf` / `replace_node` / `remove_node` / `find_axis_split` | 树纯操作 |
| `MIN_FRACTION` / `RESIZE_STEP` | resize 常量 |

两个结构性问题：

1. **放错层的状态**。按 [architecture-boundaries.md](../../rules/architecture-boundaries.md) §五 自检表
   「**状态放在正确的层**：文档 / 标签 / 搜索 → `EditorSession`」，而窗格树状态既不在 `EditorSession`、
   也不在任何 L1 模型里，被挂在了 L2 的 widget 包里。它之所以"看起来像类型层"，正是因为它是被
   **抽出来共享**的，而不是因为它真的是类型定义。
2. **违反 §3.1「不建"公共类型层"」**。`pane_types.py` 恰好是规则禁止的那种"公共类型层"形态；
   规则 §3.6 的反例清单还直接点了名：「数据操作（`pane_types.py` 的 `find_leaf` / `replace_node`…）
   一律用函数」——说明该模块的定位在规则成文时就已被标记为待处理。

它当前**唯一**的正当理由写在模块 docstring 里：打断 `editor.py` ⇄ `panes.py` 的类型级环。
而该环的根治方式不是"新建一个跨层公共类型文件"，而是**把模型下沉到 L1**——L1 天然允许被
L2 与 L3 同时 import，环自然消失。

### 为什么不能下沉到 `editor_core`

`ViewState.scroll_row` / `scroll_col` 是**视口**概念；`editor_core` 的定位是
"纯编辑逻辑：buffer / document model / search engine（无 Textual 依赖）"。把布局状态混入会污染
其纯性——**本轮不动 `editor_core` 一行**，这是硬性前提。

### 术语与命名（保留，不改名）

`Leaf` / `Split` / `Node` / `ViewState` **本次不改名**。理由：本次要解决的是**位置**问题，
改名是纯审美且会额外波及 `tests/test_panes.py` 与 pilot 用例。若将来要把词表对齐 vim 的
`window` 语义（`Leaf` → `Window` 等），独立一轮做，不在本 Plan 范围。

---

## G.2 目标分层（本轮改动后）

```
L0  editor_core            Document / TextBuffer / SearchEngine          ← 不动（保持纯性）
L1  session.py             EditorSession + 【窗格模型】(Leaf/Split/Node/ViewState/
                           Axis/树操作/常量)                              ← 新家（只依赖 L0）
L2  editor_view/editor.py  EditorView：`from yate.session import Leaf`
    editor_view/panes.py   PaneManager / PaneHost：`from yate.session import ...`
                           （删除 deprecated 重导出段）
L3  yate/editor.py         Editor：`from yate.session import Axis, Leaf`
```

依赖图（零环）：

```
editor_core ──> session.py ──> editor_view/* ──> editor.py
                  ▲
                  └── 同时被 editor_view/panes.py、editor_view/editor.py、yate/editor.py 直接 import
```

`yate/session.py` 新增依赖仅 `from dataclasses import dataclass, field` 与
`from yate.editor_core.buffer import Pos`（均已是 L0，且 `Document` 已在文件内）。

> **关键点**：`EditorSession` **类本身零改动**。窗口布局不由 session 持有（仍由
> `PaneManager` 持有、`Editor` 组装），本 Plan 只让"无 UI 的窗格模型"与 `EditorSession`
> **同模块**——模块 docstring 会把这层关系写清楚，避免读者误以为 session 管窗格。

---

## G.3 交付物

| 文件 | 动作 | 内容 |
|---|---|---|
| `yate/editor_view/pane_types.py` | **删除** | 全部 155 行迁入 `session.py` |
| `yate/session.py` | **接收** | 新增「窗格树模型」分区：`Axis` / `MIN_FRACTION` / `RESIZE_STEP` / `ViewState` / `Leaf` / `Split` / `Node` / 5 个纯函数 / `_normalized`；模块 docstring 补一段；顶部 import 增补 |
| `yate/editor_view/panes.py` | **改 import + 删重导出** | import 源改 `yate.session`；删除第 54–65 行的"backward compatibility"段与 `__all__`，或收窄为仅 `PaneManager` / `PaneHost` |
| `yate/editor_view/editor.py` | **改 import** | 第 26 行 `from .pane_types import Leaf` → `from yate.session import Leaf` |
| `yate/editor.py` | **改 import** | 第 48 行 `from yate.editor_view.pane_types import Axis, Leaf` → `from yate.session import Axis, Leaf` |
| `tests/test_panes.py` | **改 import** | 从 `yate.editor_view.panes` 的 deprecated 路径改为 `from yate.session import ...` |
| `tests/test_app_textual.py` | **改 import** | 第 29–30 行同样迁移（`PaneSplit` / `pane_leaves` 别名保留） |

**不改动**：`yate/editor_view/panes.py` 的 `PaneManager` / `PaneHost` 行为与签名、
`yate/session.py` 的 `EditorSession` 行为与签名、任何渲染/渲染顺序/消息文案。

---

## G.4 执行步骤

> 顺序刻意安排为「先落地新家 → 再切消费者 → 最后删旧文件」，**中途任何一步都不出现
> "文件已删但引用未改"的瞬态**（每个步骤单独 commit 都能 import 成功）。

### G.4.1 步骤 1：`session.py` 接收模型（纯搬运）

在 `yate/session.py` 末尾追加分区（放在 `_notify_closed` 之后，或 `EditorSession` 之前均可，
建议**放文件末尾**以保持 `EditorSession` 的阅读连续性）：

```python
# ============================================================== 窗格树模型
# 无 UI 的窗口布局模型：一个 Leaf 是一个绑定 Document 的编辑器窗口槽位，
# Split 是其水平/垂直组合。它们与 EditorSession 同属 L1（只依赖 editor_core），
# 因此 L2 的 editor_view/editor.py 与 editor_view/panes.py 都能直接 import，
# 无需中间类型层（原 editor_view/pane_types.py）。窗口布局本身仍由 Editor
# （L3）组装、PaneManager（L2）持有——EditorSession 不感知窗格。

#: Split axis: ``horizontal`` stacks top/bottom (:split), ``vertical`` puts
#: windows side by side (:vsplit).
Axis = Literal["horizontal", "vertical"]

#: Smallest share of a split any one pane may hold while resizing.
MIN_FRACTION = 0.12

#: Fraction transferred per ``ctrl+w +/-/< />`` keypress.
RESIZE_STEP = 0.08


@dataclass
class ViewState:
    """Per-(leaf, document) view: independent cursor, anchor and scroll."""

    cursor: Pos = (0, 0)
    anchor: Optional[Pos] = None
    scroll_col: int = 0
    scroll_row: int = 0


@dataclass
class Leaf:
    """One editor window bound to a document."""
    ...  # 原 pane_types.py 第 43-63 行原样

@dataclass
class Split:
    """A horizontal/vertical arrangement; ``sizes`` sum to 1.0."""
    ...  # 原 pane_types.py 第 67-72 行原样

Node = Union[Leaf, Split]


def leaves(node: Node) -> list[Leaf]:
    ...  # 原 pane_types.py 第 81-155 行原样（含 find_leaf / replace_node /
         # remove_node / find_axis_split / _normalized）
```

顶部 import 变更：

```python
from dataclasses import dataclass, field          # 新增
from typing import Callable, Literal, Optional, Union   # Literal/Union 新增

from yate.editor_core.buffer import Pos           # 新增
```

docstring 变更（`session.py` 第 1-12 行）：**只增不减**——保留现有「UI free /
knows nothing about panes…」表述的含义（指 `EditorSession` 类），在末尾追加：

```
The module also carries the UI-free *window* model (``Leaf`` / ``Split`` /
``ViewState`` and the tree operations from the deleted ``pane_types`` module):
one ``Leaf`` is a document slot plus its per-document viewport state.  It lives
here because it is L1 state with L0-only dependencies, shared by ``EditorView``
and ``PaneManager`` without an intermediate type-only module.  ``EditorSession``
itself stays pane-agnostic: the window layout is owned by ``PaneManager`` (L2)
and composed by ``Editor`` (L3).
```

### G.4.2 步骤 2：切换 4 处消费者 import

| 文件 | 旧 | 新 |
|---|---|---|
| `yate/editor_view/editor.py:26` | `from .pane_types import Leaf` | `from yate.session import Leaf` |
| `yate/editor_view/panes.py:39-52` | `from yate.editor_view.pane_types import (...)` | `from yate.session import (...)`（符号列表不变） |
| `yate/editor.py:48` | `from yate.editor_view.pane_types import Axis, Leaf` | `from yate.session import Axis, Leaf` |
| `tests/test_panes.py:18-26` | `from yate.editor_view.panes import (MIN_FRACTION, Leaf, PaneManager, Split, find_axis_split, leaves)` + `from yate.session import EditorSession` | 拆为 `from yate.session import (EditorSession, Leaf, MIN_FRACTION, Split, find_axis_split, leaves)` + `from yate.editor_view.panes import PaneManager` |
| `tests/test_app_textual.py:29-30` | `from yate.editor_view.panes import Split as PaneSplit` / `leaves as pane_leaves` | `from yate.session import Split as PaneSplit` / `from yate.session import leaves as pane_leaves` |

> `yate/editor_view/panes.py` 的 import 需按仓库风格重排：`yate.editor_view.editor` /
> `yate.session` 属同组，`from yate.session import ...` 放在该组内（现有文件已在用
> 绝对路径风格 `from yate.editor_view.editor import EditorView`，保持一致）。

### G.4.3 步骤 3：删除 `panes.py` 的 deprecated 重导出

```python
# 删除前（panes.py 第 54-65 行）
# Re-export for backward compatibility -- external code imports from panes.
# DEPRECATED: prefer ``from yate.editor_view.pane_types import Axis, Leaf, ...``
# These re-exports may be removed in a future version.
__all__ = [
    "Axis", "Leaf", "Node", "Split", "ViewState",
    "PaneManager", "PaneHost",
]
```

```python
# 删除后：要么整段消失，要么收窄为
__all__ = ["PaneManager", "PaneHost"]
```

> **取舍**：`__all__` 里 `PaneManager` / `PaneHost` 是本模块自有符号，保留 `__all__` 无害。
> 若保留，注意它不再承担"兼容入口"职责，注释必须删除（避免误导为还有 deprecated 层）。
> 建议：**整段删除**（够干净），门禁会证明没有遗漏的引用者。

### G.4.4 步骤 4：删除 `yate/editor_view/pane_types.py`

删除前确认全仓无残留引用：

```powershell
rg -n "pane_types" yate tests tools
# 期望：0 命中（本 Plan 文档本身除外）
```

### G.4.5 步骤 5：文档回填（与代码同批提交）

| 文档 | 变更 |
|---|---|
| [architecture-boundaries.md](../../rules/architecture-boundaries.md) §一 L1 行 | `yate/session.py（EditorSession）` → `（EditorSession + 窗格树模型：Leaf/Split/ViewState/树操作）` |
| 同上 §二 职责表 L1 行 | 「可以做什么」补「窗格状态模型（无 UI）」；「不可以做什么」保持 `不 import editor_view、不碰 Textual` |
| 同上 §三.6 | 反例「（`pane_types.py` 的 `find_leaf` / `replace_node`…）」→「（`session.py` 的 `find_leaf` / `replace_node`…）」 |
| 同上 §六 | 若新增守护见 G.6.3，同步用例数与描述 |
| [README.md](README.md) §2 模块清单 | 删除 `pane_types.py` 条目；`session.py` 条目补「+ 窗格树模型」 |
| 同上 §4 冻结清单 | `PaneRegistry` 的"唯一新增环打断器"表述保持不变（本 Plan 不动它） |
| [plan_B_widget_selfhold.md](plan_B_widget_selfhold.md) §B.2 | `pane_types.py` 行迁移目标改为 `session.py`（保留历史说明：原为 `editor_view/pane_types.py`） |
| [../split_panes_plan.md](../split_panes_plan.md) 实施状态段 | `pane_types.py` 路径更新为 `session.py`，或追加一句"（2026-09-23 Plan G：已下沉至 `session.py`）" |
| `yate/resources/changelog.zh.md` / `.en.md` | 按项目惯例追加一条内部分层条目（若本轮随 CHANGELOG 一起发布） |

---

## G.5 设计取舍与被否方案

| 方案 | 判定 | 理由 |
|---|---|---|
| **并入 `session.py`（本 Plan）** | ✅ 采用 | 一次消灭两个入口（`pane_types.py` + `panes.py` 重导出）；L1 与 `EditorSession` 同模块，"状态放在正确的层"的规则表述可直接引用；不新增层平面文件 |
| 新建 `yate/panes.py`（L1） | ❌ 否 | 问题从"L2 有一个类型层"变成"L1 有两个并列状态入口"，且"窗格状态为何不在 session 里"仍需解释；一个文件能解决的事不拆两个 |
| 并入 `editor_core` | ❌ 否 | `ViewState.scroll_*` 是视口概念，会污染 `editor_core` 纯性（用户明确要求，且与 README/规则定义冲突） |
| 并入 `editor_view/panes.py` | ❌ 否 | 直接把类型级环退回源码层；且 R6 禁止 `TYPE_CHECKING`，`editor.py` 将无法在不 import `panes` 的情况下拿到 `Leaf` |
| 保留现状 + 只删重导出 | ❌ 否 | 治标：`pane_types.py` 仍在 L2 承担状态职责 |
| 同时把 `Leaf` 改名为 `Window` | ⏸ 延后 | 纯审美，波及面大（测试 + pilot + 文档）；独立一轮 |

### 明确的边界（本 Plan 不做）

- 不动 `EditorSession` 的任何方法/属性（窗格树**不**注入 session）；
- 不动 `PaneManager` / `PaneHost` 的结构操作与同步逻辑（`capture_active` / `apply_doc` 等留在 L2）；
- 不动 `PaneRegistry`（R2 冻结白名单）；
- 不动 `editor_core` 任何文件；
- 不引入新文件、不引入新 `Protocol`、不引入 `TYPE_CHECKING`。

---

## G.6 验收与门禁

### G.6.1 硬门禁（全绿才算完成）

```powershell
python -m pyright yate/ tests/ tools/      # 0 errors, 0 warnings, 0 informations
python -m pytest tests/ -q                 # 全绿
python -m pytest tests/test_architecture.py -q   # 12 passed（R1-R11 + 命名守卫）
python -m pytest tests/test_panes.py -q    # 窗格模型单测全绿
python -m yate --diag                      # 报告正常
python -m yate --version                   # 正常
```

### G.6.2 人工断言（搬运不改行为）

- `diff` 语义等价：`session.py` 新增段与删除的 `pane_types.py` **逐字一致**（仅 docstring/注释
  可增补），可用 `git show HEAD:yate/editor_view/pane_types.py` 与新段做对比；
- `rg -n "pane_types" yate tests tools` → **0 命中**；
- `rg -n "TYPE_CHECKING" yate tests tools` → **0 命中**（R6 不退化）；
- import 方向抽查：`python -c "import yate.session, yate.editor_view.panes, yate.editor_view.editor, yate.editor"` 无错；
- 反向依赖抽查：`rg -n "yate.editor_view" yate/session.py` → **0 命中**（R4 不退化）。

### G.6.3 可选：补一条架构守护（推荐）

`tests/test_architecture.py` 目前不守护"模型归属层"。可在本 Plan 顺手加一条低成本用例，
防止未来有人把 `Leaf` / `ViewState` 再挪回 L2：

```python
def test_pane_model_lives_in_l1_session() -> None:
    """The pane tree model is L1 state, not a widget-package type layer:
    ``session.py`` owns it; ``editor_view`` imports it, never re-exports it."""
    source = (YATE / "session.py").read_text(encoding="utf-8")
    for name in ("class Leaf", "class Split", "class ViewState", "def find_leaf"):
        assert name in source, name
    assert not (YATE / "editor_view" / "pane_types.py").exists()
    panes = (YATE / "editor_view" / "panes.py").read_text(encoding="utf-8")
    assert "backward compatibility" not in panes
```

> 若采纳，rules §六 的用例数由 12 → 13，需同步 [Plan E](plan_E_tests_tools.md) 的计数描述。

### G.6.4 冒烟（行为回归防护）

窗格是本轮唯一相关功能区，跑冒烟中与窗格相关的场景即可（若 `tools/smoke_test/scenarios/panes.py`
未覆盖全部，至少人工验证）：

- `:split` / `:vsplit` 后两窗格内容一致、各自光标/滚动独立；
- 同文档双窗格：一侧编辑，另一侧实时跟随内容（`ui_refresh` 联动）；
- `ctrl+w` 和弦：`s` / `v` / `q` / `o` / `h j k l` / `+ - < >` / `=`；
- `:only` / `:bd`（多窗共有文档后叶子正确改绑）；
- host-less 路径：`tests/test_panes.py` 全绿（结构操作不经 widget 的路径）。

---

## G.7 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 遗漏引用点导致 import error | 低 | 全仓仅 6 处引用（已核）；G.6.2 的 `rg` 断言兜底 |
| `session.py` 职责变宽，被误读为"session 管窗格" | 中 | 模块 docstring 明写边界（G.4.1）；`EditorSession` 类零改动；G.6.3 守护防回退 |
| 循环 import 在新位置复现 | 低 | `session.py` 只依赖 `editor_core`（已由 R4 守护）；import 链单向 |
| pyright 因 `Union` / `Literal` 新增 import 产生诊断 | 低 | `Node = Union[Leaf, Split]` 是既有写法，原样搬运；pyright strict 门禁验证 |
| `panes.py` 删 `__all__` 后对外可见符号变化 | 低 | 全仓已无 `from yate.editor_view.panes import <模型符号>` 的调用者（G.4.2 一并迁移）；`__all__` 只影响 `import *`，仓库内无该用法 |
| 文档脱节 | 中 | G.4.5 与代码同批提交；rules 变更属强制项（规则 §七） |

---

## G.8 完成定义（DoD）

- [x] `yate/editor_view/pane_types.py` 已删除；`session.py` 含完整窗格模型；
- [x] 4 处源码引用 + 2 处测试引用全部迁移，无 deprecated 重导出残留；
- [x] `rg -n "pane_types" yate tests tools` → 0；
- [x] pyright 0 诊断 / pytest 全绿 / `test_architecture.py` 全过；
- [x] `architecture-boundaries.md`、本目录 README §2、`plan_B` §B.2、`split_panes_plan.md` 已回填；
- [x] （已采纳 G.6.3）新增守护用例 `test_pane_model_lives_in_l1_session` 并通过，
  rules §六 与 [Plan E](plan_E_tests_tools.md) 计数同步（12 → 13）；
- [x] CHANGELOG：仓库 CHANGELOG 由 `tools.changelog` 自动生成（文件头写明
  *do not edit by hand*），本轮不手工追加，条目随提交信息生成。

---

## G.9 落地记录（2026-09-23 实测）

| 范围 | 结果 |
|---|---|
| `yate/editor_view/pane_types.py` | ✅ 删除（155 行整体迁入 `yate/session.py`，搬运段与原文件**逐字等价**：归一化换行后 `segment_equal=True`） |
| `yate/session.py` | 161 → **281 行**（非空行口径）：`EditorSession` 类零改动，新增窗格树模型段 120 行 |
| 消费者 import | ✅ `editor_view/editor.py` / `editor_view/panes.py` / `editor.py` / `tests/test_panes.py` / `tests/test_app_textual.py` 全部改到 `yate.session` |
| deprecated 重导出 | ✅ `panes.py` 的 `backward compatibility` 段与 `__all__` 已删（模型符号全仓无残留调用者） |
| pyright | ✅ `python -m pyright yate/ tests/ tools/` → **0 errors, 0 warnings, 0 informations** |
| pytest | ✅ `python -m pytest tests/ -q` exit 0 全绿；`test_architecture.py` + `test_panes.py` = **25 passed**（架构守护 12 → **13**） |
| 冒烟 | ✅ `python -m tools.smoke_test run --fail-only` → **86/86 场景、889/889 checks**（100%，exit 0，68.61s） |
| `--diag` / `--version` | ✅ 正常 |

### 与计划的偏离（实测依据）

| # | 项 | 处置 |
|---|---|---|
| 1 | G.6.2 要求 `rg -n "pane_types" yate tests tools` → **0 命中**，但 G.4.1 指定的 docstring 与 G.6.3 的守护断言本身都含 `pane_types` 字面量 | 保留历史说明与守护断言，`pane_types` 实际命中：**2 处**（`yate/session.py` L14 docstring、L207 分区注释，均为历史说明）+ **2 处**（`tests/test_architecture.py` L31 docstring、L307 断言）。`yate/` / `tests/` / `tools/` 中**无任何 import 或代码引用** |
| 2 | `tests/test_panes.py` 括号内符号序 | 采用仓库 isort 风格「常量 → 类 → 函数」（`MIN_FRACTION, EditorSession, Leaf, Split, find_axis_split, leaves`），与 G.4.2 片段的字母序略有差异；符号集合一致 |
| 3 | G.4.5 的 CHANGELOG 条目 | 不追加：CHANGELOG 为自动生成文件 |
| 4 | README §1 既有行数（`editor.py` 1245、`commands.py` 203）与实测不符 | 已按实测回填（`editor.py` 1274、`commands.py` 207）；差异非本轮造成（HEAD 上即如此，原值为 Plan A–F 时点旧值） |
