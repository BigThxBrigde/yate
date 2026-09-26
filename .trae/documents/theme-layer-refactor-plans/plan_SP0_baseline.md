# Plan SP0 — 环境准备（worktree 基线）

> 状态：⏳ **待实施** · 前置：无 · 后置：[Plan SP1](plan_SP1_decouple.md)
> 工作量：S · 步骤：S0.1 → S0.2
> 目的：worktree 独立 venv 就绪 + 四项门禁**基线数字留档**，供 SP3 收尾对比（证明改动本身零回归）。

---

## S0.1 建 venv 并安装 dev 依赖

| 项 | 内容 |
|---|---|
| 输入 | 干净 worktree（仅未跟踪的 `.trae/documents/theme-layer-refactor-plans/`） |
| 动作 | `python -m venv .venv`；`.venv\Scripts\python.exe -m pip install -e ".[dev]"` |
| 输出 | worktree 根 `.venv\` 就绪 |
| 验收 | `.venv\Scripts\python.exe -c "import yate.config, yate.cli"` 无异常 |

## S0.2 基线门禁留档 ×4

| 项 | 内容 |
|---|---|
| 输入 | S0.1 |
| 动作 | 依次跑：① `pytest tests/test_architecture.py -q`；② `pyright yate/ tests/ tools/`；③ `pytest tests/ -q`；④ `python -m tools.smoke_test run --fail-only`（解释器均用 `.venv\Scripts\python.exe`） |
| 输出 | 四项实测数字写入下方「执行记录」 |
| 验收 | 架构 **13 passed**；pyright **0 errors**；pytest exit 0；冒烟 exit 0。参考值（同码态主工作区 2026-09-26 实测）：pytest 全量 1231 collected / 7 skipped、冒烟 88/88 场景 · 917/917 checks——**以 worktree 实测为准** |

---

## 执行记录（回填区，执行时填写）

> 格式参照 app-layering Plan F §F.6：命令 + 实测数字 + 偏离项。

- S0.1：（日期、安装是否一次通过、特殊依赖备注）
- S0.2 基线：
  - `pytest tests/test_architecture.py -q` → ___ passed
  - `pyright yate/ tests/ tools/` → ___ errors, ___ warnings, ___ informations
  - `pytest tests/ -q` → ___ collected / ___ skipped / exit ___
  - `python -m tools.smoke_test run --fail-only` → ___/___ 场景 · ___/___ checks · exit ___
- 偏离参考值的项及原因：
