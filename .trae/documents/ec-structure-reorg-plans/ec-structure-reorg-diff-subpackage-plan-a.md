# Plan A: diff/ 子包化（wave-1）

## 输入

- `yate/editor_components/diffview.py`（581 行）
- `yate/editor_components/diff_pane.py`（488 行）

## 输出

- `yate/editor_components/diff/__init__.py`（惰性、零 re-export）
- `yate/editor_components/diff/screen.py`（原 diffview.py 内容）
- `yate/editor_components/diff/pane.py`（原 diff_pane.py 内容）
- 旧文件删除（`git mv` 保 rename）

## 独占文件清单

| 操作 | 文件 |
|---|---|
| git mv | `yate/editor_components/diffview.py` -> `yate/editor_components/diff/screen.py` |
| git mv | `yate/editor_components/diff_pane.py` -> `yate/editor_components/diff/pane.py` |
| 新增 | `yate/editor_components/diff/__init__.py` |
| 编辑 | `yate/flows/overlay_flows.py`（import 行） |
| 编辑 | `yate/editor_components/diff/screen.py`（原 diffview.py：内部 import + docstring） |
| 编辑 | `yate/editor_components/diff/pane.py`（原 diff_pane.py：docstring） |
| 编辑 | `tests/test_diffview.py`（import 行 ×4） |
| 编辑 | `tests/test_diff_integration.py`（import 行 ×2） |
| 编辑 | `tests/test_command_path_args.py`（import 行 ×2） |
| 编辑 | `tools/smoke_test/scenarios/diffview.py`（import 行 ×2） |
| 编辑 | `tests/test_architecture.py`（UI_FROZEN_FILES 键） |
| 编辑 | `.trae/rules/architecture-boundaries.md`（§三.7 已出名单注释） |
| 编辑 | `.trae/wikis/yate-architecture.md`（行 26/175 diffview/diff_pane 引用） |

## 具体修改

### 步骤 a.1 — git mv + 新增 __init__.py

```powershell
cd D:\Programming\yate-ec-structure-reorg
New-Item -ItemType Directory -Path yate\editor_components\diff -Force
git mv yate/editor_components/diffview.py yate/editor_components/diff/screen.py
git mv yate/editor_components/diff_pane.py yate/editor_components/diff/pane.py
```

新增 `yate/editor_components/diff/__init__.py`：

```python
"""Diff viewer subpackage: screen widget and per-side pane.

UI package (rules section 3.5): no re-exports here -- import the
submodules by name (``yate.editor_components.diff.screen`` / ``.pane``).
"""
```

### 步骤 a.2 — 更新 diff/screen.py 内部 import

[yate/editor_components/diff/screen.py](file:///D:/Programming/yate-ec-structure-reorg/yate/editor_components/diff/screen.py)
（原 diffview.py 内容）：

- 行 4：`from yate.editor_components.diff_pane import DiffPane, PaneDiffState`
  -> `from yate.editor_components.diff.pane import DiffPane, PaneDiffState`
- 行 3-6 docstring 中 `~yate.editor_components.diff_pane.DiffPane` /
  `~yate.editor_components.diff_pane.PaneDiffState`
  -> `~yate.editor_components.diff.pane.DiffPane` /
  `~yate.editor_components.diff.pane.PaneDiffState`

### 步骤 a.3 — 更新 diff/pane.py docstring

[yate/editor_components/diff/pane.py](file:///D:/Programming/yate-ec-structure-reorg/yate/editor_components/diff/pane.py)
（原 diff_pane.py 内容）：

- 行 3：`:mod:`yate.editor_components.diffview``
  -> `:mod:`yate.editor_components.diff.screen``
- 行 6：`~yate.editor_components.diffview.DiffScreen`
  -> `~yate.editor_components.diff.screen.DiffScreen`

### 步骤 a.4 — 更新消费方 import

| 文件 | 行 | 旧 | 新 |
|---|---|---|---|
| `yate/flows/overlay_flows.py` | 24 | `from yate.editor_components.diffview import MAX_DIFF_LINES, DiffScreen` | `from yate.editor_components.diff.screen import MAX_DIFF_LINES, DiffScreen` |
| `tests/test_diffview.py` | 23 | `from yate.editor_components.diff_pane import DiffPane` | `from yate.editor_components.diff.pane import DiffPane` |
| `tests/test_diffview.py` | 24 | `from yate.editor_components.diffview import DiffScreen` | `from yate.editor_components.diff.screen import DiffScreen` |
| `tests/test_diffview.py` | 1101 | `from yate.editor_components.diff_pane import PaneDiffState` | `from yate.editor_components.diff.pane import PaneDiffState` |
| `tests/test_diffview.py` | 1114 | `from yate.editor_components.diff_pane import _BADGES` | `from yate.editor_components.diff.pane import _BADGES` |
| `tests/test_diff_integration.py` | 19 | `from yate.editor_components.diff_pane import DiffPane` | `from yate.editor_components.diff.pane import DiffPane` |
| `tests/test_diff_integration.py` | 20 | `from yate.editor_components.diffview import MAX_DIFF_LINES, DiffScreen` | `from yate.editor_components.diff.screen import MAX_DIFF_LINES, DiffScreen` |
| `tests/test_command_path_args.py` | 21 | `from yate.editor_components.diff_pane import DiffPane` | `from yate.editor_components.diff.pane import DiffPane` |
| `tests/test_command_path_args.py` | 22 | `from yate.editor_components.diffview import DiffScreen` | `from yate.editor_components.diff.screen import DiffScreen` |
| `tools/smoke_test/scenarios/diffview.py` | 27 | `from yate.editor_components.diff_pane import DiffPane` | `from yate.editor_components.diff.pane import DiffPane` |
| `tools/smoke_test/scenarios/diffview.py` | 28 | `from yate.editor_components.diffview import DiffScreen` | `from yate.editor_components.diff.screen import DiffScreen` |

### 步骤 a.5 — 更新守卫集合

[tests/test_architecture.py](file:///D:/Programming/yate-ec-structure-reorg/tests/test_architecture.py)
行 233：

```python
# 旧
"yate.editor_components.diffview",
# 新
"yate.editor_components.diff.screen",
```

### 步骤 a.6 — 更新规则文档

[.trae/rules/architecture-boundaries.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/rules/architecture-boundaries.md)

- 行 367-368：`editor_components/diffview.py`（2026-10-08 big-module-split b 波：Pane 侧
  迁入 `diff_pane.py`，screen 侧留在原文件，两文件均低于阈值）
  -> 更新为：`editor_components/diffview.py` + `diff_pane.py`（2026-10-08 big-module-split b 波
  拆分；2026-11-03 进一步子包化为 `diff/screen.py` + `diff/pane.py`，两文件均低于阈值）

[.trae/wikis/yate-architecture.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/wikis/yate-architecture.md)

- 行 26：`diffview / diff_pane` -> `diff/screen / diff/pane`
- 行 175：`diffview.py::DiffScreen` / `diff_pane.py::DiffPane`
  -> `diff/screen.py::DiffScreen` / `diff/pane.py::DiffPane`

### 步骤 a.7 — 验收门禁

```powershell
cd D:\Programming\yate-ec-structure-reorg
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate -q  # 覆盖率 >= 75%
.venv\Scripts\python.exe -m tools.smoke_test
```

残留 grep（期望 0 命中）：

```powershell
.venv\Scripts\python.exe -c "import subprocess; r = subprocess.run(['rg', '--type', 'py', 'editor_components\.diffview|editor_components\.diff_pane', 'yate/', 'tests/', 'tools/'], capture_output=True, text=True); print(r.stdout); exit(1 if r.stdout.strip() else 0)"
```

### 步骤 a.8 — 负向演练（R15 守卫验证）

临时在 `yate/editor_components/diff/screen.py` 中删除 `apply_slim_scrollbars` 调用
（DiffScreen 继承 ModalScreen，是 ScrollView 子类，R15 守卫应拦截），运行
`test_scrollable_widgets_apply_theme_scrollbar_pair` 确认失败，然后还原。

```powershell
# 演练步骤（手工）：
# 1. 临时注释 diff/screen.py 中的 apply_slim_scrollbars 调用
# 2. 运行 .venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_scrollable_widgets_apply_theme_scrollbar_pair -q
# 3. 期望：FAILED（offenders 包含 diff/screen.py）
# 4. 还原注释
```

### 步骤 a.9 — 独立提交

```powershell
git add -A
git commit -m "refactor(editor-components): subpackage diff/ (screen + pane)"
```

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| git mv 丢失 rename 历史 | 用 `git mv` 而非手动 mv + add；提交后 `git log --follow` 验证 |
| R15 守卫漏扫子包 | R15 测试用 `rglob("*.py")` 递归扫，子包自动覆盖；负向演练确认 |
| 消费方遗漏 | 全仓 grep 已取证（7+7 处），步骤 a.4 逐条对齐 |
| 回滚 | `git revert <commit>` 单提交回滚，零行为变化 |
