# plan-b：流程模块统一 *Flows（flows-rename）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 用户裁定：流程模块命名统一 `*Flows`（Controller 不好）；lsp_sync 语义准确保留。
> 纯重命名，行为零变更，不新增测试用例。

## 一、改动清单

| 现状 | 目标 | 方式 |
|---|---|---|
| `shell_flow.py::ShellFlow` | `shell_flows.py::ShellFlows` | `git mv` + 类改名 |
| `overlays.py::OverlayController` | `overlays.py::OverlayFlows` | 类改名（文件名不动） |
| `completion.py::CompletionController` | `completion.py::CompletionFlows` | 类改名（文件名不动） |
| `prompt_flows.py::PromptFlows` | 已合规 | 不动 |
| `lsp_sync.py::LspSync` | 语义准确 | 不动 |

**成员名不变**：ed.shell / ed.overlays / ed.completion / ed.prompt_flows（Editor 内
`shell_flow.ShellFlow` 类型注解与 import 随之更新，:54/:68/:280 与 `_build_pane_stack`
:226/:237、类注解区 :279-282）。

## 二、步骤

1. `git mv yate/shell_flow.py yate/shell_flows.py`；类 `ShellFlow`→`ShellFlows`
   （含 docstring 自引）；overlays.py / completion.py 类改名及 docstring 自引。
2. editor.py：import（:33 CompletionController、:54 ShellResult 无关、:68 ShellFlow、
   :54 OverlayController 行）与注解更新；成员赋值名不变。
3. tests：`git grep -n "shell_flow\|ShellFlow\|OverlayController\|CompletionController"`
   逐处更新——已知 test_app_textual.py:1937 patch 目标
   `yate.shell_flow.run_shell` → `yate.shell_flows.run_shell`；docstring 提及处
   一并改正（AST 用例的 docstring 豁免不适用于字符串 patch 目标）。
4. **规则同步**（architecture-boundaries §七）：
   - architecture-boundaries.md：自检清单「`*Controller` 仅限流程类如
     CompletionController」→「流程模块按职责命名：UI 流程编排一律
     `*Flows`，同步适配器按动词命名如 `LspSync`；禁止新增
     `*Controller`」（不再以「LspSync 例外」措辞，sync 亦是职责名）；
     §六命名守卫行同步；grep 全文 `shell_flow`/`Controller` 残留更正。
   - tests/test_architecture.py：UI_FROZEN_FILES `shell_flow` 条目 → `shell_flows`；
     命名守卫 `test_no_banned_identifier_names` 把 `*Controller` 加入禁用列表
     （收紧后全仓必须 0 命中，白名单 `PaneHost`/`PaneManager`/`LspManager` 不变）。
5. 提交：`refactor: unify flow module naming to *Flows`。

## 三、验收命令（全部退出码 0；探针退出码 1 = 通过）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
git grep -n -I "ShellFlow\b\|OverlayController\|CompletionController" -- yate tests tools
Get-ChildItem yate -Filter shell_flow.py   # 应不存在
```

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| 字符串 patch 目标漏改 | grep 双模式兜底；pytest 捕获 |
| 命名守卫收紧误伤 | 收紧前 grep 确认全仓 `*Controller` 仅这三个类；架构测试负向演练 |
| 回滚 | 单笔提交 `git revert` |
