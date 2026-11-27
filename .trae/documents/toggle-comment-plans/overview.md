# 切换注释（IKWNOG）子计划总览

唯一规范来源：[`../toggle-comment-plan.md`](../toggle-comment-plan.md)。
本总览仅将其四个波次拆分为文件独占的子计划。

| 波次 | 子计划 | 产出 | 独占文件 |
|---|---|---|---|
| a | [plan-a.md](plan-a.md) | 按键常量 + 可逆的纯函数注释引擎 | `keymaps/keys.py`, `editor_core/commenting.py`, `tests/test_commenting.py`, `tests/test_key_notation.py` |
| b | [plan-b.md](plan-b.md) | 动作、命令、分发拦截、键位映射行、帮助浮层 | `actions.py`, `commands.py`, `editor_dispatch.py`, `keymaps/vsc.py`, `keymaps/vim.py` (binding rows only), `editor_components/modals.py`, `tests/test_toggle_comment.py`, `tests/test_editor_dispatch.py` |
| c | [plan-c.md](plan-c.md) | vim `gc{motion}` / `gcc` / 可视模式 `gc` 状态机与提示 | `keymaps/vim.py` (state machine), `tests/test_vim_keymap.py`, `tests/test_whichkey_flows.py` |
| d | [plan-d.md](plan-d.md) | 架构守卫 #45 + 双语文档 + changelog | `tests/test_architecture.py`, `.trae/rules/architecture-boundaries.md`, `resources/manual.en.md`, `resources/manual.zh.md`, `docs/which-key.en.md`, `docs/which-key.zh.md`, `CHANGELOG.md`, `CHANGELOG.zh.md` |

各波次严格按序执行；每个波次单独提交。评审与最终门禁见主计划 §3。
