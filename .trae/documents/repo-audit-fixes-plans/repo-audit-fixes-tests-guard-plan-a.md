# 子计划 plan-b：测试守护与覆盖说明（A6 守护测试 / A17 tests README）

> 所属波次：**wave-1**（与 rules-docstring / changelog-zh / assets 文件不重叠，可并行）。
> 执行者：**子代理**（仅 `tests/`，不改产品源码；subagent-workflow §一.3）。
> 来源：评审 A6 / A17；主计划 §四.3（PEP 735 否决理由）、F5。

## 一、输入

- A6：`pyproject.toml:24-53`（dev）与 `:57-88`（ts）26 个 tree-sitter 条目逐行重复，唯一同步手段是 `:28` 注释；ts 升级 dev 漏改时 `.[dev]` 的 strict 类型检查与 ts 后端版本漂移。
- A17：7 个根模块无同名 `test_<module>.py`（`dist_meta.py`、`document_flows.py`、`window_flows.py`、`extension_flows.py`、`overlays.py`、`prompt_flows.py`、`lsp_sync.py`），覆盖由 pilot 集成测试间接达成；`actions.py`+`commands.py` 合并进 `test_action_table.py`；约定未成文。
- 决策：A6 走守护测试路线（venv pip 24.3.1 < 25.1，PEP 735 缓做，见主计划 §四.3）。

## 二、独占文件清单

1. `tests/test_dependency_groups.py`（新增）
2. `tests/README.md`（新增）

## 三、具体修改

### 3.1 A6——依赖组一致性守护测试

`tests/test_dependency_groups.py`：stdlib `tomllib` 解析仓库根 `pyproject.toml`，取 `["project"]["optional-dependencies"]` 的 `dev` 与 `ts` 两组。

测试用例（文件内 2 个）：

1. `test_ts_group_subset_of_dev_group`
   - 前置：仓库根存在 `pyproject.toml`，`project.optional-dependencies` 含 `dev` 与 `ts`；
   - act：解析两组为 `dict[str, str]`（按包名小写归一，含 extras/版本约束整串为值）；
   - 断言：ts 组每个包名都出现在 dev 组，且**版本约束字符串逐字相等**（如 `tree-sitter>=0.24,<0.26`）；缺失或版本不等时断言消息列出差异包名与两侧约束。
2. `test_dev_group_keeps_pyright_gate_dependencies`
   - 前置：同上；
   - act：解析 dev 组；
   - 断言：`pyright`、`pytest`、`pytest-cov` 三个门禁依赖在 dev 组中存在（防止未来依赖组重构时静默丢掉 pyright 门禁——与 A4 CI 门禁互为守卫）。

模块 docstring 注明：本测试是 dev/ts 双清单漂移的守护（A6）；PEP 735 迁移被缓做的理由（pip ≥25.1 基线），迁移落地时本文件应删除并同步移除本条登记。

### 3.2 A17——tests/README.md

新增 `tests/README.md`（≤60 行），内容：
- 组织约定：测试**按行为域组织**，不按被测模块一一对应（例：`actions.py` + `commands.py` 合并进 `test_action_table.py`；L3 流程模块由 `test_app_textual.py` 等 Textual pilot 测试间接覆盖）；
- 间接覆盖映射表：7 个无同名测试的根模块 → 覆盖它的测试文件（`dist_meta.py` → `test_diagnostics.py`；`document_flows.py` / `window_flows.py` / `overlays.py` / `prompt_flows.py` / `lsp_sync.py` → `test_app_textual.py` / `test_explorer.py` / `test_changelog_view.py` 等，以 grep 实测为准填写）；`extension_flows.py` → `test_extensions.py`；
- 指路：新测试的命名/隔离约定见 `tests/conftest.py` docstring 与 autouse `isolated_home` fixture；架构守卫见 `test_architecture.py` 与 `.trae/rules/architecture-boundaries.md` §六。

## 四、验证方案

- 验证目标：A6 漂移守护生效；A17 约定成文。不触碰任何 `yate/` 文件。
- 命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dependency_groups.py -q
.venv\Scripts\python.exe -m pyright tests/test_dependency_groups.py
```

- 负向演练（执行者必做并记录输出）：临时把 `pyproject.toml` 中 dev 组某条 tree-sitter 版本改成与 ts 组不同（如 `>=0.24`），确认 `test_ts_group_subset_of_dev_group` 失败并列出差异，然后**还原**（不留 diff）。
- 手工验证：README 中间接覆盖映射表逐行抽查——每个被映射的测试文件确实 import 或以 pilot 方式触达对应模块。

## 五、风险与回滚

- 风险：`tomllib` 解析依赖 pyproject 语法合法（无风险，构建本身也依赖它）；负向演练忘还原——验收时 `git diff --exit-code pyproject.toml` 兜底。
- 回滚：删除两个新文件即可，零依赖。
