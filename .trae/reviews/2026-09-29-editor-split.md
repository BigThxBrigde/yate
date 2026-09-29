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
| 2 | `yate/extension_flows.py::load_startup_services` | 时序细微差：旧代码先 extend 缓冲后注册服务器；现告警在注册之后才返回，若 `register_server` 抛错则告警丢失。当前注册为纯内存操作，不可观测 | ✅ 同日 TRAE-code-review 复核确认后修复（`8d1fb42`：拆分 `load_extensions` / `register_configured_servers`，缓冲先于注册，精确恢复基线 on_mount 时序） |
| 3 | `yate/editor.py::_build_pane_stack` docstring | 仍只枚举 4 个控制器，未提及 DocumentFlows 接线与 WindowFlows 构造 | ✅ 已当场修复（`a4990c2`） |

## 四、结论

**通过，可合并。** 0 blocker / 0 major；3 minor 中 2 条当场修复（`a4990c2`）、
1 条信息级保留。系列为行为保持的纪律性拆分：门禁全绿、架构边界守卫化、
命名统一 `*Flows`、每波单独提交可独立 revert。

## 五、复核记录（同日 TRAE-code-review，双校验代理共识裁决）

对同一范围（`a267b7d..HEAD`）按通用评审流程二次评审：逐字对照基线取证 +
2 个独立校验代理对全部候选问题做存在性/严重度/可达性三重裁决。

- **确认并修复（`8d1fb42`，门禁全绿后提交）**：
  1. `extension_flows` 告警时序（= §三 #2，见上表）；
  2. `document_flows.open_path` try 范围过宽（基线逐字迁移的存量怪癖）：
     目录分支 OSError 曾静默落入 `_open_document` 误报 "not a text file"，
     现收窄 try 到 `is_dir` 探测、错误显式暴露；
  3. `open_path_async` 未挂载早退守卫（基线逐字迁移、全部调用方挂载后运行、
     不可达防御代码）：删除，与同步版尾部一致。
- **判为误报剔除**：DocumentFlows 二段注入无运行时守卫——`attach_pane_stack`
  在同步 `__init__` 内完成、用户流均在挂载后派发，运行时守卫即死代码
  （不变量已由 `a4990c2` 类注解固化）。
- 修复后门禁复测：pyright 0 诊断 / pytest 全绿（覆盖率 90.74%）/
  架构 20 passed / 冒烟 932/932 / `--diag` 退出码 0。

## 六、关联登记

同日 Gitee PR #37 平台 AI 审查（PR观察者，无阻断项、1 条可维护性建议）
已登记于 [2026-09-29-pr37-editor-split.md](2026-09-29-pr37-editor-split.md)。
