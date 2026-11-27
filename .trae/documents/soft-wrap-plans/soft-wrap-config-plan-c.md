# 软换行 - 计划 C：配置、:set 与切换动作（L0/L3）

> 唯一规范来源：`overview.md` + issue IKVRXT。独立于计划 A/B
> （配置数据 + 动作接线；计划 B 中视图通过注入读取它）。
> 审批：无人值守（自动批准）。

## 1. 目标 / 非目标

- 目标：新增 `wrap` 布尔选项（yaterc + `:set wrap=on|off`），默认
  `off`（不换行），另加一个 `toggle_soft_wrap` 动作在运行时翻转它。
- 非目标：不做按键绑定（计划 D），不做显示行移动（计划 D），
  不做视图渲染。现有 yaterc 文件无需迁移（新键为可选）。

## 2. 事实（已核实，文件:行号）

- `config.py:34-39` 的 `KNOWN_OPTIONS`（yaterc 可识别变量）—— 加入 `"wrap"`。
- `config.py:219-230` 的 `_TRUTHY/_FALSY` + `parse_bool()` 接受
  `on|off|true|false|1|0|yes|no`。
- `config.py:290-292` 的 `_parse_bool_option()` 包装 `parse_bool`。
- `config.py:176` 的 `YateConfig.which_key: bool = True` —— 数据字段先例；
  在其附近加入 `wrap: bool = False`。
- `config.py:299-370` 的 `SET_OPTION_SPECS`（`:set` 的唯一规范来源）——
  加入 `SetOption("wrap", (), _parse_bool_option,
  "wrap must be on|off ...", "wrap=on|off")`，仿照 `which_key`（:356-362）。
- `config.py:373-377` 的 `set_option_names()` 从 spec 自动派生 -> 补全
  列表无需手工修改。
- `yaterc_options.py:467-469` 的 `_extract_options` 遍历 `KNOWN_OPTIONS`；
  `:552-559` 的 which_key `isinstance(bool)` 校验 -> 加入并列的 `wrap`
  校验（bool 检查，否则追加配置错误）。
- `commands.py:36-40` 的 `SET_OPTION_INDEX` 从 specs 派生；`:47` 的 `SET_APPLY`；
  `:95-104` 的 `_apply_support_mouse`、`:107-122` 的 `_apply_which_key` 是
  apply 函数的先例；`:141-152` 的 `SET_APPLY.update(...)` 注册它们；
  `:429-460` 的 `_set()` 负责分发。
- `actions.py:26-251` 的 `populate(registry, editor)`；`:231` 的 `toggle_whichkey`、
  `:233` 的 `toggle_keymap`、`:235` 的 `toggle_screensaver` 是切换动作的先例；
  `:240-249` 的宏动作展示了「状态 + 刷新」模式。
- `editor.py:622-629` 的 `select_keymap`、`:692-703` 的 `set_readonly`、`:705-740`
  的 `set_filetype` 是编辑器侧的 `:set` 处理器（状态 -> 消息 ->
  `refresh_ui()`）。
- `test_set_options.py` 已存在（7.79 KB）：断言 specs/apply 覆盖率 —— 必须
  保持通过，并为 `wrap` 扩展。

## 3. 设计

- `YateConfig.wrap: bool = False`（默认关闭；AC1/AC3，零 yaterc 迁移）。
- `commands.py::_apply_wrap(editor, value)`：
  ```python
  enabled = cast(bool, value)
  editor.set_soft_wrap(enabled)
  editor.message(f"soft wrap {'on' if enabled else 'off'}", kind="ok")
  ```
  在 `SET_APPLY.update(...)` 中注册 `wrap=_apply_wrap`。
- `editor.py::set_soft_wrap(enabled: bool) -> None`：设置 `self.config.wrap`；
  关闭时，将每个窗格视图的 `scroll_col` 重置为 0（横向状态仅在
  不换行时有意义；保留之前的值？overview §7.4 第 5 项说关闭时
  scroll_col 保留在 ViewState 中 -> 保留它，不要重置）；
  调用 `self.refresh_ui()`。文档说明计划 B 的视图读取 `wrap_enabled=lambda:
  ed.config.wrap`，因此一次刷新即可传播。
- `editor.py::toggle_soft_wrap() -> None`：`self.set_soft_wrap(not self.config.wrap)`
  + 消息（消息放在 set_soft_wrap 内或此处 —— 只保留一个负责人）。
- `actions.py::populate`：注册 `toggle_soft_wrap` -> lambda ctx：
  `ctx` 通过闭包携带编辑器（`reg("toggle_soft_wrap", lambda ctx:
  editor.toggle_soft_wrap(), ...)`），仿照 `toggle_keymap`。
- Which-key 提示通过绑定 `description` 自动出现（计划 D）。

## 4. 文件（独占）

- `yate/config.py`
- `yate/yaterc_options.py`
- `yate/commands.py`
- `yate/actions.py`
- `yate/editor.py`
- `tests/test_set_options.py`（扩展）
- 新建 `tests/test_soft_wrap_config.py`

## 5. 步骤与验收命令

1. 加入 `KNOWN_OPTIONS`、`YateConfig.wrap`、`SET_OPTION_SPECS` 条目。
2. 在 `yaterc_options.py` 中为 `wrap` 加入 bool 校验。
3. 加入 `_apply_wrap` + `SET_APPLY.update`，扩展 `test_set_options.py`。
4. 加入 `editor.set_soft_wrap` / `toggle_soft_wrap` + `actions.populate` 条目。
5. 编写配置测试：默认 False；yaterc `wrap = on` 解析为 True；
   非法值产生配置错误；`:set wrap=on` 翻转配置；
   `toggle_soft_wrap` 动作翻转两次回到初态。
6. 验证：
   - `.venv\Scripts\python.exe -m pyright yate/config.py yate/yaterc_options.py yate/commands.py yate/actions.py yate/editor.py tests/test_set_options.py tests/test_soft_wrap_config.py`
   - `.venv\Scripts\python.exe -m pytest tests/test_set_options.py tests/test_soft_wrap_config.py -q -n 1`
   - `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`（editor.py 体积豁免不变；未登记不得越过 810 行）

## 6. 风险 / 回滚

- 风险：editor.py 807 行 -> 新增方法越过 800 行豁免必须保持
  登记状态（`SIZE_EXEMPT_FILES` 已包含 editor.py；守卫断言 len==6
  且成员资格，而非精确行数 -> 没问题，无需改规则；但仍需在
  计划回填中记录新的行数）。
- 风险：`:set` 补全列表漂移 -> `set_option_names()` 自动派生，
  无手工列表；`test_set_options.py` 中的覆盖率守卫可捕获遗漏。
- 回滚：还原五个源文件；删除新测试；恢复 test_set_options.py。

## 7. Mermaid

```mermaid
flowchart LR
  Y["yaterc wrap = on"] --> P["yaterc_options._extract_options"]
  S[":set wrap=on"] --> I["SET_OPTION_SPECS -> parse_bool"]
  I --> A["commands._apply_wrap"]
  A --> E["editor.set_soft_wrap -> config.wrap = True + refresh_ui"]
  K["alt+z (计划 D)"] --> T["editor.toggle_soft_wrap"]
  T --> E
  E --> V["计划 B 视图：wrap_enabled() lambda"]
```
