# 波次 c：vim `gc{motion}` / `gcc` / 可视模式 `gc`

来源：[`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.2/§3。

## 输入
波次 b 的产出；`yate/keymaps/vim.py` 状态机细节：
- `g` 前缀分支位于 `_handle_normal`（`:873-878`），后续分支包括
  `gg`（`:831-833`）、`gj`/`gk`（`:834-844`）、可视模式对应分支
  （`:575-589`）、提示（`:403-404`）、操作符待定（`:1071-1097`）。
- `ctx.ui.execute_action("toggle_comment")` 是唯一的动作入口。

## 改动
- NORMAL：`g` 分支 -> `c` 后续项解析出一个注释操作：
  - `gcc`（支持可选计数）应用于当前行；
  - `gc{motion}` 复用现有的 motion 解析推导行跨度
    （至少支持 `j`、`k`、`w` 与计数）并应用同一动作；
  - 任何其他 `g` 后续项行为完全不变。
- VISUAL / VISUAL-LINE：`gc` 应用于所选行并返回 NORMAL。
- which-key 的 `g` 前缀提示新增 `c` 行；其他提示不变。
- 解析时清除寄存器/前缀/计数状态，避免任何残留。

## 独占文件
`yate/keymaps/vim.py`（仅状态机）、`tests/test_vim_keymap.py`、
`tests/test_toggle_comment.py`（vim 部分）、`tests/test_whichkey_flows.py`。

## 验收命令
```
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_toggle_comment.py tests/test_whichkey_flows.py tests/test_soft_wrap_keys.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py
```
