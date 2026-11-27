# 波次 2 子计划 B：`editor_components/editor.py` -> `view.py`

索引：[overview.md](overview.md) | 主计划：[../iktbxc-plan.md](../iktbxc-plan.md)
事实：[../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §C。

所有路径均相对仓库根（命令基准）。编辑前先读每个区域；不做盲目全局替换。`editor_view.py` 为**禁用**。

## 1. 输入 / 输出

输入：L2 模块 `yate/editor_components/editor.py`，持有 `PaneRegistry`（`:50`）与 `EditorView`（`:74`），有 14 处产品代码引用、1 处 tcss 注释、9 处测试引用、1 个冒烟场景、2 行规则与 1 行评审。
输出：`yate/editor_components/view.py`，类与行为不变；所有 import、docstring、守卫集合、tcss 注释、测试、冒烟场景、规则文本与当前架构 wiki 均同步。
独立提交：`refactor(editor-components): rename editor module to view`。

## 2. 独占文件清单

- `yate/editor_components/editor.py` -> `yate/editor_components/view.py`（`git mv`）
- `yate/editor.py`、`yate/editor_dispatch.py`、`yate/session.py`、`yate/editor_components/__init__.py`、`welcome.py`、`highlighting.py`、`panes.py`、`terminal.py`、`completion.py`、`yate/flows/mouse_flows.py`、`yate/flows/completion_flows.py`
- `yate/resources/editor-view.tcss`
- `tests/test_app_mouse.py`、`tests/test_app_panes.py`、`tests/test_dispatch_guards.py`、`tests/test_panes.py`、`tests/test_support_mouse.py`、`tests/test_architecture.py`
- `tools/smoke_test/scenarios/multi_cursor.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`

未触碰：`.trae/reviews/**`（只读记录）、`.trae/documents/**` 历史计划、`CHANGELOG*`、`SIZE_EXEMPT_FILES`、任何类名、tcss 文件名 `editor-view.tcss`（仅其注释中的路径字符串改动）。

## 3. 步骤

### 步骤 B1 —— 基线

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

退出码 0，37 个用例。

### 步骤 B2 —— 重命名

```powershell
git mv yate/editor_components/editor.py yate/editor_components/view.py
```

`git status --short` 必须显示 `R`。此前不存在 `view.py`（已核实）。

### 步骤 B3 —— 精确字符串编辑

每处 `yate.editor_components.editor` -> `yate.editor_components.view`、每处 `editor_components/editor.py` -> `editor_components/view.py`，以及每处 `~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView`：

| 文件:行 | 类型 | 旧 -> 新 |
|---|---|---|
| `yate/editor.py:61` | import | `from yate.editor_components.editor import EditorView` -> `...view import EditorView` |
| `yate/editor_dispatch.py:19` | import | 同上 |
| `yate/session.py:272` | 注释 | `editor_components/editor.py` -> `editor_components/view.py` |
| `yate/editor_components/__init__.py:5` | docstring 引用 | `~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView` |
| `yate/editor_components/__init__.py:26` | import 示例 | `from yate.editor_components.editor import EditorView` -> `...view...` |
| `yate/editor_components/welcome.py:3` | docstring | `:mod:\`yate.editor_components.editor\`` -> `:mod:\`yate.editor_components.view\`` |
| `yate/editor_components/highlighting.py:3` | docstring | 同上 |
| `yate/editor_components/panes.py:24` | docstring | 同上 |
| `yate/editor_components/panes.py:40` | import | `from yate.editor_components.editor import LEFT_BUTTON, EditorView` -> `...view...` |
| `yate/editor_components/terminal.py:40` | import | `from yate.editor_components.editor import LEFT_BUTTON` -> `...view...` |
| `yate/editor_components/completion.py:4` | docstring 引用 | `~yate.editor_components.editor.EditorView` -> `~yate.editor_components.view.EditorView` |
| `yate/flows/mouse_flows.py:3` | docstring 引用 | 同上 |
| `yate/flows/mouse_flows.py:19` | import | `from yate.editor_components.editor import LEFT_BUTTON, EditorView` -> `...view...` |
| `yate/flows/completion_flows.py:24` | import | `from yate.editor_components.editor import EditorView` -> `...view...` |
| `yate/resources/editor-view.tcss:2` | CSS 注释 | `editor_components/editor.py` -> `editor_components/view.py` |
| `tests/test_app_mouse.py:22` | import | `...editor import EditorView` -> `...view import EditorView` |
| `tests/test_app_panes.py:16` | import | 同上 |
| `tests/test_dispatch_guards.py:19` | import | 同上 |
| `tests/test_panes.py:26` | import | 同上 |
| `tests/test_support_mouse.py:31` | import | 同上 |
| `tools/smoke_test/scenarios/multi_cursor.py:18` | import | 同上 |
| `tests/test_architecture.py:130` | `ALLOWED_PROTOCOLS` **键** | `"editor_components/editor.py"` -> `"editor_components/view.py"` |
| `tests/test_architecture.py:213` | `UI_FROZEN_FILES` 值 | `"yate.editor_components.editor"` -> `"yate.editor_components.view"` |
| `tests/test_architecture.py:225` | `UI_FROZEN_FILES` 值 | 同上 |
| `tests/test_architecture.py:329` | docstring | `editor_components/editor.py` -> `editor_components/view.py` |
| `.trae/rules/architecture-boundaries.md:113` | R2 白名单文本 | `editor_components/editor.py::PaneRegistry` -> `editor_components/view.py::PaneRegistry` |
| `.trae/rules/architecture-boundaries.md:347` | 历史拆分注释 | `editor_components/editor.py` -> `editor_components/view.py` |
| `.trae/wikis/yate-architecture.md:167` | 表格文件单元格 | `` `editor.py::EditorView` `` -> `` `view.py::EditorView` `` |

两个 `UI_FROZEN_FILES` 键（`flows/completion_flows.py:208`、`flows/mouse_flows.py:223`）保持不变：仅其允许集值改动。`ALLOWED_PROTOCOLS` 值 `{"PaneRegistry"}` 保持不变。不重命名任何类、函数、常量、widget id 或 CSS 选择器。

### 步骤 B4 —— 负向演练（两处守卫）

演练 B4.1（R2 路径白名单）：
1. 在 `tests/test_architecture.py` 中临时把 `ALLOWED_PROTOCOLS` 键改回 `"editor_components/editor.py"`；核对磁盘。
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_new_protocols -q` 必须失败并点名 `editor_components/view.py` / `PaneRegistry`。
3. 还原新键、清理 `tests/__pycache__`，重跑 -> 退出码 0。

演练 B4.2（R11 冻结面）：
1. 临时把一个 `UI_FROZEN_FILES` 允许值改回 `"yate.editor_components.editor"`（例如 `flows/completion_flows.py` 的集合）；核对磁盘。
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_collaborators_keep_widget_coupling_frozen -q` 必须失败：`flows/completion_flows.py` 确实 import 了 `yate.editor_components.view`，而它此时不在 `allowed` 中。
3. 还原、清理 `tests/__pycache__`，重跑 -> 退出码 0。

两者均以 `git status --short` 只显示预期的 wave-2 diff 收尾。

### 步骤 B5 —— 验收

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_app_panes.py tests/test_dispatch_guards.py tests/test_panes.py tests/test_support_mouse.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
git grep -n -E "editor_components\.editor|editor_components/editor" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

均退出码 0；最后一条 grep 不打印任何内容（无匹配退出码 1 是预期信号，必须如此记录）。

### 步骤 B6 —— 提交与重命名检查

```powershell
git add -A
git commit -m "refactor(editor-components): rename editor module to view"
git --no-pager log --follow --oneline -- yate/editor_components/view.py
```

`git log --follow` 必须显示该 widget 模块重命名前的历史。

## 4. 风险 / 回滚

- 以旧路径为键的守卫集合是首要风险；演练 B4.1/B4.2 证明其生效，pyright + 全量 pytest 捕获任何遗漏 import。
- `yate/resources/editor-view.tcss` 名称有意保持不变（issue 非目标：除模块路径外不重命名类/资产）。
- 回滚：必要时在回退 wave 3 后 `git revert <wave-2 commit>`。

## 5. 回填（执行期间填写）

真实命令结果、退出码、两次演练结果、偏离记录。
