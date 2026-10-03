# dap-support 子计划总纲（overview）

主计划：[../dap-support-plan.md](../dap-support-plan.md)（设计权威：协议差异 §2、
包设计 §3-§4、TUI 集成 §5、测试方案 §8、时序 §11）。分支 `feat/dap-support`
（worktree `../yate-dap-support`）。本文档是波次编排与文件独占的**唯一事实来源**。

## 一、波次表

同波次内文件互不重叠，可并行（子代理批 2~3 个，硬上限 6）；波次间串行。
依赖列指明必须先完成的波次/子计划。

| 波次 | 子计划 | 主题 | 依赖 | 并行性 |
|------|--------|------|------|--------|
| W1 | [dap-support-keys-plan-a.md](dap-support-keys-plan-a.md) | 键位层带修饰 F 键 | — | 与 b 并行 |
| W1 | [dap-support-f5-migration-plan-b.md](dap-support-f5-migration-plan-b.md) | F5→F7 迁移与文档同步 | — | 与 a 并行 |
| W2 | [dap-support-protocol-plan-c.md](dap-support-protocol-plan-c.md) | `editor_dap/` 协议与类型 | — | 串行起点 |
| W2 | [dap-support-client-plan-d.md](dap-support-client-plan-d.md) | `DapClient` | c | 串行 |
| W2 | [dap-support-manager-plan-e.md](dap-support-manager-plan-e.md) | `DapManager` + 包导出 | d | 串行 |
| W3 | [dap-support-ext-bridge-plan-f.md](dap-support-ext-bridge-plan-f.md) | `DapExtensionBridge` + `api.dap` | e | 与 g/h 并行 |
| W3 | [dap-support-python-ext-plan-g.md](dap-support-python-ext-plan-g.md) | python_dap + JS 范例 | f | 与 f/h 并行 |
| W3 | [dap-support-config-plan-h.md](dap-support-config-plan-h.md) | `debug_options` 配置 | e | 与 f/g 并行 |
| W4 | [dap-support-tui-views-plan-i.md](dap-support-tui-views-plan-i.md) | DebugPanel / gutter / 状态栏 | c-e | 单独 |
| W5 | [dap-support-wiring-plan-j.md](dap-support-wiring-plan-j.md) | Editor 接线 / 动作 / 命令 / 键位 | a,b,e,f,i | 单独 |
| W6 | [dap-support-diagnostics-plan-k.md](dap-support-diagnostics-plan-k.md) | `--diag` dap 节 | j | 与 l 并行 |
| W6 | [dap-support-docs-plan-l.md](dap-support-docs-plan-l.md) | 双语文档 / 手册 / README | j,k | 与 k 并行 |

## 二、执行纪律

1. 每份子计划先读主计划对应章节，**以它为准，不要凭常识猜**；
2. 子代理只改自己名下的独占文件清单；**不得修改清单外任何文件**（含产品源码
   之外文档），确需改就停下上报主代理；
3. 写盘/执行命令的成员显式 `acceptEdits`；spawn 与探活同回合闭合；判死后
   不得原样重试，改主代理直接执行；
4. 只认落盘结果：主代理重跑该成员名下验收命令后才算完成；
5. 每个子计划完成后按 `git-commit-message.md` 单独提交一次
   （scope 取主题，如 `feat(editor_dap): ...`、`refactor(keymaps): ...`）；
   **只提交、不推送**。

## 三、每波次通用验收（波次收口时主代理跑）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

全量收尾门禁见主计划 §8.3（含 `--cov-fail-under=75` 与手动 debugpy 走查）。
