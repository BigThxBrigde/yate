# Plan B: theme/ 子包化（wave-2）

## 输入

- `yate/editor_components/theme.py`（193 行）
- `yate/editor_components/themes.py`（599 行）
- `yate/editor_components/theme_files.py`（137 行）
- `yate/editor_components/cells.py`（148 行，留根）

## 输出

- `yate/editor_components/theme/__init__.py`（广播枢纽 + 门面再导出，原 theme.py 内容）
- `yate/editor_components/theme/themes.py`（原 themes.py 内容）
- `yate/editor_components/theme/files.py`（原 theme_files.py 内容）
- `yate/editor_components/cells.py` 留根不动

## 独占文件清单

| 操作 | 文件 |
|---|---|
| git mv | `yate/editor_components/theme.py` -> `yate/editor_components/theme/__init__.py` |
| git mv | `yate/editor_components/themes.py` -> `yate/editor_components/theme/themes.py` |
| git mv | `yate/editor_components/theme_files.py` -> `yate/editor_components/theme/files.py` |
| 编辑 | `yate/editor_components/theme/__init__.py`（内部 import 路径 + docstring） |
| 编辑 | `yate/editor_components/theme/files.py`（内部 import + docstring） |
| 编辑 | `yate/editor_components/theme/themes.py`（docstring 互引路径） |
| 编辑 | `yate/editor_components/terminal.py:47`（import themes） |
| 编辑 | `yate/editor_components/manual.py:59`（import themes） |
| 编辑 | `yate/editor_components/whichkey.py:17`（docstring 引用） |
| 编辑 | `tests/test_theme_trust.py`（import 行 ×3） |
| 编辑 | `tests/test_theme_files.py`（import 行 ×2 + docstring） |
| 编辑 | `tests/test_theme_palettes.py:456`（logger name string） |
| 编辑 | `tools/smoke_test/scenarios/modules.py`（import 行 ×2 + docstring） |
| 编辑 | `tests/test_architecture.py`（SIZE_EXEMPT_FILES 注释） |
| 编辑 | `.trae/rules/architecture-boundaries.md`（§三.5② 门面例外注记 + §三.7 已出名单） |
| 编辑 | `.trae/wikis/yate-architecture.md`（行 26/181 theme/themes/cells/theme_files 引用） |

## 具体修改

### 步骤 b.1 — git mv

```powershell
cd D:\Programming\yate-ec-structure-reorg
New-Item -ItemType Directory -Path yate\editor_components\theme -Force
git mv yate/editor_components/theme.py yate/editor_components/theme/__init__.py
git mv yate/editor_components/themes.py yate/editor_components/theme/themes.py
git mv yate/editor_components/theme_files.py yate/editor_components/theme/files.py
```

### 步骤 b.2 — 更新 theme/__init__.py 内部 import + docstring

- 行 9：`:mod:`yate.editor_components.themes`` -> `:mod:`yate.editor_components.theme.themes``
- 行 13：`:mod:`yate.editor_components.theme_files`` -> `:mod:`yate.editor_components.theme.files``
- 行 43：`from yate.editor_components.theme_files import (` -> `from yate.editor_components.theme.files import (`
- 行 49：`from yate.editor_components.themes import (` -> `from yate.editor_components.theme.themes import (`

### 步骤 b.3 — 更新 theme/files.py 内部 import + docstring

- 行 5：`yate.editor_components.themes.register_theme` -> `yate.editor_components.theme.themes.register_theme`
- 行 11：`:mod:`yate.editor_components.themes`` -> `:mod:`yate.editor_components.theme.themes``
- 行 22：`from yate.editor_components.themes import Theme, register_theme` -> `from yate.editor_components.theme.themes import Theme, register_theme`

### 步骤 b.4 — 更新 theme/themes.py docstring

- 行 26：`:mod:`yate.editor_components.theme`` -> `:mod:`yate.editor_components.theme``（不变，门面路径相同）
- 行 30：`:mod:`yate.editor_components.theme_files`` -> `:mod:`yate.editor_components.theme.files``

### 步骤 b.5 — 更新消费方 import

| 文件 | 行 | 旧 | 新 |
|---|---|---|---|
| `yate/editor_components/terminal.py` | 47 | `from yate.editor_components.themes import Theme` | `from yate.editor_components.theme.themes import Theme` |
| `yate/editor_components/manual.py` | 59 | `from yate.editor_components.themes import Theme` | `from yate.editor_components.theme.themes import Theme` |
| `tests/test_theme_trust.py` | 15 | `from yate.editor_components import themes` | `from yate.editor_components.theme import themes` |
| `tests/test_theme_trust.py` | 16 | `from yate.editor_components.theme_files import ...` | `from yate.editor_components.theme.files import ...` |
| `tests/test_theme_trust.py` | 23 | `from yate.editor_components.themes import THEMES` | `from yate.editor_components.theme.themes import THEMES` |
| `tests/test_theme_files.py` | 1 | docstring `yate.editor_components.theme_files` | `yate.editor_components.theme.files` |
| `tests/test_theme_files.py` | 19 | `from yate.editor_components import theme_files, themes` | `from yate.editor_components.theme import files, themes` |
| `tests/test_theme_files.py` | 20 | `from yate.editor_components.theme_files import ...` | `from yate.editor_components.theme.files import ...` |
| `tests/test_theme_palettes.py` | 456 | `logger="yate.editor_components.themes"` | `logger="yate.editor_components.theme.themes"` |
| `tools/smoke_test/scenarios/modules.py` | 10 | docstring `yate.editor_components.theme_files` | `yate.editor_components.theme.files` |
| `tools/smoke_test/scenarios/modules.py` | 21 | `from yate.editor_components.theme_files import load_theme_paths` | `from yate.editor_components.theme.files import load_theme_paths` |
| `tools/smoke_test/scenarios/modules.py` | 22 | `from yate.editor_components.themes import THEMES` | `from yate.editor_components.theme.themes import THEMES` |

### 步骤 b.6 — 更新 whichkey.py docstring

[yate/editor_components/whichkey.py](file:///D:/Programming/yate-ec-structure-reorg/yate/editor_components/whichkey.py)
行 17：`:mod:`yate.editor_components.themes`` -> `:mod:`yate.editor_components.theme.themes``

### 步骤 b.7 — 更新规则文档

[.trae/rules/architecture-boundaries.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/rules/architecture-boundaries.md)

- 行 275：`editor_components/theme.py` 作为主题广播枢纽与门面再导出
  -> `editor_components/theme/__init__.py` 作为主题广播枢纽与门面再导出
- 行 371-374：已出名单中 `editor_components/theme.py` 拆分记录
  -> 更新为子包化描述

[.trae/wikis/yate-architecture.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/wikis/yate-architecture.md)

- 行 26：`theme(hub) / themes / cells / theme_files` -> `theme/(hub+facade) / theme/themes / theme/files / cells`
- 行 181：`theme.py` 描述更新为 `theme/__init__.py`

### 步骤 b.8 — 验收门禁

```powershell
cd D:\Programming\yate-ec-structure-reorg
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate -q
.venv\Scripts\python.exe -m tools.smoke_test
```

残留 grep（期望 0 命中，theme/themes.py 自身除外）：

```powershell
.venv\Scripts\python.exe -c "import subprocess; r = subprocess.run(['rg', '--type', 'py', 'editor_components\.theme_files|editor_components\.themes', 'yate/', 'tests/', 'tools/'], capture_output=True, text=True); print(r.stdout); exit(1 if r.stdout.strip() else 0)"
```

### 步骤 b.9 — 负向演练（R15 守卫验证）

临时在 `yate/editor_components/theme/__init__.py` 中删除某处 `apply_slim_scrollbars`
调用（如有），或更简单地：确认 R15 rglob 扫描能递归进入 `theme/` 子包。
由于 theme/__init__.py 不定义 ScrollView 子类，R15 不会触发；负向演练改为
确认 `test_leaf_package_reexports_carry_exception_note` 不误伤 theme 子包
（theme 不是 L0 叶包，不在扫描面）。

### 步骤 b.10 — 用户面 API 兼容核查

`from yate.editor_components.theme import THEMES / register_theme / ...` 在
docs/yaterc.{en,zh}.md、docs/themes.{en,zh}.md、yaterc.example 共 8 处示例语句
**不变仍有效**——门面随子包到 `theme/__init__.py`，导入路径
`yate.editor_components.theme` 指向同一模块对象。仅核查周边模块路径表述文字
（docstring 中 `themes.py` / `theme_files.py` 已在步骤 b.2-b.4 更新）。

### 步骤 b.11 — 独立提交

```powershell
git add -A
git commit -m "refactor(editor-components): subpackage theme/ (hub + themes + files)"
```

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| 门面导入路径变化破坏用户代码 | `theme/__init__.py` 保持 `from yate.editor_components.theme import X` 有效 |
| cli.py N30 懒加载失效 | cli.py 用 `from yate.editor_components import theme as theme_mod`，包级 import 不变 |
| R15 rglob 漏扫子包 | rglob 递归，自动覆盖；负向演练确认 |
| 回滚 | `git revert <commit>` 单提交回滚 |
