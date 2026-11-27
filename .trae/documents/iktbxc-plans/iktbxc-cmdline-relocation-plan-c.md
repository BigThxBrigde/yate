# 波次 3 子计划 C：将 `cmdline_completions` 迁出 L3 `flows/`

索引：[overview.md](overview.md) | 主计划：[../iktbxc-plan.md](../iktbxc-plan.md)
事实：[../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §D/§E/§G。

所有路径均相对仓库根（命令基准）。编辑前先读每个区域；不做盲目全局替换。

## 1. 设计决定（偏离记录于主计划 §3/C4）

`git mv yate/flows/cmdline_completions.py yate/cmdline_completions.py`，另加一条新的 `_LAYER_RANKS` 条目 `("cmdline_completions.py", 1)`。

为何取 rank 1：该模块在 `:12-14` import `yate.registries`（L1）、`yate.session`（L1）与 `yate.services.workspace`（L0）。`_layer_rank()` 对未列出路径默认取 0，`UPWARD_EDGES_FROZEN` 为空，且 `test_no_unregistered_upward_imports` 拒绝任何目标 rank 高于源 rank 的 import。取 rank 1 时两处 L1 import 为同层、L0 import 为向下：零新增向上边，被迁移模块内零 import 行改动。从其唯一消费方 `yate/editor_compose.py`（rank 3）看，新 import 是向下的。这是 issue 的第二个建议目标；第一个（`services/` L0）在主计划 §3/C2-C3 中被否决。

## 2. 输入 / 输出 / 独占文件清单

输出：根级 L1 纯函数模块；规则文本、守卫 rank、wiki、注释与测试 import 均已同步；零运行时行为变更。
独立提交：`refactor(architecture): relocate cmdline_completions out of flows`。

文件：
- `yate/flows/cmdline_completions.py` -> `yate/cmdline_completions.py`（`git mv`）
- `yate/editor_compose.py`、`yate/config.py`、`yate/services/extensions/api.py`
- `tests/test_app_find.py`、`tests/test_cmdline_completions.py`、`tests/test_workspace_filter.py`、`tests/test_architecture.py`
- `tools/smoke_test/scenarios/guards.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`
- `README.md`、`README.zh.md`：**核实无需改动** —— 两者都已在根 `yate/` 树中列出裸文件名（`:272` / `:290`），迁移后即准确；因此不触发双语同步。

未触碰：`yate/flows/__init__.py`（无再导出、0 处引用）、`yate/services/__init__.py`、`tests/test_set_options.py:45`（测试名已用裸函数名）、`.trae/documents/**` 历史计划、`.trae/reviews/**`、`CHANGELOG*`、`tools/changelog/zh_overrides.json`、`UI_FROZEN_FILES`（它没有 `flows/cmdline_completions.py` 键）、P2 文件。

## 3. 步骤

### 步骤 C1 —— 基线

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmdline_completions.py tests/test_app_find.py -q
```

退出码 0。

### 步骤 C2 —— 重命名

```powershell
git mv yate/flows/cmdline_completions.py yate/cmdline_completions.py
```

`git status --short` 显示 `R`。模块正文（53 行）未变；其中无 import 改写。

### 步骤 C3 —— 精确字符串编辑

| 文件:行 | 类型 | 旧 -> 新 |
|---|---|---|
| `yate/editor_compose.py:33` | import | `from yate.flows.cmdline_completions import cmdline_completions` -> `from yate.cmdline_completions import cmdline_completions`（在 `from yate.*` 组内重新按字母序排列） |
| `yate/config.py:12` | 模块 docstring | `:mod:\`yate.flows.cmdline_completions\`` -> `:mod:\`yate.cmdline_completions\`` |
| `yate/config.py:290` | `#:` 注释 | `` ``flows/cmdline_completions`` `` -> `` ``cmdline_completions`` `` |
| `yate/services/extensions/api.py:411` | 注释 | `` ``flows/cmdline_completions.py`` `` -> `` ``cmdline_completions.py`` `` |
| `tests/test_app_find.py:18` | import | `from yate.flows.cmdline_completions import cmdline_completions` -> `from yate.cmdline_completions import cmdline_completions`（重新排序） |
| `tests/test_cmdline_completions.py:28` | import | 同上 |
| `tests/test_workspace_filter.py:887` | 注释 | `migrated from flows/cmdline_completions, 2026-10-30` -> `migrated from cmdline_completions, 2026-10-30`（保留历史日期，去掉过时路径） |
| `tools/smoke_test/scenarios/guards.py:200` | docstring | `yate/flows/cmdline_completions.py` -> `yate/cmdline_completions.py` |
| `tests/test_architecture.py:25` | 模块 docstring | 从 R11 协作者列表移除 `` ``flows/cmdline_completions.py`` ``（它不再位于 `flows/`） |
| `tests/test_architecture.py:141-158` | `_LAYER_RANKS` | 在 L1 组添加 `("cmdline_completions.py", 1)`，并加一条 `#:` 注释说明两处 L1 import 与无向上边的不变式 |

规则文本（`.trae/rules/architecture-boundaries.md`）：

| 行 | 章节 | 编辑 |
|---|---|---|
| `:25` | §一 L3 `flows/` 清单 | 从 L3 列表移除 `cmdline_completions.py` |
| `:31-37` | §一 L1 清单 | 添加 `cmdline_completions.py` 并注明：纯提示补全计算，消费 `registries` / `session`（L1）与 `services/workspace`（L0）；在 `tests/test_architecture.py` 中 rank 注册为 L1 |
| `:133` | R11 flows 枚举 | 移除 `cmdline_completions.py` |
| `:139-142` | R11 关于已移除 `UI_FROZEN_FILES` 条目的注释 | 改写为说明该模块经 IKTBXC 离开 `flows/`、现位于 L1 根级；白名单条目仍保持缺失 |
| `:268` | §二 职责表 | 把 `flows/cmdline_completions.py` 示例替换为根级 `cmdline_completions.py`（或去掉示例，保留纯函数分类） |
| `:297` | §三.6 纯计算清单 | 保留 `cmdline_completions` 并标注其新的根级 L1 位置 |
| `:457` | §六 R11 守卫清单 | 移除 `flows/cmdline_completions.py` |
| §六 37 例表 | 不变（本任务无新增架构用例） |

架构 wiki（`.trae/wikis/yate-architecture.md`）：

| 行 | 编辑 |
|---|---|
| `:23` | Mermaid FLOWS 节点：去掉 `+ lsp_sync/cmdline_completions` -> `+ lsp_sync` |
| `:151` | 表格行 `flows/completion_flows.py / flows/cmdline_completions.py` -> `flows/completion_flows.py` + `cmdline_completions.py`（根级 L1），描述沿用 "prompt completion" |
| `:159` | flows 清单：从 `flows/*` 行移除 `cmdline_completions.py::cmdline_completions`，另加一条根级 L1 行 |

规则文件的硬依赖图中无需为任何 Mermaid 节点新增边：根模块是 L1 消费方，通过 rank 标注体现，而非新增跨层箭头。

### 步骤 C4 —— 负向演练（层级 rank 守卫）

1. 在 `tests/test_architecture.py` 中临时移除新加的 `("cmdline_completions.py", 1)` 条目；核对磁盘。
2. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_unregistered_upward_imports -q` 必须失败，报 `unregistered upward import(s)` 且消息含 `cmdline_completions.py -> yate.registries` 与 `cmdline_completions.py -> yate.session`。
3. 还原条目、核对磁盘、清理 `tests/__pycache__` 与 `yate/__pycache__`，重跑 -> 退出码 0。
4. `git status --short` 只显示预期的 wave-3 diff。

### 步骤 C5 —— 验收

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmdline_completions.py tests/test_app_find.py tests/test_set_options.py tests/test_workspace_filter.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m yate --help
git grep -n -E "flows\.cmdline_completions|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

均退出码 0；最后一条 grep 不打印任何内容（预期无匹配退出码 1）。

### 步骤 C6 —— 提交与重命名检查

```powershell
git add -A
git commit -m "refactor(architecture): relocate cmdline_completions out of flows"
git --no-pager log --follow --oneline -- yate/cmdline_completions.py
```

## 4. 风险 / 回滚

- 守卫 rank 遗漏是首要风险；C4 演练证明该条目承载关键。
- 规则文本漂移：六处规则位置均落在同一提交。
- 过时注释/README：残余 grep + 人工 `git grep` 分诊。
- 回滚：`git revert <wave-3 commit>`（必要时再回退 wave 2/1）。

## 5. 回填（执行期间填写）

真实命令结果、退出码、C4 演练证据、偏离记录。
