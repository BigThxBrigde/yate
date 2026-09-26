# Plan SP3 — 收尾门禁、校准回填与提交

> 状态：⏳ **待实施** · 前置：[Plan SP1](plan_SP1_decouple.md) ✅ + [Plan SP2](plan_SP2_guard_docs.md) ✅ · 后置：无
> 工作量：S · 步骤：S3.1 → S3.2 → S3.3
> 门槛：pyright 全仓 0 诊断 · pytest 全量两轮全绿（防时序偶发，本项目惯例）· 冒烟全绿。

---

## 1. 步骤表

| 步 | 动作 | 输入 | 输出 | 验收 |
|---|---|---|---|---|
| S3.1 | 全量门禁（命令见 §2）：pyright 全仓 + pytest 全量**两轮** + 冒烟 `--fail-only` | 全部代码与文档步骤 | 实测数字 | 三门禁全绿；数字与 SP0 基线一致（新增 2 用例 → collected +2） |
| S3.2 | 校准记录回填：本 Plan「执行记录」+ [README §9](README.md#9-校准记录回填区)（SP0 基线 / S1.5 审计结论 / S2.2 负向验证证据 / S3.1 门禁数字 / 偏离项与理由）；[README §8](README.md#8-交付前自检清单) 逐项勾选 | S3.1 | 回填完整 | 与自检清单逐项对应；各 Plan 执行记录无空白占位 |
| S3.3 | 两笔提交（各自可 revert）：① `refactor(config): decouple yaterc loader from editor_view.theme`（config.py + cli.py + tests 修补与新增用例）；② `docs(arch): enforce UI-free config layer and record N30 decision`（test_architecture.py + 4 处文档 + 本目录全部计划文档） | S3.1–S3.2 | 干净工作区 | `git status` 干净；提交信息符合 git-commit-message 规范（英文、conversation 模板）；不推送由用户定 |

## 2. 门禁命令（Windows PowerShell，worktree 根目录执行）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q     # 第一轮
.venv\Scripts\python.exe -m pytest tests/ -q     # 第二轮（防时序偶发）
.venv\Scripts\python.exe -m tools.smoke_test run --fail-only
```

## 3. 风险提示（收尾阶段特有）

| 风险 | 对策 |
|---|---|
| 两轮 pytest 出现时序偶发（pilot/防抖类用例） | 先单独复跑确认，再下结论；不许直接改断言（子代理纪律 §三.3 同款） |
| 提交拆分把守卫/文档与解耦代码混在一起 | 按 S3.3 文件域严格分笔：tests/test_architecture.py 与 `.trae/**` 只进第②笔 |

---

## 执行记录（回填区，执行时填写）

- S3.1 门禁（两轮各自记录）：
  - `pyright yate/ tests/ tools/` → ___ errors, ___ warnings, ___ informations
  - `pytest tests/ -q` 第一轮 → ___ collected / ___ skipped / exit ___；第二轮 → exit ___
  - `python -m tools.smoke_test run --fail-only` → ___/___ 场景 · ___/___ checks · exit ___
  - 与 SP0 基线差异说明（预期仅 collected +2）：
- S3.2 回填确认：README §8 自检清单 ___/5 勾选；各 Plan 执行记录完整
- S3.3 提交：① sha ___（___ 文件，+___/−___）；② sha ___（___ 文件，+___/−___）
- 偏离计划项及理由：
