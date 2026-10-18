# 子计划 d —— `yate/services/__init__.py` 门户 docstring（Fix-C3 代码侧）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 来源：审计记录 S-4（门户 docstring 只列 3 项，实际 10 个模块）
- 波次：wave-2｜独占文件：`yate/services/__init__.py`（**只改这一个文件**，且**只改模块 docstring**）
- 前置依赖：无

## 一、目标

模块 docstring 补齐职责清单（10 个成员 + 子包），保留既有"deliberately not re-exported"
约束说明。**不得**改动任何代码语句、`__all__` 或导入。

## 二、逐处改动（逐字替换整个模块 docstring）

现状：
```python
"""Service layer: workspace tree, shell execution and extension loading.

Submodules are deliberately **not** re-exported: importing this package
(e.g. ``from yate.services import fonts``) must not eagerly load the
extension loader and the rest of the service stack. Import from the
submodule that defines the symbol
(``from yate.services.workspace import Workspace``).
"""
```
目标：
```python
"""Service layer: the UI-free services the editor and the shell share.

Members (each imported from its own submodule):

* :mod:`yate.services.workspace` -- workspace tree / file system browsing;
* :mod:`yate.services.shell` -- shell command execution;
* :mod:`yate.services.clipboard` -- system clipboard (degrade-safe wrapper);
* :mod:`yate.services.fonts` -- bundled Nerd Font detection and user install;
* :mod:`yate.services.trust` -- workspace trust store for extension auto-loading;
* :mod:`yate.services.user_setup` -- one-time ``~/.yate/`` setup and cleanup;
* :mod:`yate.services.events` -- editor event hub for extension scripts;
* :mod:`yate.services.idle_tracker` -- idle-input tracking for the screensaver;
* :mod:`yate.services.yxp` -- ``.yxp`` package read / verify / install (no
  extension runtime coupling, so it stays out of ``services/extensions/``);
* :mod:`yate.services.extensions` -- the L3 extension machinery subpackage.

Submodules are deliberately **not** re-exported: importing this package
(e.g. ``from yate.services import fonts``) must not eagerly load the
extension loader and the rest of the service stack. Import from the
submodule that defines the symbol
(``from yate.services.workspace import Workspace``).
"""
```

## 三、验收命令

```powershell
git --no-pager diff --stat yate/services/__init__.py
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/                        # 期望 0/0/0
.venv\Scripts\python.exe -m pytest tests/ -q -k "services or diagnostics or dist or yxp"
```

- 判定：diff 仅 docstring 区域变化（`git diff` 目视确认无代码语句变化）；import 顺序与
  `from __future__ import annotations` 位置不变；
- 含代码文件改动 → 不走纯文档豁免，最终由总纲 §四 全量门禁兜底；
- 输出：改动清单 + 命令输出与退出码。

## 四、风险与回滚

- 误改代码语句会触发 pyright/pytest → diff 目视 + 命令兜底；
- docstring 语言为英文（misc-rules §四），行宽 ≤100（python-coding-style §1.1）；
- 回滚：`git revert <本步提交 sha>`。
