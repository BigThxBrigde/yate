# plan SP4 — `typing.override` 落地 + 规则固化（3.12 核心收益）

> 从属于[总纲](README.md)；前置：SP3 + D1 拍板（SP0 产出的精确落点清单）。
> pyupgrade 等语法重写工具**做不了**继承链语义判断（总纲工具化策略评估第 3 条），本波由主代理
> 以 pyright `reportImplicitOverride` 诊断清单为工单逐文件处理。

## 1. 输入

SP0 的精确落点清单（文件:行:方法；预计 ≈55+，17 个 yate 文件为核心，tests/tools 另计）。

## 2. 步骤（按 D1 分支执行）

- **分支 A（≤150 处，默认）**：逐文件给覆写方法加 `from typing import override` + `@override`；
  然后把 `reportImplicitOverride = "error"` 永久写进 [pyproject.toml](../../../pyproject.toml)
  `[tool.pyright]`，防回归。
- **分支 B（>150 处）**：只装饰 L2 组件链（editor_view/*、app.py）+ editor_term/editor_lsp；
  `reportImplicitOverride` 保持关闭并登记为后续项；本分支验收降为「pyright 0 + 抽查 10 处正确性」。

## 3. 装饰判定边界（工单执行规则）

- **加**：真正覆写基类的方法——Textual 的 `on_*` / `compose` / `render` / `watch_*` / `key_*`、
  dunder 覆写；
- **不加**：`action_*` 命名分派方法（非基类覆写）；
- 导入：每文件 `from typing import override`，按规则 §1.3 导入分组与字母序放置。

## 4. 边界

纯装饰，零运行时行为变更（`typing.override` 是纯标注装饰器）；不改方法体、不动签名。

## 5. 验证命令（门禁）

```powershell
.venv\Scripts\python.exe -m pyright yate tests tools         # 0（分支 A 含新规则生效后的 0）
.venv\Scripts\python.exe -m pytest tests/ -q                 # 连续两次全量全绿
.venv\Scripts\python.exe -m tools.smoke_test run --fail-only # exit 0
git diff                                                     # 复核：无任何非装饰行改动
```

## 6. 提交

- 单提交：`refactor(types): annotate overrides with typing.override`
- 分支 A 信息体补一句：enable `reportImplicitOverride = "error"` in pyright config to prevent regressions.
