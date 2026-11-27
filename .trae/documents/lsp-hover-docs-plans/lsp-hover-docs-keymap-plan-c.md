# 计划 c — 两个 keymap 中共用一个 hover 按键（wave-1，L1）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，决策 D1

## 输入

- `yate/keymaps/keys.py:18-55`（记法 / `SPECIAL_KEYS`）、`:93-152`（`parse_key` 将 shift 折叠进 ctrl 编码）。
- `yate/keymaps/base.py:21-26`（记法名称的再导出）、`:120-153`（以原始按键为键的绑定索引）。
- `yate/keymaps/vsc.py:36-122`、`yate/keymaps/vim.py:145-233`、`yate/keymaps/vim.py:80`、`:238-266`（`_FUNCTION_KEYS` 快速路径）。
- `yate/keyproto/key_codec.py:20`（`_NAMED_KEYS` 由 `SPECIAL_KEYS` 构建）。
- `yate/services/extensions/api.py:295-305`（`keymap="both"` → 两个目标）。
- `tests/test_keymaps_conflicts.py`、`tests/conftest.py:366-377`（`make_action_context`）。

## 待实现的决策（必须遵守）

issue 中的 `<ctrl-k>` 被否决：`parse_key("<ctrl-k>") == parse_key("<ctrl-shift-k>") == "\x0b"`；vsc 将 `\x0b` 绑定到 `delete_line`（`vsc.py:47`），且 `tools/smoke_test/scenarios/edit.py:48-52` 对此作了断言。AC2 禁止这种冲突。唯一默认值是 **`<f7>`**（`\x1b[18~`），两张表都未占用，存在于 `SPECIAL_KEYS` 与 `key_codec._NAMED_KEYS` 中，且由 vim 的 `_FUNCTION_KEYS` 分支在任何模式处理之前分发——因此所有 vim 模式与 vsc 都使用完全相同的按键。两张表与所有文档都必须引用同一个值。

## 独占文件

- `yate/keymaps/keys.py`
- `yate/keymaps/base.py`
- `yate/keymaps/vsc.py`
- `yate/keymaps/vim.py`
- `tests/test_hover_key_binding.py`（新增）

`yate/actions.py` **不在**本计划内（归 wave-4 的 plan h 所有，由其注册 `show_hover_docs` 动作）。在此之前，该绑定解析到一个未注册的动作，这无害：`Keymap.dispatch` 报告一个失效动作，`Editor.execute_action` 返回 `False`；没有测试断言每张表的动作都已预先注册（由下方的验收命令验证）。

## 具体变更

1. `yate/keymaps/keys.py:55`——紧接 `SPECIAL_KEYS` 之后添加：

   ```python
   #: Shared default for the "show API documentation" action. Both built-in
   #: keymaps import this single L0 constant (AC2); <ctrl-k> is NOT usable
   #: because it aliases <ctrl-shift-k> (delete_line) at raw byte \x0b.
   HOVER_DOC_KEY: str = "<f7>"
   ```

2. `yate/keymaps/base.py:21-26`——在 `from yate.keymaps.keys import (...)` 再导出块中加入 `HOVER_DOC_KEY as HOVER_DOC_KEY`（与 `KEY_ALIASES` 相同的 `X as X` 风格）。如果模块定义了 `__all__`，也在其中加入该名称。
3. `yate/keymaps/vsc.py:102-121`（VIEW 区）——添加 `_k(HOVER_DOC_KEY, "show_hover_docs", "Show API documentation at cursor", VIEW)`；从 `yate.keymaps.base` 导入 `HOVER_DOC_KEY`（保持按字母顺序的导入次序）。
4. `yate/keymaps/vim.py:212-233`（HLP 区）——添加 `KeyBinding(parse_key(HOVER_DOC_KEY), "show_hover_docs", "Show API documentation at cursor", HLP)`；在现有分组导入（`:33-39`）中从 `yate.keymaps.base` 导入该常量。
5. 不要触碰 `RESERVED_KEYS`、`_MOTION_CODES`、`_FUNCTION_KEYS` 或 `toggle_keymap`。不新增 `Protocol`，不用相对导入，只用 ASCII 注释。

## 测试（`tests/test_hover_key_binding.py`）

| 测试 | Arrange / Act | 断言 |
| --- | --- | --- |
| `test_hover_key_constant_is_f7_and_maps_to_f7_raw` | `parse_key(HOVER_DOC_KEY)` | `HOVER_DOC_KEY == "<f7>"` 且 raw `== "\x1b[18~"`（`SPECIAL_KEYS["f7"]`）|
| `test_vsc_and_vim_bind_the_same_raw_key_to_hover_action` | `VscKeymap().lookup(raw)`、`VimKeymap().lookup(raw)` | 两者都 `is not None`，两者 `.action == "show_hover_docs"`，且两者的 raw 键相同 |
| `test_hover_key_is_not_a_conflict_in_either_keymap` | `find_key_conflicts(VscKeymap())`、`find_key_conflicts(VimKeymap(), reserved=RESERVED_KEYS)` | 不存在 `.raw == raw` 的冲突；`VscKeymap().lookup("\x0b").action == "delete_line"` 仍成立 |
| `test_hover_key_is_not_a_vim_motion_or_reserved_key` | 检查 `RESERVED_KEYS`、`_MOTION_CODES` | 对两者都有 `raw not in`；`HOVER_DOC_KEY not in ("<f1>","<f2>","<f8>","<f9>","<ctrl-shift-k>")` |
| `test_both_tables_reference_the_shared_constant` | 对 `vsc.py` 与 `vim.py` 源码做 `ast.parse` | 每个文件在 `build_bindings` 内恰有一个 `Name(id="HOVER_DOC_KEY")`；两张表中都没有字面量 `"<f7>"`（漂移守卫）|
| `test_vim_dispatches_hover_key_in_normal_insert_and_visual_modes` | 对每个 `VimMode`，构造 `make_action_context`，用一个记录器 monkeypatch `ctx.ui.execute_action`，调用 `VimKeymap().handle_key(ctx, raw)` | `handle_key` 返回 `True`，且记录器在**全部三种**模式下都收到 `["show_hover_docs"]` |
| `test_toggle_keymap_preserves_hover_binding` | 用 vsc+vim 构造 `KeymapSet()`，在 `toggle()` 前后（两次）做 `lookup(raw)` | 两个激活的 keymap 都用同一个 raw 暴露 `show_hover_docs` |
| `test_key_name_round_trip_displays_the_hover_key` | `key_name(raw)` | 包含 `"f7"`（help/which-key 显示）|

plan h 另外覆盖该动作上的 `bind_key(..., keymap="both")`，并在 `tests/test_architecture.py` 中新增一项 AST 守卫。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_key_binding.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_keymaps_conflicts.py tests/test_key_notation.py tests/test_keyproto.py tests/test_action_table.py tests/test_keymap_set.py -q -n 1
```

两条命令退出码均为 0。第二条是回归守卫，证明在新动作尚未注册时，既有绑定/动作表行为未改变。

## 风险与回滚

- 风险：运行时检查发现某个表动作必须注册。此时**停下上报**；由主代理决定是否将动作注册提前（这需要 `Editor.hover_flows` 属性，属于 wave-4 的交付物）。
- 风险：终端不送达 `<f7>`。`key_codec._NAMED_KEYS` 映射了它；plan i 在冒烟中按 `f7`。若证实存在真实冲突，只改动 `HOVER_DOC_KEY` 并重跑 plan f 的文档一致性测试。
- 回滚：回退该提交；没有其他 wave-1 计划依赖这两张表。
