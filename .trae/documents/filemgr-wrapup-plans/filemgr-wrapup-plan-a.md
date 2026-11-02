# plan-a：filemgr 包迁移（R2）

## 目标

把三个平铺文件收进独立子包 `yate/editor_view/filemgr/`，消除 `editor_view/` 根目录的 filemgr 三件套散落；`preview.py`（palette 共享预览管线）**不迁**。

## 迁移映射

| 旧 | 新 |
|---|---|
| `yate/editor_view/filemgr.py`（888 行，SIZE_EXEMPT 在案） | `yate/editor_view/filemgr/screen.py` |
| `yate/editor_view/filemgr_model.py` | `yate/editor_view/filemgr/model.py` |
| `yate/editor_view/filemgr_keys.py` | `yate/editor_view/filemgr/keys.py` |
| — | `yate/editor_view/filemgr/__init__.py`（**惰性、零 re-export**，§三.5②：`editor_view` 为 UI 包禁 re-export；docstring 一句话自述） |

git 操作用 `git mv` 保 renames 追踪。

## 波内步骤

### a-1 建包并迁移

1. `git mv yate/editor_view/filemgr.py yate/editor_view/filemgr/screen.py` 等（目录需先建 `__init__.py`）。
2. 新 `__init__.py`：仅模块 docstring（英文，说明"UI 包禁 re-export，子模块按名导入"），无代码。
3. 包内相互导入改绝对路径（`test_no_relative_imports` 禁 `from .X`）：
   - `screen.py` 中 `from yate.editor_view.filemgr_model import ...` → `from yate.editor_view.filemgr.model import ...`；
   - `from yate.editor_view.filemgr_keys import ...` → `from yate.editor_view.filemgr.keys import ...`。

### a-2 同步消费方导入

- `yate/flows/filemanager_flows.py:21`：`from yate.editor_view.filemgr import FileManagerScreen` → `from yate.editor_view.filemgr.screen import FileManagerScreen`（docstring 里 `:class:`~yate.editor_view.filemgr.FileManagerScreen`` 引用同步为 `...filemgr.screen.FileManagerScreen`）。
- `tools/smoke_test/scenarios/filemanager.py:25`：同上改导入。
- `tests/test_filemgr.py` / `tests/test_filemgr_model.py` / `tests/test_filemgr_flows.py` / `tests/test_app_filemgr.py`：全部旧导入路径改写。

### a-3 守卫面与文档同步

- `tests/test_architecture.py`：
  - `UI_FROZEN_FILES["flows/filemanager_flows.py"]` 的值 `yate.editor_view.filemgr` → `yate.editor_view.filemgr.screen`（约 :253）；
  - `SIZE_EXEMPT_FILES` 键 `editor_view/filemgr.py` → `editor_view/filemgr/screen.py`，并按守卫口径 `splitlines()` 复测行数更新豁免行注记（预期仍 >800，维持豁免；若 ≤800 则删除该键——以实测为准）。
- `.trae/rules/architecture-boundaries.md` §三.7 filemgr 豁免行（约 :314-320）：路径与行数同步，追加一句迁移登记（日期 + 本计划相对链接）。
- `yate/resources/filemgr-screen.tcss:2` 头注释路径同步。
- `yate/docs/file-manager.{en,zh}.md`：检查模块路径表述（双语同步是硬约束），如有 `editor_view/filemgr.py` 路径性表述改为新路径。

### a-4 验收

```bash
python -m pyright yate/ tests/ tools/
python -m pytest tests/ -q -n auto
python -m pytest tests/test_architecture.py -q
# 旧模块语义路径残留应为 0（包前缀本身除外）：
# grep -rn "editor_view\.filemgr import" yate/ tests/ tools/   → 0 命中
# grep -rn "editor_view\.filemgr_model|editor_view\.filemgr_keys" yate/ tests/ tools/   → 0 命中
# grep -rn "editor_view/filemgr\.py" .trae/ yate/   → 0 命中（规则文档历史描述行按随改随迁处理）
```

可见行为零变化：不改任何逻辑，纯移动 + 导入改写 + 守卫键/文档同步。

## 回滚

单提交 `refactor(filemgr): move file manager modules into a subpackage`；失败 `git reset --hard` 回到 plan-a 起点。

## 执行记录（2026-11-02）

- 已按计划完成，提交 `3a4dcff`（13 文件，+31/-21；三文件 `git mv` rename 追踪 95-100%）。
- 新 `filemgr/__init__.py` 仅英文 docstring（UI 包禁 re-export、按名导入子模块），零代码。
- `screen.py` 迁移后 882 行（splitlines 口径），维持豁免（后续 plan-b 波复测 954 行）。
- `yate/docs/file-manager.{en,zh}.md` 经 grep 核实无模块路径表述，未改动。
- 残留 grep：`editor_view.filemgr import`（不带 .screen/.model/.keys）与 `editor_view.filemgr_model` / `editor_view.filemgr_keys` 在 `yate/ tests/ tools/` 均 0 命中；`yate/resources/changelog.{en,zh}.md` 中的 `filemgr_model` 为历史 commit 注记（描述过去提交，不属活跃导入路径）。
- 验收：pyright 0 诊断 / pytest 全量绿 / 架构 37 passed。
- 环境注记：worktree 无自带 `.venv`，pyright 经 `--pythonpath` 指主仓 venv 解释器（后续 plan-b 波已建 `.venv` junction，git-ignored）。
