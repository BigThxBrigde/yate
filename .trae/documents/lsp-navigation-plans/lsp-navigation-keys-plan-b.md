# 计划 b — 共享按键与动作注册（波次 1）

父计划：[../lsp-navigation-plan.md](../lsp-navigation-plan.md)。

## 输入 / 输出

输入：issue 简报 AC1-AC3、AC8；父计划 §2 中的 keymap 事实。
输出：五个新的共享按键常量、vim 的 `gd`/`gr` 和弦键与 `K`、vsc 的 alt 键与 `K`、
已注册的动作名。此处不实现流程（波次 d）。

## 独占文件

- `yate/keymaps/keys.py`
- `yate/keymaps/vim.py`
- `yate/keymaps/vsc.py`
- `yate/actions.py`
- `tests/test_lsp_navigation_keys.py`（新增）

## 具体改动

### 1. `keymaps/keys.py`

在 `HOVER_DOC_KEY`（`:57-60`）旁添加，每个都带一条 `#:` 注释：

```python
GOTO_DEF_KEY: str = "gd"             # vim chord
FIND_REFS_KEY: str = "gr"            # vim chord
GOTO_DEF_VSC_KEY: str = "<alt-g>"    # vsc single key
FIND_REFS_VSC_KEY: str = "<alt-r>"   # vsc single key
HOVER_POPUP_KEY: str = "<shift-k>"   # both keymaps, normalizes to "K"
```

添加前检查 `conflicts.py` 的保留键：`<alt-g>` / `<alt-r>` /
`<shift-k>` 在当前表中空闲；不要使用 `<f12>`（宏回放）。

### 2. `keymaps/vim.py`

- 在现有的导入块中从 `yate.keymaps.keys` 导入这五个常量。
- 在 `build_bindings` 中增加引用这些常量（绝不写字面量）的帮助条目：
  `KeyBinding(parse_key(GOTO_DEF_KEY), "goto_definition", ...)`,
  `FIND_REFS_KEY` 同理，以及用本文件的辅助函数写的
  `_k(HOVER_POPUP_KEY, "show_hover_docs", ...)`。
  更新前缀 `g` 的 `chord_hints()`，使其提及 `d definition / r references`。
- 在 `_handle_normal` 中，于 `:896` 处通用的未知后续键分支之前插入：
  - `self.prefix == "g" and key == "d"` → 清除 prefix/count，
    `ctx.ui.execute_action("goto_definition")`，返回 `True`。
  - `self.prefix == "g" and key == "r"` → 同上，但为 `find_references`。
  不要消费其他 `g` 后续键；保持 `gg`/`gj`/`gk`/`gc` 行为不变。
  `K` 会到达 `:1095-1097` 的扩展绑定回退，因此新的帮助绑定会让 `<shift-k>`
  分发到 `show_hover_docs`。

### 3. `keymaps/vsc.py`

导入这三个单键常量，并在现有 hover 条目（`:142`）附近添加到 `build_bindings`：

```python
_k(GOTO_DEF_VSC_KEY, "goto_definition", "Go to definition", "NAV"),
_k(FIND_REFS_VSC_KEY, "find_references", "Find references", "NAV"),
_k(HOVER_POPUP_KEY, "show_hover_docs", "Show hover documentation", VIEW),
```

绝不要在 `build_bindings` 中写出 `<alt-g>` / `<alt-r>` / `<shift-k>` 的字面量。

### 4. `actions.py`

在 `show_hover_docs`（`:267-268`）附近注册，全部为调用将来流程对象的 lambda
（波次 d 提供这些方法）：

```python
reg("goto_definition", lambda ctx: editor.lsp_navigation.goto_definition(), ...)
reg("find_references", lambda ctx: editor.lsp_navigation.find_references(), ...)
reg("show_outline", lambda ctx: editor.lsp_navigation.show_outline(), ...)
reg("rename_symbol", lambda ctx: editor.lsp_navigation.rename_symbol(), ...)
reg("show_code_actions", lambda ctx: editor.lsp_navigation.show_code_actions(), ...)
reg("show_signature_help", lambda ctx: editor.lsp_navigation.show_signature_help(), ...)
```

保持 `show_hover_docs` 不变（`K` 复用它）。不改 `commands.py`。

## 测试（`tests/test_lsp_navigation_keys.py`）

- `test_lsp_navigation_keys_are_distinct_and_defined_once`：五个常量互不相同；`parse_key(HOVER_POPUP_KEY) == "K"`。
- `test_vsc_lsp_shortcuts_resolve_to_actions`：`VscKeymap().lookup(parse_key(GOTO_DEF_VSC_KEY)).action == "goto_definition"`，引用键和 `HOVER_POPUP_KEY -> show_hover_docs` 同理。
- `test_vim_k_resolves_to_hover_action`：`VimKeymap().lookup(parse_key(HOVER_POPUP_KEY)).action == "show_hover_docs"`。
- `test_vim_g_chords_call_navigation_actions`：用一个最小的 `ActionContext`，其 `ui.execute_action` 记录名称，先喂入 `g` 再喂入 `d`，断言 `["goto_definition"]`；重置后喂入 `g` 再喂入 `r`，断言 `["find_references"]`；断言两次之后 `prefix` 都被清除。复用现有 vim keymap 测试中的 context/UI 桩模式（在 `tests/` 中找；不要修改那些文件）。
- `test_vim_gd_does_not_break_existing_g_chords`：`gg`、`gj`、`gc` 仍走各自原有路径（用同一个桩断言没有记录任何导航动作，且原有的状态转换仍会发生）。
- `test_builtin_actions_include_lsp_navigation_names`：用 `populate(reg, editor_stub)` 填充一个 `ActionRegistry`，断言六个新名称都能解析；一个暴露了 `lsp_navigation` 的桩 editor 即可。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation_keys.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps yate/actions.py tests/test_lsp_navigation_keys.py
```

要求以 0 退出。注意：`keymaps/vim.py` 属于大小豁免文件；本计划之后由计划 e 更新
记录的行数（此处不改计数）。

## 风险 / 回滚

风险：vim 的 `K` 可能在扩展回退之前被 `_SHIFT_KEYS` 拦截；上述测试必须验证实际分发。
若确实如此，在 `_SHIFT_KEYS` 处理之前增加一个显式的 `K` 分支，并记录该偏离。
风险：`alt-g`/`alt-r` 可能与终端序列冲突；通过 `conflicts.find_key_conflicts`
在本地测试文件中运行与 `python -m tools.check_keys` 等价的测试。
回滚：回退本计划的提交；在动作名敲定之前波次 d 无法开始。

## 执行偏离记录（2026-11-22）

实测：`yate/actions.py` 中六个新动作使 pyright 报告 24 个
`reportAttributeAccessIssue` 错误，因为 `Editor.lsp_navigation` 直到波次 d
（`flow-plan-d.md` §3）才存在。keymap 改动和全部六个测试均通过；唯一失败的
验收命令是针对 `actions.py` 的 pyright。依据无人值守模式的授权，该偏离获批：
计划 b 在 pytest 全绿的情况下提交，其 pyright 验收推迟到波次 d 添加 `Editor`
属性之后，届时主代理将重新运行
`.venv\Scripts\python.exe -m pyright yate/actions.py`。
没有为绕过该问题而引入任何 `Protocol` / `Any` / ignore 注释。
