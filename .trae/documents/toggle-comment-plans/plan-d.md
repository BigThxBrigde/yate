# 波次 d：架构守卫与文档

来源：[`../toggle-comment-plan.md`](../toggle-comment-plan.md) §3。

## 改动
1. `tests/test_architecture.py`：新增守卫 #45
   `test_toggle_comment_keys_are_shared_and_identical`，仿照 hover/soft-wrap
   守卫：AST 断言 `keymaps/vsc.py` 与 `keymaps/vim.py` 都引用 `TOGGLE_COMMENT_KEY`
   于 `build_bindings` 内，且从不字面写出 `"\x1f"` / `"<ctrl-/>"`；
   `keys.py` 声明这两个常量；运行时断言两套键位映射都将原始按键解析为
   `toggle_comment`。反向演练：临时改动一侧，确认失败，再恢复。
2. `.trae/rules/architecture-boundaries.md`：守卫计数 44 -> 45，补充表格行与
   措辞；仅使用相对路径链接。
3. 双语手册（`yate/resources/manual.en.md` / `.zh.md`）：按键表、
   键位映射切换章节、vim 操作符表、终端兼容性说明
   （旧终端不支持 `Ctrl+Shift+/`；改用 `:set keymap=`）、
   关于 `Ctrl+/` 的显著破坏性变更说明。
4. `yate/docs/which-key.en.md` / `.zh.md`：`g` 前缀提示新增 `gc`。
5. `CHANGELOG.md` / `CHANGELOG.zh.md`：Unreleased 特性条目 + 破坏性变更说明；
   如检查器要求，用 `python -m tools.changelog` 生成。

## 独占文件
`tests/test_architecture.py`, `.trae/rules/architecture-boundaries.md`,
`yate/resources/manual.en.md`, `yate/resources/manual.zh.md`,
`yate/docs/which-key.en.md`, `yate/docs/which-key.zh.md`,
`CHANGELOG.md`, `CHANGELOG.zh.md`.

## 验收命令
```
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -n 1
.venv\Scripts\python.exe -m tools.changelog check
```
