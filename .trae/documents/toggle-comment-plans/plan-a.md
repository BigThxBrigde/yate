# 波次 a：按键常量与可逆注释引擎

来源：[`../toggle-comment-plan.md`](../toggle-comment-plan.md) §2.1/§2.3/§3。

## 输入
- 共享常量 `TOGGLE_COMMENT_KEY = "<ctrl-/>"`（原始值 `\x1f`）与
  `TOGGLE_KEYMAP_KEY = "ctrl+shift+/"`（event.key 名称，按此记载）
  位于 `yate/keymaps/keys.py`；仅在需要时添加便于帮助展示的别名条目，
  不要对 shift 拼写调用 `parse_key`（它会归约为 `\x1f`）。
- `yate/editor_core/commenting.py`（新增 L0 模块，仅依赖 stdlib + 以普通标记形式传入的
  `LangSpec` dataclass 结构）：暴露
  `comment_range(lines: Sequence[str], first: int, last: int, *, line_comment:
  str | None, block_comment: tuple[str, str] | None) -> list[str]`。检测规则见主计划
  §2.3。空行保持不变；混合行先收敛为已注释再精确还原；仅块注释语言逐行包裹/解包；
  无标记 -> 原样返回输入行。

## 独占文件
`yate/keymaps/keys.py`, `yate/editor_core/commenting.py`,
`tests/test_commenting.py`, `tests/test_key_notation.py`.

## 产出
可从 `yate.keymaps.keys` 导入的常量；带 docstring 的纯函数助手；
针对 python `#`、c `//`、html `<!-- -->`、css `/* */`、lua
`--`、空行、混合行、无标记的往返测试。

## 验收命令
```
.venv\Scripts\python.exe -m pytest tests/test_commenting.py tests/test_key_notation.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/keymaps/keys.py yate/editor_core/commenting.py
```
