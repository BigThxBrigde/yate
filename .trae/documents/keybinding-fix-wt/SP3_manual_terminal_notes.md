# SP3 — manual 终端兼容性标注（D1=A）

> 前置：SP1、SP2 已提交
> 预估：30min　|　独占文件：`yate/resources/manual.en.md`、`yate/resources/manual.zh.md`、`README.md`/`README.zh.md`（如列出该键）

## 目标

把「哪些键受终端能力限制」写成用户可见文档：`ctrl+1`（及同族 kitty CSI-u 编码键）仅 kitty/CSI-u 终端可用；
Windows Terminal / conhost 因修饰键丢失不可达。`ctrl+/` 与 `ctrl+p` 全平台可用（SP1/重构已修）。

## 实施步骤

### 步骤 3.1　定位键位表

在 `yate/resources/manual.en.md` / `manual.zh.md` 中定位 vsc 键位表（绑定来自 `vsc.py:100-110`）：
`ctrl+1`（focus editor）、`ctrl+shift+e`（focus explorer）、`ctrl+p`（quick open）、`ctrl+/`（toggle keymap）。

### 步骤 3.2　加注（双语同构）

键位表下方追加一段「终端兼容性」说明（英文版示例，中文版对译）：

> Keys encoded via the kitty keyboard protocol (CSI-u), such as `ctrl+1`, are only
> delivered by terminals that support it (kitty, WezTerm, WT ≥ 1.25 preview with the
> protocol active). Windows Terminal and classic conhost drop the ctrl modifier on
> digits, so `ctrl+1` does not reach yate there; use the command palette (`alt+shift+p`)
> or `:focus editor` instead. `ctrl+/`, `ctrl+p` and `ctrl+q`/`ctrl+w` work on all terminals.

要点：
- 给出**替代路径**（`alt+shift+p` 命令面板 / `:` 命令），不只是"不支持"；
- 提及 `win_keybinding_plan.md` 的根治路线可放在 `.trae` 文档而非用户手册（手册面向用户，不引用内部计划）。

### 步骤 3.3　README 键位速览

检查 `README.md` / `README.zh.md` 是否列出 `ctrl+1`；如列出，同样加一行 `(CSI-u terminals)` 类标注；未列出则跳过。

### 步骤 3.4　help 面板核对（只读验证，无代码改动）

`ctrl+/` 经 SP1 后 help 面板显示 `<ctrl-/>`；`ctrl+1` 显示 `parse_key` 产物（kitty CSI-u 串，
`key_name` 走默认分支显示 `<\x1b[49;5u>`——**已知限制**：不在本 SP 处理，登记到"遗留项"，
由方案 B P1 的 canonical 名层（`aliases.CANONICAL_NAMES` 渲染）根治）。

## 测试

文档改动无单测；执行既有 changelog/文档相关冒烟（如 `tools/smoke_test` 中涉及 manual 的场景）：

```powershell
d:\Programming\yate\.venv\Scripts\python.exe -m pytest tests\ -q
```

（全量跑一次确认文档改动未触碰代码路径。）

## 验收标准

- [ ] 双语 manual 均含终端兼容性说明且译文同构；
- [ ] 提供了 `ctrl+1` 的替代操作路径；
- [ ] `pytest tests/ -q` 全绿。

## 回滚

单 commit revert（纯文档）。
