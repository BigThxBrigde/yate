# plan SP2 — 规则 3.12 化与工具引入（纯文档波）

> 从属于[总纲](README.md)；前置：SP1。
> **规则修订已于 2026-09-25 先行落盘（commit 4fe388c）**，本波剩余动作 = 复核 + 工具就位。

## 1. 已落盘修订复核清单（[python-coding-style.md](../../rules/python-coding-style.md)）

对照 `git show 4fe388c -- .trae/rules/python-coding-style.md` 逐条勾验：

- §适用范围 `3.10+` → `3.12+`；§1.3 导入示例、§2.3 docstring 示例去 `Optional` 化；
- **§3.2 翻转**：可空标注 `X | None`（PEP 604）、联合 `X | Y`（含运行时别名）、
  新增 `typing.Self` 指引；前向引用示例 `"YateConfig" | None` 同步；
- **§3.5 重写**：PEP 695 泛型 / `type` 别名语句为新代码首选；§1.2 类型变量行同步；
- §五快速清单新增「`X | None` / `X | Y` / `@override`」条目。

发现缺漏就地补齐（补齐部分单独 `docs(rules)` 提交）。

## 2. 工具引入（一次性 codemod，不进 dev extras）

- `pip install pyupgrade`（装进 `.venv`；SP3 完成后可卸载，不留依赖）；
- SP3 固定命令：`.venv\Scripts\pyupgrade.exe --py312-plus --keep-percent-format <files...>`
  （`--keep-percent-format` 防 `%` 格式被改写为 f-string、违反 §4.6 日志惰性求值——理由见总纲工具化策略评估）。

## 3. 架构规则联动核查

- `architecture-boundaries.md`：无 Optional/版本号关联表述（§七仅交叉引用 TYPE_CHECKING 条款）→ **不动**；
- `tests/test_architecture.py`：不涉及类型风格 → **不动**。

## 4. 验证命令（门禁，纯文档波降级）

```powershell
.venv\Scripts\python.exe -m pyright yate tests tools   # 0（未动代码）
.venv\Scripts\python.exe -m pytest tests/ -q           # 全绿一次（双跑无增量信息）
```

外加人工复核：规则文档内部无自相矛盾（示例与条款一致）。

## 5. 提交

- 若复核发现补齐项：`docs(rules): <补齐内容>` 单独提交；
- 否则本波**零提交**（4fe388c 已覆盖全部条款级修订）。
