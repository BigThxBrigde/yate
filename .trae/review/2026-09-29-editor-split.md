# editor-split 系列评审 — 2026-09-29

> 评审方式：code-review-expert 剧本（子代理独立评审 + 主代理复核门禁）。
> 方案来源：[`.trae/documents/editor-split-plans/overview.md`](../documents/editor-split-plans/overview.md)
> （总纲 + plan-a…plan-f，各子计划 §八为执行记录）。本文是**只读事实文档**：只记录
> 发现与核对结论，不放修复排期。

## 一、评审对象

分支 `ref/editor-refactoring`，基线 `a267b7d`（master 合并点）→ `d1c1a2c`，
editor-split 系列 5 个代码提交：

| 提交 | 内容 |
|---|---|
| `e6d32ac` | 流程模块统一 `*Flows` 命名（plan-b） |
| `d634079` | 删除 Editor 全部薄委托/薄壳（23 个），调用方直调（plan-c） |
| `0cff320` | 抽取 DocumentFlows（文档生命周期 19 方法，plan-d） |
| `63717cf` | 抽取 WindowFlows（窗格命令 + ctrl+w 弦，plan-e） |
| `d1c1a2c` | 抽取 ExtensionFlows（扩展装载/信任/LSP 注册，plan-f） |

结果形态：editor.py 1425 → 882 行；新增 3 个 L3 流程模块
`document_flows.py` / `window_flows.py` / `extension_flows.py`，与既有
OverlayFlows / CompletionFlows / ShellFlows / PromptFlows / LspSync 同构
（构造注入具体对象，R8；零向上依赖）。

## 二、门禁实测（评审代理与主代理各跑一轮，均退出码 0）

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/`（strict） | 0 errors / 0 warnings |
| `pytest tests/ -q --cov=yate --cov-fail-under=75` | 全绿；覆盖率 **90.70%**（document_flows 81%、window_flows 89%、extension_flows 82%、editor.py 87%） |
| `pytest tests/test_architecture.py -q` | **20 passed** |
| `python -m tools.smoke_test run` | **932/932 checks，89/89 scenarios** |
| `python -m yate --diag` | 退出码 0，`[extensions]` 节正常（plan-f 验收附加项） |

迁移完整性探针：被迁成员名（`open_path` / `cycle_tab` / `window_pending` /
`trust_cwd_extensions` 等）在 editor.py 中 grep 零残留。

## 三、发现

**Blocker：无。Major：无。**

逐行对照基线 `a267b7d` 核验的关键面（全部确认等价）：

- 迁移方法（open/save/close/cycle、split 簇、ctrl+w 弦状态机、扩展启动流）为忠实迁移：
  kind、worker group、守卫逐项一致；R10（handle_key 派发）未动。
- 晚挂钩子安全：`explorer_tree.open_path` / `window_prefix` 均在 `__init__`
  同步期内赋值（任何事件循环迭代之前），explorer 侧三处调用点均有 `is not None` 守卫。
- `load_startup_services` 返回 `list[str]`：on_mount 在原时点 extend 缓冲；
  headless `--diag` 丢弃返回值与旧行为等价（缓冲本就不冲刷）。
- 二段注入 `DocumentFlows.attach_pane_stack` 成立：panes/completion 的全部使用
  均在挂载后或 attach 后。
- 架构边界：流程模块零 `yate.editor` / `yate.app` 导入；
  `UI_FROZEN_FILES` 白名单与真实导入精确一致；无新增 Protocol / TYPE_CHECKING / Any；
  R5（editor 不反向 import 内置表）完好；规则文本与守卫同步。

**Minor：3 条**（均不阻断）：

| # | 位置 | 内容 | 处置 |
|---|---|---|---|
| 1 | `yate/document_flows.py`（attach_pane_stack 双属性） | `panes` / `completion` 仅在 `attach_pane_stack` 赋值，类体无声明，二段注入不变量靠调用纪律维持 | ✅ 已当场修复（`a4990c2`：类体注解，与 Editor 工厂装配属性惯例一致） |
| 2 | `yate/extension_flows.py::load_startup_services` | 时序细微差：旧代码先 extend 缓冲后注册服务器；现告警在注册之后才返回，若 `register_server` 抛错则告警丢失。当前注册为纯内存操作，不可观测 | 📌 信息级登记（无行为差异，无需改动） |
| 3 | `yate/editor.py::_build_pane_stack` docstring | 仍只枚举 4 个控制器，未提及 DocumentFlows 接线与 WindowFlows 构造 | ✅ 已当场修复（`a4990c2`） |

## 四、结论

**通过，可合并。** 0 blocker / 0 major；3 minor 中 2 条当场修复（`a4990c2`）、
1 条信息级保留。系列为行为保持的纪律性拆分：门禁全绿、架构边界守卫化、
命名统一 `*Flows`、每波单独提交可独立 revert。
