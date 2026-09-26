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

## 执行记录（2026-09-26 回填）

- S0.1：2026-09-26，`python -m venv .venv` + `pip install -e ".[dev]"` 一次通过（EXIT=0，
  仅 pip 升级提示）；`import yate.config, yate.cli` ok。
- S0.2 基线：
  - `pytest tests/test_architecture.py -q` → **13 passed**（3.14s）
  - `pyright yate/ tests/ tools/` → **0 errors, 0 warnings, 0 informations**
  - `pytest tests/ -q` → **1216 passed / 7 skipped / exit 0**（201.65s；与主工作区参考
    1231 collected 差 8 = release-tool 分支新用例不在 master 基点，预期内）
  - `python -m tools.smoke_test run --fail-only` → **88/88 场景 · 917/917 checks · exit 0**（93.20s）
- 偏离参考值的项及原因：
  1. **dev extras 需含 `ts`**：首装 `.[dev]` 后 pyright 报 6 errors（tests/test_ts_backend.py
     与 languages.py 的 `tree_sitter` import 不可解析）——可选依赖组 `ts` 是 pyright/测试
     基线的**事实必需**；补装 `.[dev,ts]` 后归零。后续 Plan 引用本记录时直接用 `.[dev,ts]`。
  2. pytest 汇总行被吞的问题：pyproject `addopts = "-q"` 与命令行 `-q` 叠加成双 quiet；
     门禁命令统一改用 `-o addopts= -q`（或接受退出码 + 末两行进度判定）。
