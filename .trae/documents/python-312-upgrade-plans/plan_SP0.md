# plan SP0 — 勘察与基线（主代理，串行前置）

> 从属于[总纲](README.md)。**只读勘察波：不改任何产品文件，无提交。**
> 产出三件事：基线数字留存、SyntaxWarning 守卫零告警证明、@override 精确落点清单与计数（供 D1 拍板）。

## 1. 输入

总纲 §一 F1–F11 现状。

## 2. 步骤与命令（Windows PowerShell，解释器统一 `.venv\Scripts\python.exe`）

1. **基线数字留存**（对照门禁用）：
   - `.venv\Scripts\python.exe -m pytest tests/ -q` → 记录用例总数
   - `.venv\Scripts\python.exe -m pyright yate tests tools` → 记录诊断数（应为 0）
   - `.venv\Scripts\python.exe -m tools.smoke_test run --fail-only` → 记录 exit 0 与 checks 数
2. **SyntaxWarning 守卫试跑**（当前 venv 3.13.2 上先证零告警；该告警在 3.12 升级语境下必须为零）：
   - `.venv\Scripts\python.exe -W error::SyntaxWarning -m compileall -q yate tools tests`
   - `.venv\Scripts\python.exe -m pytest tests/ -q -W error::SyntaxWarning`
3. **reportImplicitOverride 试开盘点**：
   - 临时在 [pyproject.toml](../../../pyproject.toml) `[tool.pyright]` 加 `reportImplicitOverride = "error"`；
   - `.venv\Scripts\python.exe -m pyright yate tests tools` 收集全部诊断（文件:行:符号）并计数；
   - **还原 pyproject**（该改动不进入任何提交）。
4. **D1 拍板**：计数 ≤150 → 分支 A（全量装饰 + 规则固化）；>150 → 分支 B（仅装饰核心链）。
   拍板结果与依据记入总纲 §五校准记录。

## 3. 输出与验收

- **输出**：@override 精确落点清单（文件:行:方法）+ 计数 + 基线数字 → 回填总纲校准记录。
- **验收**：清单与计数经主代理复核（以命令实跑输出为准，不采信记忆值或转述值）。
