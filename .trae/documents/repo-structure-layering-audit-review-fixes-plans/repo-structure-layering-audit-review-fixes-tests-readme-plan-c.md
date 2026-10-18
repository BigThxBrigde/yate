# 子计划 c —— `tests/README.md` 修正（Fix-C1）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 来源：审计记录 S-6
- 波次：wave-2｜独占文件：`tests/README.md`（**只改这一个文件**）
- 前置依赖：无

## 一、目标

1. 修掉 2 处失效路径引用（`overlays.py` → `overlay_flows.py`；`yate/services/extensions.py` →
   `yate/services/extensions/`）；
2. 覆盖表口径改为"抽检映射"，并写入本轮实测数字，避免下次审计把"表不全"重复登记为发现。

## 二、逐处改动（逐字替换）

### 改动 1 —— 第 3-9 行（引言段）

现状（含 `overlays.py`）：
```
`test_action_table.py`; the L3 flow modules (`document_flows.py`,
`window_flows.py`, `overlays.py`, `prompt_flows.py`, `lsp_sync.py`,
`extension_flows.py`) are exercised indirectly through the Textual pilot
```
目标：
```
`test_action_table.py`; the L3 flow modules (`document_flows.py`,
`window_flows.py`, `overlay_flows.py`, `prompt_flows.py`, `lsp_sync.py`,
`extension_flows.py`) are exercised indirectly through the Textual pilot
```

### 改动 2 —— 第 11-14 行（覆盖表标题与前言）

现状：
```
## Indirect coverage map

Root modules without a same-named `test_<module>.py`, and the test files that
cover them:
```
目标：
```
## Indirect coverage map (spot checks)

This is a **spot-check map, not an exhaustive registry**: tests are organised
by behaviour domain, so most modules have no same-named test file (2026-10-17
measurement: 92 of the 139 `yate/` modules). Listed below are the root modules
whose indirect coverage is worth documenting explicitly, and the test files
that cover them:
```

### 改动 3 —— 第 22 行（表行）

现状：
```
| `overlays.py`        | `test_action_table.py`, `test_app_textual.py`, `test_changelog_view.py`, `test_vim_keymap.py` |
```
目标：
```
| `overlay_flows.py`   | `test_action_table.py`, `test_app_textual.py`, `test_changelog_view.py`, `test_vim_keymap.py` |
```

### 改动 4 —— 第 26-27 行（脚注）

现状：
```
(`test_extensions.py` covers `yate/services/extensions.py`, the extension
loader — not `extension_flows.py`. `test_architecture.py` references several
```
目标：
```
(`test_extensions.py` covers the extension machinery under
`yate/services/extensions/` -- the facade plus the `loader` submodule, R14 --
not `extension_flows.py`. `test_architecture.py` references several
```

## 三、验收命令

```powershell
git --no-pager diff --stat tests/README.md
Select-String -Path tests\README.md -Pattern 'overlays\.py|services/extensions\.py'   # 期望 0 命中
Select-String -Path tests\README.md -Pattern 'overlay_flows\.py|services/extensions/'  # 期望 ≥2 命中
```

- 判定：0 残留守旧引用；新增表述与 `tests/README.md` 既有风格一致（英文、连字符路径）；
- 纯文档改动，测试门禁并入总纲 §四；
- 输出：改动清单 + 命令输出。

## 四、风险与回滚

- 表格为 Markdown 对齐表：改动后表头分隔行与列数不得变化；
- 回滚：`git revert <本步提交 sha>`。
