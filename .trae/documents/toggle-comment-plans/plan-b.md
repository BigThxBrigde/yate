# 波次 b：动作、命令、分发、键位映射与帮助浮层

来源：[`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.4/§3。

## 输入
波次 a 的产出，加上以下已核实事实：
- vsc 绑定位于 `yate/keymaps/vsc.py:121`；vim 绑定位于
  `yate/keymaps/vim.py:247`，特例位于 `:275-281`。
- 动作表 `yate/actions.py`（填充，编辑区）；
  命令表 `yate/commands.py`（键位映射/帮助区，`:vim`/`:vsc`）。
- 分发全局项位于 `yate/editor_dispatch.py:128-160`；原始值转换位于
  `:167-174`；已核实 `event_to_raw("ctrl+shift+/") is None`。
- `help overlay` 位于 `yate/editor_components/modals.py:91-93` 及 GLOBAL KEYS。

## 改动
1. `actions.py`：注册 `toggle_comment`，解析 `LangSpec`，经由
   `lang_for(ctx.doc.filetype)`（L3 -> L0 合法），通过 `selected_rows()` 或当前行获取行范围，
   委托给 `comment_range`，应用一次 `TextBuffer.replace_range`，
   恢复光标并钳制；无标记 -> 给出消息。
2. `commands.py`：`toggle-comment` 命令转发到
   `editor.execute_action("toggle_comment")`。
3. `editor_dispatch.py`：在 `event_to_raw` 之前拦截
   `event.key in {"ctrl+shift+/"}`（常量 + `ctrl+shift+slash` 别名），
   调用 `ed.execute_action("toggle_keymap")`，返回 True。放在提示栏所有权检查之后。
4. `vsc.py` / `vim.py`：将 `\x1f` 绑定替换为
   `_k(TOGGLE_COMMENT_KEY, "toggle_comment", "Toggle comment", ...)`；
   在两张表中添加 `TOGGLE_KEYMAP_KEY` 的仅帮助行；删除 vim 的
   `\x1f` 键位映射切换特例。
5. `modals.py`：标题 + GLOBAL KEYS 文本改为 `ctrl+shift+/`。

## 独占文件
`yate/actions.py`, `yate/commands.py`, `yate/editor_dispatch.py`,
`yate/keymaps/vsc.py`, `yate/keymaps/vim.py`（仅绑定行与特例移除）、
`yate/editor_components/modals.py`、`tests/test_toggle_comment.py`、
`tests/test_editor_dispatch.py`。

## 验收命令
```
.venv\Scripts\python.exe -m pytest tests/test_toggle_comment.py tests/test_editor_dispatch.py tests/test_vsc_keymap.py tests/test_keymaps_conflicts.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/actions.py yate/commands.py yate/editor_dispatch.py yate/keymaps/ yate/editor_components/modals.py
```
