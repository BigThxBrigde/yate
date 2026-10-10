# plan-a：yate/ 包相对导入转绝对导入（wave-1）

> 隶属 [主计划](../abs-import-api-style-plan.md) 议题 1。独占文件域：`yate/**`（与 plan-b 的 `tools/**` 零重叠，可并行）。

## 一、输入

- 主计划 §二 议题 1 的事实清单：`yate/` 72 处相对导入、46 个文件（全量扫描 `^\s*from\s+\.+`）。
- 现行规则 [../../rules/python-coding-style.md](../../../rules/python-coding-style.md) §1.3（wave-2 才改文本，本步先改代码）。

## 二、改写规则（统一映射）

| 相对形态 | 绝对形态 |
|---|---|
| `from .X import Y` | `from yate.<pkg>.X import Y`（`<pkg>` 为文件所在包全名） |
| `from . import X`（子模块） | `from yate.<pkg> import X` |
| `from ..X import Y` | `from yate.<parentpkg>.X import Y` |
| 显式 re-import `from .X import Y as Y` | 绝对化后**保留** `as Y` 子句（pyright strict 的显式 re-export 语义） |

多行括号导入（`from .cells import (`）只改 `from` 行的模块路径，括号体不动。

## 三、改动文件清单（47 个）

### editor_view（16 文件 40 处）

| 文件 | 行号与改写 |
|---|---|
| [editor.py](../../../yate/editor_view/editor.py) | 33 `from . import theme` → `from yate.editor_view import theme`；34-36 `.highlighting`/`.scrollbars`/`.welcome` 同法 |
| [statusbar.py](../../../yate/editor_view/statusbar.py) | 28-30（`. import theme` / `.commandline` / `.icons`） |
| [explorer.py](../../../yate/editor_view/explorer.py) | 26-29 |
| [theme.py](../../../yate/editor_view/theme.py) | 32（多行 `.cells`）/ 40（多行 `.theme_files`）/ 45（多行 `.themes`） |
| [theme_files.py](../../../yate/editor_view/theme_files.py) | 20 `.themes` |
| [welcome.py](../../../yate/editor_view/welcome.py) | 17 `. import theme` |
| [terminal.py](../../../yate/editor_view/terminal.py) | 44-45 |
| [palette.py](../../../yate/editor_view/palette.py) | 40-42 |
| [modals.py](../../../yate/editor_view/modals.py) | 18-19 |
| [manual.py](../../../yate/editor_view/manual.py) | 43-44 |
| [diffview.py](../../../yate/editor_view/diffview.py) | 44-45 |
| [diff_pane.py](../../../yate/editor_view/diff_pane.py) | 36-37 |
| [commandline.py](../../../yate/editor_view/commandline.py) | 25-26 |
| [completion.py](../../../yate/editor_view/completion.py) | 30 |
| [chrome.py](../../../yate/editor_view/chrome.py) | 23-24 |
| [scrollbars.py](../../../yate/editor_view/scrollbars.py) | 26 |

示例（editor.py:33-36 改写后）：

```python
from yate.editor_view import theme
from yate.editor_view.highlighting import HighlightMixin
from yate.editor_view.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars
from yate.editor_view.welcome import _WelcomeRow, render_welcome_row, welcome_rows
```

### editor_lsp（3 文件 5 处）

| 文件 | 行号与改写 |
|---|---|
| [parsing.py](../../../yate/editor_lsp/parsing.py) | 24 → `from yate.editor_lsp.client import Completion, Diagnostic, DiagnosticSeverity` |
| [client.py](../../../yate/editor_lsp/client.py) | 30 `. import protocol` → `from yate.editor_lsp import protocol` |
| [manager.py](../../../yate/editor_lsp/manager.py) | 32 `. import parsing, protocol`；33 多行 `.client`；41-42 `from yate.editor_lsp.parsing import _from_utf16 as _from_utf16` / `_to_utf16 as _to_utf16`（保留 `as`） |

### editor_term（2 文件 6 处）

| 文件 | 行号与改写 |
|---|---|
| [__init__.py](../../../yate/editor_term/__init__.py) | 13-16 包根 re-export → `from yate.editor_term.emulator import ...` 等 4 行 |
| [emulator.py](../../../yate/editor_term/emulator.py) | 26 `from yate.editor_term.keys import key_to_terminal as key_to_terminal`（保留 `as`）；27 `.palette` |

### editor_sprites（25 文件 25 处）

- `yate/editor_sprites/chars/` 下 24 个精灵数据文件各 1 处：`from ._shared import SHARED` → `from yate.editor_sprites.chars._shared import SHARED`。完整文件名：bomberman, caine, coin, digdug, duck, fireflower, frog, galaga, gangle, ghost, goomba, iceclimber, jax, link, mario, megaman, mushroom, pacman, pomni, ragatha, samus, slime, snake, star（各 `:7`）。
- [characters.py](../../../yate/editor_sprites/characters.py) | 25 多行 `from .chars import (` → `from yate.editor_sprites.chars import (`。

### 顺手对齐（议题 3 表 #4，同主题导入区整理）

- [extensions.py](../../../yate/services/extensions.py) | 42-43：交换两行顺序，使 yate 导入组恢复字母序（`client` 在 `manager` 前）。改后：

```python
from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerConfig
from yate.editor_lsp.manager import LspManager
```

（`extensions.py` 无相对导入，仅此 2 行顺序调整，零行为变化。）

## 四、输出

- `yate/` 全部 72 处相对导入变为绝对形态；`from .` / `from ..` 在 `yate/` 下归零。
- 零行为变化：导入解析结果与改写前完全等价。

## 五、验收命令（worktree 根执行）

```powershell
# 1. 相对导入归零（应无输出，退出码 1 = 无匹配）
rg -n "^\s*from\s+\.+" yate/ ; if ($LASTEXITCODE -eq 1) { "CLEAN" } else { "FAIL" }

# 2. 类型门禁零诊断
.venv\Scripts\python.exe -m pyright yate/

# 3. 全量测试回归（含 28 个架构守卫）
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 六、风险与回滚

- 风险：无循环导入风险（导入图不变）；`from yate.editor_view import theme` 是子模块导入，与 `from . import theme` 等价，`editor_view/__init__.py` 惰性（不 re-export）不受影响。
- `editor_view/editor.py` / `editor_core/buffer.py` / `keymaps/vim.py` 在豁免名单——本计划不改其行数（每处替换同行数），无需更新 `SIZE_EXEMPT_FILES`。
- 回滚：本计划单独 commit；异常时 `git revert` 该 commit 即可，不影响 plan-b。
