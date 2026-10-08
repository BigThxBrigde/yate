# support-mouse plan-a：`support_mouse` 配置管线（wave-1）

输入：overview.md 调研结论 §配置管线；issue IKJRFK 需求 2
（yaterc 新增 `support_mouse` 布尔选项，可启用/禁用）。
本计划只落配置通路与文档，不触碰任何鼠标行为（行为在 plan-c/e 消费该字段）。

## 一、独占文件清单

| 文件 | 操作 |
|---|---|
| `yate/config.py` | 修改 |
| `yate/yaterc.py` | 修改 |
| `yate/cli.py` | 修改（1 行日志） |
| `yate/docs/yaterc.en.md` | 修改 |
| `yate/docs/yaterc.zh.md` | 修改 |
| `yate/yaterc.example` | 修改（存在则加注释行，不存在则跳过并在此文档回填说明） |
| `tests/test_config.py` | 新增用例 |
| `tests/test_set_options.py` | 新增用例 |

## 二、具体修改

### 1. `yate/config.py`

1. `KNOWN_OPTIONS`（34-38 行）：追加 `"support_mouse"`：
   ```python
   KNOWN_OPTIONS: tuple[str, ...] = (
       "keymap", "theme", "tab_width", "use_spaces",
       "shell", "terminal_height", "show_hidden",
       "yate_trace", "yate_trace_level", "key_protocol",
       "support_mouse",
   )
   ```
2. `YateConfig`（122-173 行）：在 `show_hidden` 字段（146 行）之后新增：
   ```python
   #: Master switch for all mouse interaction (``support_mouse = False``
   #: in yaterc).  ``False`` makes the app drop every mouse event before
   #: it reaches any widget (gate lives in ``YateApp.on_event``).  On by
   #: default: mouse support is additive, the switch is an explicit
   #: opt-out (issue IKJRFK).
   support_mouse: bool = True
   ```
3. `SET_OPTION_SPECS`（259-309 行）：追加一个 `SetOption`（复用既有
   `_parse_bool_option`，config.py:250-252）：
   ```python
   SetOption(
       name="support_mouse",
       aliases=(),
       parse=_parse_bool_option,
       invalid_message="support_mouse must be on|off (true/false/1/0/yes/no accepted)",
       summary="support_mouse=on|off",
   ),
   ```

### 2. `yate/yaterc.py`

`_extract_options`（552 行起）在 `show_hidden` 分支（619-626 行）之后，
照同一布尔样板新增：

```python
support_mouse = options.get("support_mouse")
if support_mouse is not None:
    if isinstance(support_mouse, bool):
        config.support_mouse = support_mouse
    else:
        config.errors.append(
            f"support_mouse must be True or False, got {support_mouse!r}"
        )
```

### 3. `yate/cli.py`

resolved 启动日志（344-349 行）的格式串与实参各加一项
`support_mouse=%s` / `config.support_mouse`，使启动日志可回答
"鼠标开关生效值是多少"。

### 4. 双语手册（同改同验，硬约束）

- `yate/docs/yaterc.en.md`：选项表（65-87 行）在 `show_hidden` 行（79 行）
  之后插入：
  `| `support_mouse` | `bool` | `True` | `True` / `False` | Master switch for mouse interaction. `False` ignores every mouse event (text area, tab bar, explorer, terminal, scrollbars, separator drag); keyboard input is unaffected. Non-boolean values are rejected. |`
- `yate/docs/yaterc.zh.md`：对应位置插入语义一致的中文行。
- 若 `yate/yaterc.example` 存在：在布尔示例区追加注释行
  `# support_mouse = True   # set False to ignore all mouse input`。

## 三、新增测试（详细用例）

### `tests/test_config.py`

1. `test_support_mouse_defaults_true`
   - 前置：无（纯模型）。
   - 操作：`YateConfig()`。
   - 断言：`config.support_mouse is True`。
2. `test_support_mouse_rc_value_applied`
   - 前置：临时 rc 文件内容 `support_mouse = False`（fixture 参照本文件
     既有 rc 加载用例的 tmp_path 写法）。
   - 操作：`load_config([rc])`。
   - 断言：`config.support_mouse is False` 且 `config.errors == []`。
3. `test_support_mouse_rejects_non_bool_keeps_default`
   - 前置：rc 内容 `support_mouse = "yes"`（字符串故意的）。
   - 操作：`load_config([rc])`。
   - 断言：`config.support_mouse is True`（默认保留）且
     `config.errors == ["<rc>: support_mouse must be True or False, got 'yes'"]`
     形态（errors 含该子串即可，断言 `any("support_mouse must be True or False" in e for e in config.errors)`）。

### `tests/test_set_options.py`

4. `test_set_support_mouse_on_off_roundtrip`
   - 前置：参照本文件既有 `:set` 驱动方式构造 commands/编辑器夹具。
   - 操作：依次 `:set support_mouse=off`、`=on`。
   - 断言：off 后 `config.support_mouse is False`；on 后 `is True`。
5. `test_set_support_mouse_invalid_value_reports`
   - 操作：`:set support_mouse=maybe`。
   - 断言：消息行出现 `support_mouse must be on|off`，值不变。

## 四、验证方案

| 项 | 命令 / 步骤 | 通过判定 |
|---|---|---|
| 单测 | `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_set_options.py -q` | 退出码 0，含上述 5 个新用例 |
| 回归 | `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_cli.py tests/test_prompt_completion.py -q` | 退出码 0（`prompt_completion` 从 SET_OPTION_SPECS 派生 `:set` 候选，须确认新选项无副作用） |
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |
| 手册 | 双语表格逐行对照 | en/zh 行成对出现，默认值均为 `True` |

## 五、风险与回滚

- 风险：`SET_OPTION_SPECS` 是 `prompt_completion` 的派生源（config.py
  docstring 明示 A8 单源），新增选项改变 `:set` 补全候选——已列回归命令。
- 风险：`KNOWN_OPTIONS` 放行后，rc 中写错类型只会记 error 不中断加载
  （yaterc 惯例），无破坏性。
- 回滚：本计划全部改动为加法（无行为接线），单提交 `git revert` 即可
  完全还原；字段无人消费时 `support_mouse=True` 默认即现状。
